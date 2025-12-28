#!/bin/bash


echo "Starting patch_1 UKRAA PicoMuon..."
echo "This patch will correct for missing NMDB data from 26th July 2025"


#echo "Start updating packages..."
#sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y
#echo "Finished updating packages"

# create copy of any existing NMDB data for 26/07/2025
echo "If there is NMDB data for 2025-07-26, move to 2025-07-26_old.txt..."
if [ -r $HOME/UKRAA_PicoMuon/data/NMDB/neutrons/2025/2025-07/2025-07-26.txt ]; then
    su pi -c "mv -f $HOME/UKRAA_PicoMuon/data/NMDB/neutrons/2025/2025-07/2025-07-26.txt \
                    $HOME/UKRAA_PicoMuon/data/NMDB/neutrons/2025/2025-07/2025-07-26_old.txt"
fi

# copy correct NMDB data to folder
echo "Moving correct NMDB data to $HOME/UKRAA_PicoMuon/data/NMDB/neutrons/2025/2025-07/..."
sudo -u pi cp -v $HOME/UKRAA_PicoMuon/patch_1/2025-07-26.txt \
                 $HOME/UKRAA_PicoMuon/data/NMDB/neutrons/2025/2025-07/2025-07-26.txt
echo "Finished moving correct NMDB data to $HOME/UKRAA_PicoMuon/data/NMDB/neutrons/2025/2025-07/"


# create copy of any processed day data for 26/07/2025
echo "If there is processed day data for 2025-07-26, move to 2025-07-26_old.txt..."
if [ -r $HOME/UKRAA_PicoMuon/data/processed/day/ACM0/2025/2025-07/2025-07-26.txt ]; then
    su pi -c "mv -f $HOME/UKRAA_PicoMuon/data/processed/day/ACM0/2025/2025-07/2025-07-26.txt \
                    $HOME/UKRAA_PicoMuon/data/processed/day/ACM0/2025/2025-07/2025-07-26_old.txt"
fi

# Process day data for 26/07/2025
echo "Process day data for 26 July 2025..."
echo "For Raspberry Pi 4 this will take about 90 minutes... please be patient..."
echo "For Raspberry Pi 5 this will take about 20 minutes... please be patient..."
su pi -c "/usr/bin/python3 $HOME/UKRAA_PicoMuon/patch_1/Process20250726.py"
echo "Completed processing revised day data for 26/07/2025"


echo "Completed patch_1 UKRAA PicoMuon."
echo "Your week/month plots should be correct after these data are processed tomorrow with the corrected day data."
sleep 10


# if successful
echo "Removing patch_1 directory and exiting..."
exec rm -vrf $HOME/UKRAA_PicoMuon/patch_1
