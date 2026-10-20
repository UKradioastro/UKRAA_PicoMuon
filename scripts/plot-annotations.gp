generatedAt = system("date -u '+%Y-%m-%d %H:%M:%S UTC'")
if (GPVAL_SYSTEM_ERRNO != 0) { exit error "Unable to determine plot generation time" }
generatedLabel = "\nGenerated ".generatedAt."\n"
observatoryLocation = system("PYTHONPATH=\"$PICOMUON_BASE_PATH/scripts\" python3 -c 'from picomuon_common import get_base_path; from picomuon_metadata import load_observation; print(load_observation(get_base_path()).get(\"Observatory\", {}).get(\"observatory_location\", \"\"))'")
if (GPVAL_SYSTEM_ERRNO != 0) { exit error "Unable to read observatory configuration for plotting" }
muonAxisLabel = "% change in muon flux".(strlen(observatoryLocation) ? " - ".observatoryLocation : "")
set datafile missing "nan"
