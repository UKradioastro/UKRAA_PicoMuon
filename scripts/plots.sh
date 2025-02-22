#!/bin/bash

echo "Start plotting yesterday's graphs..."

# Plot yesterdays counts per minute
su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataCpmACM0.gp   >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# Plot yesterdays counts per minute frequency
su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataFreqACM0.gp  >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# Plot yesterdays adc frequency
su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataAdcACM0.gp   >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# Plot yesterdays % muons & % neutron deviation
su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataDayACM0.gp   >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# Plot last weeks % muons & % neutron deviation
su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataWeekACM0.gp  >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# Plot last months % muons & % neutron deviation
su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataMonthACM0.gp >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# Plot last months % muons & % neutron deviation
#su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataMonthEnvironment.gp >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# Plot last months % muons & % neutron deviation
#su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataMonthSTPACM0.gp >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# Plot last months % muons & % neutron deviation
#su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataMonthPressureACM0.gp >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

echo "Completed plotting yesterday's graphs"