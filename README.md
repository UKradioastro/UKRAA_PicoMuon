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

### To do

Instructions on initial set-up.