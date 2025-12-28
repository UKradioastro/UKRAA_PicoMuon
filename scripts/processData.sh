#!/bin/bash

# data bash script - scrape, process and plot

# entry to get NMDB Oulu neutron data
su $USER -c "/usr/bin/python3 /home/$USER/UKRAA_PicoMuon/scripts/GetDataNMDBneutron.py \
                           >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                           2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to process yesterdays data
su $USER -c "/usr/bin/python3 /home/$USER/UKRAA_PicoMuon/scripts/ProcessDataDayACM0.py \
                           >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                           2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot yesterdays % muons & % neutron deviation
su $USER -c "/usr/bin/gnuplot /home/$USER/UKRAA_PicoMuon/scripts/PlotDataDayACM0.gp\
                           >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                           2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to process last weeks data
su $USER -c "/usr/bin/python3 /home/$USER/UKRAA_PicoMuon/scripts/ProcessDataWeekACM0.py\
                        >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot last weeks % muons & % neutron deviation
su $USER -c "/usr/bin/gnuplot /home/$USER/UKRAA_PicoMuon/scripts/PlotDataWeekACM0.gp\
                        >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to process last months data
su $USER -c "/usr/bin/python3 /home/$USER/UKRAA_PicoMuon/scripts/ProcessDataMonthACM0.py\
                        >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot last months % muons & % neutron deviation
su $USER -c "/usr/bin/gnuplot /home/$USER/UKRAA_PicoMuon/scripts/PlotDataMonthACM0.gp\
                        >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to process last 90 days data
su $USER -c "/usr/bin/python3 /home/$USER/UKRAA_PicoMuon/scripts/ProcessData90DaysACM0.py\
                        >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot last 90 days % muons & % neutron deviation
su $USER -c "/usr/bin/gnuplot /home/$USER/UKRAA_PicoMuon/scripts/PlotData90DaysACM0.gp\
                        >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot last 90 days  % muons & STP deviation
su $USER -c "/usr/bin/gnuplot /home/$USER/UKRAA_PicoMuon/scripts/PlotData90DaysSTPACM0.gp\
                        >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"

# entry to plot last 90 days pressure coefficient
su $USER -c "/usr/bin/gnuplot /home/$USER/UKRAA_PicoMuon/scripts/PlotData90DaysPcoeffACM0.gp\
                        >> /home/$USER/UKRAA_PicoMuon/logfiles/log-PicoMuonACM0.txt \
                        2>>/home/$USER/UKRAA_PicoMuon/logfiles/log-error.txt"
