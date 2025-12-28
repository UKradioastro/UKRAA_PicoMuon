#!/bin/bash


echo "Start updating UKRAA PicoMuon software..."


echo "Start updating packages..."
sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y
echo "Finished updating packages"

echo "Updating PicoMuon crontab entry..."
echo "Clearing current crontab entry..."
echo "NOTE: if you have edited your sudo crontab - this will be deleted.  You will need to reedit sudo crontab post update."
sudo crontab -u root -r
echo "Now creating new crontab entry..."
sudo crontab -u root -l | cat - $HOME/UKRAA_PicoMuon/update/crontab-update.cron | crontab -u root -
echo "Finished updating PicoMuon crontab entry"


echo "Creating additional directory structure..."
sudo -u pi mkdir -vp $HOME/UKRAA_PicoMuon/data/environment/coefficient
sudo -u pi mkdir -vp $HOME/UKRAA_PicoMuon/data/processed/3month/ACM0
sudo -u pi mkdir -vp $HOME/UKRAA_PicoMuon/plots/3month/ACM0
echo "Additional directory structure created"


echo "Moving new and updated Python scripts to /UKRAA_PicoMuon/scripts..."
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/GetDataNMDBneutron.py    $HOME/UKRAA_PicoMuon/scripts/GetDataNMDBneutron.py
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/ProcessData90DaysACM0.py $HOME/UKRAA_PicoMuon/scripts/ProcessData90DaysACM0.py
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/ProcessDataAdcACM0.py    $HOME/UKRAA_PicoMuon/scripts/ProcessDataAdcACM0.py
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/ProcessDataCpmACM0.py    $HOME/UKRAA_PicoMuon/scripts/ProcessDataCpmACM0.py
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/ProcessDataDayACM0.py    $HOME/UKRAA_PicoMuon/scripts/ProcessDataDayACM0.py
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/ProcessDataMonthACM0.py  $HOME/UKRAA_PicoMuon/scripts/ProcessDataMonthACM0.py
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/ProcessDataWeekACM0.py   $HOME/UKRAA_PicoMuon/scripts/ProcessDataWeekACM0.py
echo "Finished moving new and updated Python scripts to /UKRAA_PicoMuon/scripts"


echo "Removing deprecated Python scripts from /UKRAA_PicoMuon/scripts..."
sudo -u pi rm -vf $HOME/UKRAA_PicoMuon/scripts/GetDataNeutron.py
echo "Finished removing deprecated Python scripts from /UKRAA_PicoMuon/scripts"


echo "Moving new bash scripts to /UKRAA_PicoMuon/scripts..."
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/processADC.sh  $HOME/UKRAA_PicoMuon/scripts/processADC.sh
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/processCPM.sh  $HOME/UKRAA_PicoMuon/scripts/processCPM.sh
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/processData.sh $HOME/UKRAA_PicoMuon/scripts/processData.sh
echo "Finished moving new bash scripts to /UKRAA_PicoMuon/scripts"


echo "Removing deprecated bash scripts from /UKRAA_PicoMuon/scripts..."
sudo -u pi rm -vf $HOME/UKRAA_PicoMuon/scripts/plots.sh
sudo -u pi rm -vf $HOME/UKRAA_PicoMuon/scripts/process.sh
echo "Finished removing deprecated bash scripts from /UKRAA_PicoMuon/scripts"

echo "Moving new and updated gnuplot scripts to /UKRAA_PicoMuon/scripts..."
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/PlotData90DaysACM0.gp       $HOME/UKRAA_PicoMuon/scripts/PlotData90DaysACM0.gp
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/PlotData90DaysPcoeffACM0.gp $HOME/UKRAA_PicoMuon/scripts/PlotData90DaysPcoeffACM0.gp
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/PlotData90DaysSTPACM0.gp    $HOME/UKRAA_PicoMuon/scripts/PlotData90DaysSTPACM0.gp
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/PlotDataAdcACM0.gp          $HOME/UKRAA_PicoMuon/scripts/PlotDataAdcACM0.gp
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/PlotDataCpmACM0.gp          $HOME/UKRAA_PicoMuon/scripts/PlotDataCpmACM0.gp
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/PlotDataDayACM0.gp          $HOME/UKRAA_PicoMuon/scripts/PlotDataDayACM0.gp
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/PlotDataFreqACM0.gp         $HOME/UKRAA_PicoMuon/scripts/PlotDataFreqACM0.gp
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/PlotDataMonthACM0.gp        $HOME/UKRAA_PicoMuon/scripts/PlotDataMonthACM0.gp
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/update/PlotDataWeekACM0.gp         $HOME/UKRAA_PicoMuon/scripts/PlotDataWeekACM0.gp
echo "Finished moving new and updated gnuplot scripts to /UKRAA_PicoMuon/scripts"


echo "Moving neutron data to new folder structure..."
sudo -u pi mkdir -vp $HOME/UKRAA_PicoMuon/data/NMDB/neutrons
sudo -u pi cp -vr $HOME/UKRAA_PicoMuon/data/neutrons $HOME/UKRAA_PicoMuon/data/NMDB
sudo -u pi rm -vrf $HOME/UKRAA_PicoMuon/data/neutrons
echo "Finished moving neutron data to new folder structure"


echo "Sorting out updated/new file permissions..."
sudo -u pi chmod -v +x $HOME/UKRAA_PicoMuon/scripts/*.py
sudo -u pi chmod -v +x $HOME/UKRAA_PicoMuon/scripts/*.sh
echo "Finished sorting out updated/new file permissions"


echo "Moving updated index.html file to /var/www/html..."
sudo cp -v $HOME/UKRAA_PicoMuon/update/index.html /var/www/html/index.html
echo "Finished moving updated index.html file to /var/www/html"

echo "Final cleanup, removing unneeded directories..."
sudo -u pi rm -vrf $HOME/UKRAA_PicoMuon/WWW
sudo -u pi rm -vrf $HOME/UKRAA_PicoMuon/install
echo "Finished final cleanup, removed unneeded directories"


echo "Completed updating UKRAA PicoMuon software."
echo "REMEMBER: if you had your own edits to sudo crontab, you will need to reapply them."
sleep 10

# if successful
echo "Removing update directory and exiting..."
exec rm -vrf $HOME/UKRAA_PicoMuon/update
