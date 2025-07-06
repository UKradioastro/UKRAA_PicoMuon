#!/bin/bash -e


echo "Start installing UKRAA PicoMuon software..."


echo "Start installing pandas software..."
sudo apt install python3-pandas -y
echo "pandas software installed"


echo "Start installing gnuplot software..."
sudo apt install gnuplot -y
sudo apt install gnuplot-doc -y
sudo apt install gnuplot-x11 -y
echo "gnuplot software installed"


echo "Creating directory structure..."
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/environment/coefficient
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/NMDB/neutrons
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/processed/adc/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/processed/cpm/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/processed/day/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/processed/month/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/processed/week/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/data/raw/ACM0
sudo -u pi mkdir -v  /home/pi/UKRAA_PicoMuon/logfiles
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/3month/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/adc/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/cpm/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/day/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/freq/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/month/ACM0
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/plots/week/ACM0
sudo -u pi mkdir -v  /home/pi/UKRAA_PicoMuon/temp
sudo -u pi mkdir -vp /home/pi/UKRAA_PicoMuon/WWW/temp
echo "Directory structure created"

echo "Sort out file permissions..."
sudo -u pi chmod +x /home/pi/UKRAA_PicoMuon/scripts/*.py
sudo -u pi chmod +x /home/pi/UKRAA_PicoMuon/scripts/*.sh
echo "File permissions sorted out"

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
sudo apt update

echo "Install apache2..."
sudo apt install apache2 -y

echo "Install php..."
sudo apt install php libapache2-mod-php -y

echo "Install mariadb..."
sudo apt install mariadb-server -y
sudo mysql_secure_installation

echo "Install the php-mysql connector..."
sudo apt install php-mysql -y

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


echo "Changing wallpaper..."
sudo -u pi cp /home/pi/UKRAA_PicoMuon/images/UKRAA-wallpaper.png /home/pi/Pictures/UKRAA-wallpaper.png
sudo -u pi pcmanfm --set-wallpaper /home/pi/Pictures/UKRAA-wallpaper.png --wallpaper-mode=fit
echo "Wallpaper changed"


echo "Final cleanup..."
rm -rfv /home/pi/UKRAA_PicoMuon/images
rm -rvf /home/pi/UKRAA_PicoMuon/WWW
rm -rvf /home/pi/UKRAA_PicoMuon/update
rm -v /home/pi/UKRAA_PicoMuon/README.md
echo "Finished final cleanup"


echo "Completed installing UKRAA PicoMuon software."
sleep 10

# if successful
echo "Removing install directory and exiting..."
exec rm -rvf /home/pi/UKRAA_PicoMuon/install
