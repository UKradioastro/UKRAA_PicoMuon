#!/bin/bash

# data bash script - scrape, process and plot

# entry to get NMDB Oulu neutron data
su pi -c "/usr/bin/python3 $HOME/UKRAA_PicoMuon/scripts/GetDataNMDBneutron.py \
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to process yesterdays data
su pi -c "/usr/bin/python3 $HOME/UKRAA_PicoMuon/scripts/ProcessDataDayACM0.py \
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot yesterdays % muons & % neutron deviation
su pi -c "/usr/bin/gnuplot $HOME/UKRAA_PicoMuon/scripts/PlotDataDayACM0.gp\
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to process last weeks data
su pi -c "/usr/bin/python3 $HOME/UKRAA_PicoMuon/scripts/ProcessDataWeekACM0.py\
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot last weeks % muons & % neutron deviation
su pi -c "/usr/bin/gnuplot $HOME/UKRAA_PicoMuon/scripts/PlotDataWeekACM0.gp\
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to process last months data
su pi -c "/usr/bin/python3 $HOME/UKRAA_PicoMuon/scripts/ProcessDataMonthACM0.py\
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot last months % muons & % neutron deviation
su pi -c "/usr/bin/gnuplot $HOME/UKRAA_PicoMuon/scripts/PlotDataMonthACM0.gp\
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to process last 90 days data
su pi -c "/usr/bin/python3 $HOME/UKRAA_PicoMuon/scripts/ProcessData90DaysACM0.py\
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot last 90 days % muons & % neutron deviation
su pi -c "/usr/bin/gnuplot $HOME/UKRAA_PicoMuon/scripts/PlotData90DaysACM0.gp\
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot last 90 days  % muons & STP deviation
su pi -c "/usr/bin/gnuplot $HOME/UKRAA_PicoMuon/scripts/PlotData90DaysSTPACM0.gp\
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot last 90 days pressure coefficient
su pi -c "/usr/bin/gnuplot $HOME/UKRAA_PicoMuon/scripts/PlotData90DaysPcoeffACM0.gp\
                        >> $HOME/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>$HOME/UKRAA_PicoMuon/logfiles/log-error.txt"
