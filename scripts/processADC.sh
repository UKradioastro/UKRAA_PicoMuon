#!/bin/bash

# adc bash script - process and plot

# entry to process yesterdays raw muon adc values
su $USER -c "/usr/bin/python3 /home/$USER/UKRAA_PicoMuon/scripts/ProcessDataAdcACM0.py \
                        >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot yesterdays adc frequency
su $USER -c "/usr/bin/gnuplot /home/$USER/UKRAA_PicoMuon/scripts/PlotDataAdcACM0.gp \
                        >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"
