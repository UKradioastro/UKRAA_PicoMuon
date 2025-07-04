#!/bin/bash

# cpm bash script - process and plot

# entry to process yesterdays raw muon counts per minute
su pi -c "/usr/bin/python3 /home/pi/UKRAA_PicoMuon/scripts/ProcessDataCpmACM0.py \
                        >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot yesterdays counts per minute
su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataCpmACM0.gp \
                        >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot yesterdays counts per minute frequency
su pi -c "/usr/bin/gnuplot /home/pi/UKRAA_PicoMuon/scripts/PlotDataFreqACM0.gp \
                        >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/pi/UKRAA_PicoMuon/logfiles/log-error.txt"
