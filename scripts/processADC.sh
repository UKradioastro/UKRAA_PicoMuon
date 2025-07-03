#!/bin/bash

# adc bash script - process and plot

# entry to process yesterdays raw muon adc values
su pi -c "/usr/bin/python3 /home/pi/UKRAA_PicoMuon/scripts/ProcessDataAdcACM0.py   >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot yesterdays adc frequency
su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataAdcACM0.gp      >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt 2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"
