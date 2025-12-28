#!/bin/bash

# adc bash script - process and plot

# entry to process yesterdays raw muon adc values
su pi -c "/usr/bin/python3 $HOME/UKRAA_PicoMuon/scripts/ProcessDataAdcACM0.py \
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot yesterdays adc frequency
su pi -c "/usr/bin/gnuplot $HOME/UKRAA_PicoMuon/scripts/PlotDataAdcACM0.gp \
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"
