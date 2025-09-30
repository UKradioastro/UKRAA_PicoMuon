#!/bin/bash

# cpm bash script - process and plot

# entry to process yesterdays raw muon counts per minute
su pi -c "/usr/bin/python3 $HOME/UKRAA_PicoMuon/scripts/ProcessDataCpmACM0.py \
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot yesterdays counts per minute
su pi -c "/usr/bin/gnuplot $HOME/UKRAA_PicoMuon/scripts/PlotDataCpmACM0.gp \
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot yesterdays counts per minute frequency
su pi -c "/usr/bin/gnuplot $HOME/UKRAA_PicoMuon/scripts/PlotDataFreqACM0.gp \
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"
