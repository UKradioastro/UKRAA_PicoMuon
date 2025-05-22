#!/bin/bash

echo "Start processing day, week & month data..."

# cron entry to process yesterdays data
su pi -c "/usr/bin/python3 /home/pi/UKRAA_PicoMuon/scripts/ProcessDataDayACM0.py   >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# cron entry to process last weeks data
su pi -c "/usr/bin/python3 /home/pi/UKRAA_PicoMuon/scripts/ProcessDataWeekACM0.py     >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# cron entry to process last months data
su pi -c "/usr/bin/python3 /home/pi/UKRAA_PicoMuon/scripts/ProcessDataMonthACM0.py      >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

echo "Completed processing day, week & month data"