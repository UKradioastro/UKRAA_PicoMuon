#!/bin/bash


echo "Start updating UKRAA PicoMuon software..."


echo "Updating PicoMuon crontab entry..."
echo "Clearing current crontab entry..."
echo "NOTE: if you have edited your sudo crontab - this will be deleted.  You will need to reedit sudo crontab post update."
sudo crontab -r
echo "Now creating new crontab entry..."
sudo crontab -l -u root | cat - /home/pi/UKRAA_PicoMuon/update/crontab-update.cron | crontab -u root -
echo "Finished updating PicoMuon crontab entry"


echo "Moving updates python scripts to /UKRAA_PicoMuon/scripts..."
sudo -u pi cp /home/pi/UKRAA_PicoMuon/update/ProcessDataDayACM0.py /home/pi/UKRAA_PicoMuon/scripts/ProcessDataDayACM0.py
sudo -u pi cp /home/pi/UKRAA_PicoMuon/update/ProcessDataMonthACM0.py /home/pi/UKRAA_PicoMuon/scripts/ProcessDataMonthACM0.py
sudo -u pi cp /home/pi/UKRAA_PicoMuon/update/ProcessDataWeekACM0.py /home/pi/UKRAA_PicoMuon/scripts/ProcessDataWeekACM0.py
echo "Finished moving updated python scripts to /UKRAA_PicoMuon/scripts"


echo "Moving new bash script to /UKRAA_PicoMuon/scripts..."
sudo -u pi cp /home/pi/UKRAA_PicoMuon/update/process.sh /home/pi/UKRAA_PicoMuon/scripts/process.sh
sudo -u pi cp /home/pi/UKRAA_PicoMuon/update/plots.sh /home/pi/UKRAA_PicoMuon/scripts/plots.sh
echo "Finished moving new bash script to /UKRAA_PicoMuon/scripts"


echo "Sorting out updated/new file permissions..."
sudo -u pi chmod +x /home/pi/UKRAA_PicoMuon/scripts/*.py
sudo -u pi chmod +x /home/pi/UKRAA_PicoMuon/scripts/*.sh
echo "Finished sorting out updated/new file permissions"


echo "Moving updated index.html file to /var/www/html..."
sudo cp /home/pi/UKRAA_PicoMuon/update/index.html /var/www/html/index.html
echo "Finished moving updated index.html file to /var/www/html"


echo "Completed updating UKRAA PicoMuon software."
echo "REMEMBER: if you had your own edits to sudo crontab, you will need to reappy them."