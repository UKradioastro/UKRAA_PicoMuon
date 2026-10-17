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
    local plot_script=$1 target_date=$2
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
    local input="$PICOMUON_BASE_PATH/data/$category/ACM0/${target_date:0:4}/${target_date:0:7}/$target_date.txt"
    if [ ! -f "$input" ]; then
        if [[ "$category" = week || "$category" = month ]]; then
            write_log_entry "$plot_script" "Skipped: no $category product for $target_date (see period-processing entries)" >> "$MAIN_LOG"
            return 0
        fi
        write_log_entry "$plot_script" "ERROR: required input missing: $input" >> "$ERROR_LOG"
        return 1
    fi
    write_log_entry "$plot_script" "Started plot for $target_date" >> "$MAIN_LOG"
    local status=0
    PICOMUON_TARGET_DATE=$target_date run_logged_command "$plot_script" \
        run_as_owner "$GNUPLOT" "$PICOMUON_BASE_PATH/scripts/$plot_script" || status=$?
    if [ "$status" -eq 0 ]; then
        write_log_entry "$plot_script" "Completed plot for $target_date" >> "$MAIN_LOG"
    fi
    return "$status"
}
