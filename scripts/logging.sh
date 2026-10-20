#!/bin/bash

# Shared columnar logging helper for UKRAA PicoMuon bash scripts.
# Format: YYYY-MM-DD HH:MM:SS UTC : %-26s : message

write_log_entry() {
    local source_name=$1
    local message=$2
    local timestamp line
    timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    while IFS= read -r line || [ -n "$line" ]; do
        printf '%s : %-26s : %s\n' "$timestamp" "$source_name" "${line%$'\r'}"
    done <<< "$message"
}

format_log_stream() {
    local source_name=$1
    local line
    local formatted='^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} UTC : [^:]+ : '
    while IFS= read -r line || [ -n "$line" ]; do
        line=${line%$'\r'}
        if [[ "$line" =~ $formatted ]]; then
            printf '%s\n' "$line"
        else
            write_log_entry "$source_name" "$line"
        fi
    done
}

# Wait for both stream formatters so diagnostics are written before the summary.
run_logged_command() (
    local source_name=$1
    shift
    local output_fd error_fd output_pid error_pid status=0
    exec {output_fd}> >(format_log_stream "$source_name" >> "$MAIN_LOG")
    output_pid=$!
    exec {error_fd}> >(format_log_stream "$source_name" >> "$ERROR_LOG")
    error_pid=$!
    "$@" >&"$output_fd" 2>&"$error_fd" || status=$?
    exec {error_fd}>&-
    exec {output_fd}>&-
    wait "$error_pid" || status=1
    wait "$output_pid" || status=1
    if [ "$status" -ne 0 ]; then
        write_log_entry "$source_name" "ERROR: command failed (exit code $status)" >> "$ERROR_LOG"
    fi
    return "$status"
)

run_as_owner() {
    if [ "$(id -un)" = "$PICOMUON_FILE_OWNER" ]; then
        (
            export TZ=UTC TERM=dumb
            cd "$PICOMUON_BASE_PATH" || return
            "$@"
        )
        return $?
    fi
    local command_text="" argument
    for argument in "$@"; do
        printf -v argument '%q' "$argument"
        command_text+="$argument "
    done
    su -s /bin/bash "$PICOMUON_FILE_OWNER" -c \
        "export PICOMUON_BASE_PATH=$(printf '%q' "$PICOMUON_BASE_PATH") PICOMUON_TARGET_DATE=$(printf '%q' "${PICOMUON_TARGET_DATE:-}") TZ=UTC TERM=dumb; cd $(printf '%q' "$PICOMUON_BASE_PATH") && $command_text"
}

run_logged_plot() {
    local plot_script=$1 target_date=$2 detector=${3:-}
    local category
    case "$plot_script" in
        PlotDataCpmACM0.gp|PlotDataFreqACM0.gp) category=cpm ;;
        PlotDataAdcACM0.gp) category=adc ;;
        PlotDataDayACM0.gp) category=day ;;
        PlotDataWeekACM0.gp) category=week ;;
        PlotDataMonthACM0.gp) category=month ;;
        *)
            write_log_entry "$plot_script" "ERROR: unknown plot script" >> "$ERROR_LOG"
            return 1
            ;;
    esac
    local data_detector=ACM0 output_detector=ACM0 temp_root="$PICOMUON_BASE_PATH/temp"
    if [ -n "$detector" ]; then
        PYTHONPATH="$PICOMUON_BASE_PATH/scripts" "${PYTHON:-/usr/bin/python3}" -c \
            'import sys; from picomuon_common import get_base_path; from picomuon_processing import processing_label; processing_label(get_base_path(), sys.argv[1])' \
            "$detector" || return 1
        data_detector="detectors/$detector"
        output_detector=$detector
        temp_root="$temp_root/detectors/$detector"
    fi
    local input="$PICOMUON_BASE_PATH/data/$category/$data_detector/${target_date:0:4}/${target_date:0:7}/$target_date.txt"
    local temp_group=yesterday plot_category=$category suffix event output
    local outputs=()
    case "$plot_script" in
        PlotDataCpmACM0.gp) suffix=Cpm ;;
        PlotDataFreqACM0.gp) suffix=Freq; plot_category=freq ;;
        PlotDataAdcACM0.gp) suffix=Adc ;;
        *) temp_group=periods; outputs=("$temp_root/periods/${output_detector}_${category}_plot.png") ;;
    esac
    if [ "$temp_group" = yesterday ]; then
        for event in T B C; do
            outputs+=("$temp_root/yesterday/${output_detector}_${event}-$suffix.png")
        done
    fi
    # Named publication must never reuse yesterday's successful plot after a skip/failure.
    if [ -n "$detector" ]; then
        run_logged_command "$plot_script" run_as_owner rm -f -- "${outputs[@]}" || return 1
    fi
    if [ ! -f "$input" ]; then
        if [[ "$category" = week || "$category" = month ]]; then
            write_log_entry "$plot_script" "Skipped: no $category product for $target_date (see period-processing entries)" >> "$MAIN_LOG"
            return 0
        fi
        write_log_entry "$plot_script" "ERROR: required input missing: $input" >> "$ERROR_LOG"
        return 1
    fi
    if ! run_logged_command "$plot_script" run_as_owner mkdir -p \
        "$temp_root/$temp_group" "$PICOMUON_BASE_PATH/plots/$plot_category/$data_detector"; then
        return 1
    fi
    write_log_entry "$plot_script" "Started plot for $target_date" >> "$MAIN_LOG"
    local plot_weather=0
    if [ "$plot_script" = PlotDataCpmACM0.gp ]; then
        local weather_input="$PICOMUON_BASE_PATH/data/weather/${target_date:0:4}/${target_date:0:7}/$target_date.txt"
        if [ -f "$weather_input" ]; then
            plot_weather=1
            write_log_entry "$plot_script" "Using stored modelled 2 m air temperature for $target_date" >> "$MAIN_LOG"
        else
            write_log_entry "$plot_script" "Temperature overlay unavailable: no weather product for $target_date; plotting counts only" >> "$MAIN_LOG"
        fi
    fi
    local neutron_column=7 header
    if [[ "$category" = day || "$category" = week || "$category" = month ]]; then
        while IFS= read -r header; do
            [[ "$header" = \#* || -z "$header" ]] && continue
            if [[ "$header" = *",detector_name,"* ]]; then
                neutron_column=12
            fi
            break
        done < "$input"
    fi
    local status=0
    PICOMUON_TARGET_DATE=$target_date run_logged_command "$plot_script" \
        run_as_owner "$GNUPLOT" -e "plotWeather=$plot_weather;neutronColumn=$neutron_column;detectorLabel='$detector'" "$PICOMUON_BASE_PATH/scripts/$plot_script" || status=$?
    if [ "$status" -eq 0 ] && [ -n "$detector" ]; then
        for output in "${outputs[@]}"; do
            if [ ! -s "$output" ]; then
                write_log_entry "$plot_script" "ERROR: expected plot output missing or empty: $output" >> "$ERROR_LOG"
                status=1
            fi
        done
    fi
    if [ "$status" -ne 0 ] && [ -n "$detector" ]; then
        run_logged_command "$plot_script" run_as_owner rm -f -- "${outputs[@]}" || return 1
    fi
    if [ "$status" -eq 0 ]; then
        write_log_entry "$plot_script" "Completed plot for $target_date" >> "$MAIN_LOG"
    fi
    return "$status"
}
