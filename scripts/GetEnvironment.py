#!/usr/bin/env python3

# ==========================================================================================
# INFORMATION
#
# program to get the temperature and pressure from N15Weather
#


# ==========================================================================================
# imports
import paramiko
import os
from datetime import datetime, timezone, timedelta

# ==========================================================================================
# Main program

# Path to file to write data to
DataPath = '/home/pi/UKRAA_muons/data/environment/'\
           + datetime.strftime(datetime.now(timezone.utc) - timedelta(1), '%Y')\
           + '/'\
           + datetime.strftime(datetime.now(timezone.utc) - timedelta(1), '%Y-%m')
print('DataPath: ' + DataPath)

# check if the specific path exists
pathExists = os.path.exists(DataPath)
if not pathExists:
    # create directory structure
    os.makedirs(DataPath)
    print('Made folder as necessary')
    
print('Did not need to create any folders - already existed')

# Path and name of file to write data to
SaveFileName = '/home/pi/UKRAA_muons/data/environment/'\
               + datetime.strftime(datetime.now(timezone.utc) - timedelta(1), '%Y')\
               + '/'\
               + datetime.strftime(datetime.now(timezone.utc) - timedelta(1), '%Y-%m')\
               + '/'\
               + datetime.strftime(datetime.now(timezone.utc) - timedelta(1), '%Y-%m-%d')\
               + '.txt'
print('Saving data to: ' + SaveFileName)

# source file path and name to get data from
SoureFileName = '/home/pi/weather/data/calib/'\
                + datetime.strftime(datetime.now(timezone.utc) - timedelta(1), '%Y')\
                + '/'\
                + datetime.strftime(datetime.now(timezone.utc) - timedelta(1), '%Y-%m')\
                + '/'\
                + datetime.strftime(datetime.now(timezone.utc) - timedelta(1), '%Y-%m-%d')\
                + '.txt'
print('Getting data from: ' + SoureFileName)

ssh = paramiko.SSHClient() 
ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
ssh.connect('192.168.1.123', username='pi', password='We@th3R')
sftp = ssh.open_sftp()
sftp.get(SoureFileName, SaveFileName)
sftp.close()
ssh.close()

# ==========================================================================================
# END of program