# PicoMuon_Python_code
Set of Python code to run on a RPi4/5 to get, process and present data from the UKRAA PicoMuon detector

I have written this software to suit my set-up, feel free use as you see fit.

## Requirements

The software needed to run will depend on what you intend.  You will need the following:

* Essential: [Python] 3 (https://www.python.org/)
* Optional: [Pandas] for neutron data (https://pandas.pydata.org/)
* Optional: [gnuplot] for graphing processed data (http://www.gnuplot.info/)

## File structure

### scripts
```
└── 📁scripts
    └── 📁__pycache__
        └── nest.cpython-311.pyc
    └── DateTimeTest.py
    └── GetDataRaw.py
    └── GetDataRawACM0.py
    └── GetEnvironment.py
    └── GetNeutronData.py
    └── nest.py
    └── PlotMuonAdcACM0.gp
    └── PlotMuonCpmACM0.gp
    └── PlotMuonFreqACM0.gp
    └── ProcessMuonAdcACM0.py
    └── ProcessMuonCpmACM0.py
```

### data
```
└── 📁data
    └── 📁environment
        └── 📁2024
            └── 📁2024-10
                └── 2024-10-30.txt
        └── info.txt
    └── 📁neutrons
        └── 📁2024
            └── 📁2024-10
                └── 2024-10-30.txt
    └── 📁processed
        └── 📁adc
            └── 📁ACM0
                └── 📁2024
                    └── 📁2024-10
                        └── 2024-10-30.txt
        └── 📁cpm
            └── 📁ACM0
                └── 📁2024
                    └── 📁2024-10
                       └── 2024-10-30.txt
    └── 📁raw
        └── 📁ACM0
            └── 📁2024
                └── 📁2024-10
                   └── 2024-10-31.txt
```

### plots
```
└── 📁plots
    └── 📁adc
        └── 📁ACM0
          └── 2024-10-30_ADC_T_plot.png
    └── 📁cpm
        └── 📁ACM0
           └── 2024-10-30_CPM_T_plot.png
    └── 📁freq
        └── 📁ACM0
          └── 2024-10-30_Freq_T_plot.png
```

### temp
```
└── 📁temp
    └── ACM0_B-Adc.png
    └── ACM0_B-Cpm.png
    └── ACM0_B-Freq.png
    └── ACM0_C-Adc.png
    └── ACM0_C-Cpm.png
    └── ACM0_C-Freq.png
    └── ACM0_T-Adc.png
    └── ACM0_T-Cpm.png
    └── ACM0_T-Freq.png
```

## Using the code

The code assumes that you the UKRAA PicoMuon detector is connected to the RPi4/5 via USB and that it is /dev/ttyACM0 - you can check this by using "ls /dev/tty*" in a terminal window on the RPi4/5 and reviewing the response.  If different then ocurances of '/dev/ttyACM0' in GetDataRaw.py will need to be changed.

The code assumes user is "pi", if "pi" is not the user then need to change '/home/pi' to '/home/user' in the python and gnuplot scripts to whatever your username is.


The code assumes directory structure '/home/pi/UKRAA_muons/';
* ~ $ mkdir UKRAA_muons
* ~ $ cd UKRAA_muons
* ~/UKRAA_muons $ mkdir data plots scripts temp
* copy scripts from github to scripts folder
* modify as necessary

I run "GetDataRawACM0.py" as a service

I run the other python scripts from cron

## Set-up instructions

### Raspberry Pi OS

Download Raspberry Pi Imager for your operating system.
Web link https://www.raspberrypi.com/software/

![img_0](images/RPI_OS.PNG)

Run Raspberry Pi Imager.

![img_1](images/RPi_imager_1.PNG)

Select "CHOOSE DEVICE" and then select your Raspberry Pi device.

![img_2](images/RPi_imager_2.PNG)

Select "CHOOSE OS" and then select "Raspberry Pi OS (64bit)".

![img_3](images/RPi_imager_3.PNG)

Select "CHOOSE STORAGE" and select your microSD card for your RPi.

![img_4](images/RPi_imager_4.PNG)

Select "NEXT"

![img_5](images/RPi_imager_5.PNG)

You are presented with a "Use OS customisation?" window, select "EDIT SETTINGS".

![img_6](images/RPi_imager_6.PNG)


On the "GENERAL" page...

1. Set hostname - set to whatever you want
2. Set username and password 
* Keep username as "pi"
* set your own password
3. Configure wireless LAN
* if you wish to use you RPi wirelessly
* Enter your wireless network's SSID, Password and Country
4. Set locale settings
* set timezone and keyboard to your preferences

![img_7](images/RPi_imager_7.PNG)

5. Select "SERVICES"
* Keep defaults

![img_8](images/RPi_imager_8.PNG)

6. Select "OPTIONS"
* Keep defaults
![img_9](images/RPi_imager_9.PNG)

7. Select "SAVE"

Now apply the customised OS settings by selecting "YES".

![img_10](images/RPi_imager_10.PNG)

You will be asked if you wish to proceed, select "YES".

![img_11](images/RPi_imager_11.PNG)

The operating system will now be written to the microSD card 

![img_12](images/RPi_imager_12.PNG)

and then verified, this take a bit of time...



