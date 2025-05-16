#!/bin/bash


echo "Start updating UKRAA PicoMuon software..."


echo "Updating PicoMuon crontab entry..."
echo "Clearing current crontab entry..."
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
echo "Finished moving new bash script to /UKRAA_PicoMuon/scripts"


echo "Sorting out updated/new file permissions..."
sudo -u pi chmod +x /home/pi/UKRAA_PicoMuon/scripts/*.py
sudo -u pi chmod +x /home/pi/UKRAA_PicoMuon/scripts/*.sh
echo "Finished sorting out updated/new file permissions"


echo "Moving updated index.html file to /var/www/html..."
sudo cp /home/pi/UKRAA_PicoMuon/update/index.html /var/www/html/index.html
echo "Finished moving updated index.html file to /var/www/html"


echo "Final update cleanup..."
rm -rfv /home/pi/UKRAA_PicoMuon/images
rm -v /home/pi/UKRAA_PicoMuon/README.md
echo "Finished final update cleanup"


echo "Completed updating UKRAA PicoMuon software."
