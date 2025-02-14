#!/bin/bash


echo "Start installing UKRAA PicoMuon software..."


echo "Start installing pandas software..."
sudo apt install python3-pandas
echo "pandas software installed"


echo "Start installing gnuplot software..."
sudo apt-get install gnuplot
sudo apt-get install gnuplot-doc
sudo apt-get install gnuplot-x11
echo "gnuplot software installed"


echo "Creating directory structure..."
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/processed/adc/ACM0
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/processed/cpm/ACM0
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/processed/day/ACM0
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/processed/month/ACM0
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/processed/week/ACM0
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/raw/ACM0
sudo -u  pi mkdir -v  /home/pi/UKRAA_PicoMuon/logfiles
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/adc/ACM0
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/cpm/ACM0
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/day/ACM0
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/freq/ACM0
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/month/ACM0
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/week/ACM0
sudo -u  pi mkdir -v  /home/pi/UKRAA_PicoMuon/temp
sudo -u  pi mkdir -vp /home/pi/UKRAA_PicoMuon/WWW/temp
echo "Directory structure created"


echo "Start installing PicoMuonACM0.service..."
sudo cp -f /home/pi/UKRAA_PicoMuon/install/PicoMuonACM0.service /etc/systemd/system
sudo chmod 644 /etc/systemd/system/PicoMuonACM0.service
sudo systemctl daemon-reload
sudo systemctl enable PicoMuonACM0.service
sudo systemctl start PicoMuonACM0.service
echo "PicoMuonACM0.service installed and started"


echo "Start installing PicoMuon crontab entry..."
sudo crontab -l -u root | cat - /home/pi/UKRAA_PicoMuon/install/crontab-PicoMuonACM0-entry.cron | crontab -u root -
echo "PicoMuon crontab entry installed"

echo "Start installing web server on RPi..."

echo "Update packages..."
sudo apt-get update

echo "Install apache2..."
sudo apt-get install apache2 -y

echo "Install php..."
sudo apt-get install php libapache2-mod-php -y

echo "Install mariadb..."
sudo apt-get install mariadb-server
sudo mysql_secure_installation

echo "Install the php-mysql connector..."
sudo apt install php-mysql

echo "Restart apache2..."
sudo service apache2 restart
echo "web server installed on RPi"


echo "Move files to /var/www/html..."
sudo cp /home/pi/UKRAA_PicoMuon/WWW/index.html /var/www/html/index.html
sudo cp -r /home/pi/UKRAA_PicoMuon/WWW/images /var/www/html/
sudo cp -r /home/pi/UKRAA_PicoMuon/WWW/temp /var/www/html/
echo "Files moved to /var/www/html"


echo "Start installing webpage update crontab entry..."
sudo crontab -l -u root | cat - /home/pi/UKRAA_PicoMuon/install/crontab-webpage-update-entry.cron | crontab -u root -
echo "webpage update crontab entry installed"


echo "Final cleanup..."
rm -rfv /home/pi/UKRAA_PicoMuon/images
rm -v /home/pi/UKRAA_PicoMuon/README.md
echo "Finished final cleanup"


echo "Completed installing UKRAA PicoMuon software."
