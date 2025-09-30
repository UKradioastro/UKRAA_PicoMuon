#!/bin/bash -e


echo "Start installing UKRAA PicoMuon software..."

echo "What is your username?"
read uservar


echo "Start installing pandas software..."
apt install python3-pandas -y
echo "pandas software installed"


echo "Start installing gnuplot software..."
apt install gnuplot -y
apt install gnuplot-doc -y
apt install gnuplot-x11 -y
echo "gnuplot software installed"


echo "Creating directory structure..."
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/data/environment/coefficient
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/data/NMDB/neutrons
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/data/processed/3month/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/data/processed/adc/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/data/processed/cpm/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/data/processed/day/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/data/processed/month/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/data/processed/week/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/data/raw/ACM0
sudo -u uservar mkdir -v  /home/uservar/UKRAA_PicoMuon/logfiles
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/plots/3month/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/plots/adc/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/plots/cpm/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/plots/day/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/plots/freq/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/plots/month/ACM0
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/plots/week/ACM0
sudo -u uservar mkdir -v  /home/uservar/UKRAA_PicoMuon/temp
sudo -u uservar mkdir -vp /home/uservar/UKRAA_PicoMuon/WWW/temp
echo "Directory structure created"

echo "Sort out file permissions..."
sudo -u uservar chmod -v +x /home/uservar/UKRAA_PicoMuon/scripts/*.py
sudo -u uservar chmod -v +x /home/uservar/UKRAA_PicoMuon/scripts/*.sh
echo "File permissions sorted out"

echo "Start installing PicoMuonACM0.service..."
cp -vf /home/uservar/UKRAA_PicoMuon/install/PicoMuonACM0.service /etc/systemd/system
chmod -v 644 /etc/systemd/system/PicoMuonACM0.service
systemctl daemon-reload
systemctl enable PicoMuonACM0.service
systemctl start PicoMuonACM0.service
echo "PicoMuonACM0.service installed and started"


echo "Start installing PicoMuon crontab entry..."
echo "Clearing current crontab entry..."
echo "NOTE: if you have edited your sudo crontab - this will be deleted.  You will need to reedit sudo crontab post update."
sudo crontab -u root -r
crontab -u root -l  | cat - /home/uservar/UKRAA_PicoMuon/install/crontab-PicoMuonACM0-entry.cron | crontab -u root -
echo "PicoMuon crontab entry installed"

echo "Start installing web server on RPi..."

echo "Update packages..."
apt update

echo "Install apache2..."
apt install apache2 -y

echo "Install php..."
apt install php libapache2-mod-php -y

echo "Install mariadb..."
apt install mariadb-server -y
mysql_secure_installation

echo "Install the php-mysql connector..."
apt install php-mysql -y

echo "Restart apache2..."
service apache2 restart
echo "web server installed on RPi"


echo "Move files to /var/www/html..."
cp -v /home/uservar/UKRAA_PicoMuon/WWW/index.html /var/www/html/index.html
cp -vr /home/uservar/UKRAA_PicoMuon/WWW/images /var/www/html/
cp -vr /home/uservar/UKRAA_PicoMuon/WWW/temp /var/www/html/
echo "Files moved to /var/www/html"


echo "Start installing webpage update crontab entry..."
crontab -u root -l | cat - /home/uservar/UKRAA_PicoMuon/install/crontab-webpage-update-entry.cron | crontab -u root -
echo "webpage update crontab entry installed"


echo "Final cleanup..."
sudo -u uservar rm -vrf /home/uservar/UKRAA_PicoMuon/images
sudo -u uservar rm -vrf /home/uservar/UKRAA_PicoMuon/WWW
sudo -u uservar rm -vrf /home/uservar/UKRAA_PicoMuon/update
sudo -u uservar rm -v /home/uservar/UKRAA_PicoMuon/README.md
echo "Finished final cleanup"


echo "Completed installing UKRAA PicoMuon software."
sleep 10

# if successful
echo "Removing install directory and exiting..."
exec rm -vrf /home/uservar/UKRAA_PicoMuon/install
