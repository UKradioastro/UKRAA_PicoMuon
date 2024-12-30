# PicoMuon_Python_code
Set of Python code to run on a RPi4/5 to get, process and present data from the UKRAA PicoMuon detector

I have written this software to suit my set-up, feel free use as you see fit.

## Requirements

The software needed to run will depend on what you intend.  You will need the following:

* Essential: [Python 3] (https://www.python.org/)
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

The code assumes that you the UKRAA PicoMuon detector is connected to the RPi4/5 via USB and that it is /dev/ttyACM0 - you can check this by using "ls /dev/tty*" in a terminal window on the RPi4/5 and reviewing the response.

The code assumes user is "pi", if "pi" is not the user then need to change '/home/pi' to '/home/user' in the python and gnuplot scripts to whatever your username is.

The code assumes one detector connected to RPi USB and will be "/dev/ttyACM0", if there are other devices connected to the RPi and your detector is not "/dev/ttyACM0" then  then need to change '/dev/ttyACM0' to '/dev/ttyACMx' in the GetDataRaw.py python script.

"GetDataRawACM0.py" is run as a service

Other scripts (Python and gnuplot) are run from cron

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

1. Set hostname - set to whatever you want - but write it down, we will need it latter!
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

![img_13](images/RPi_imager_13.PNG)

When finished, you can remove the microSD card and select "CONTINUE" and close the Raspberry Pi Imager.

![img_14](images/RPi_imager_14.PNG).


### RPi4 configuration

Put the microSD card you have just created into your RPi4, connect the RPi to your LAN if necessary,  insert the power cable and turn on.

Using PuTTY (https://www.putty.org/)

In Host Name (or IP address), type the host name of your RPi that you wrote down earlier... and select open.

![img_15](images/RPi_imager_15.PNG)


You will be presented with a PuTTY Security Alert - select "Accept".  You will now have a PuTTY terminal window.

![img_16](images/RPi_imager_16.PNG)

Login as "pi" and enter your password

Now type "sudo apt update" and hit enter.  This will update the RPi OS

![img_17](images/RPi_imager_17.PNG)

Now type "sudo apt upgrade" and hit enter.  This will update any preinstalled software packages.  You will be asked to type "y" to proceed.

![img_18](images/RPi_imager_18.PNG)

You may be advised that you can remove "no longer required" packages.  You can type "sudo apt autoremove" to do this. Again, you will be asked to type "y" to proceed.

![img_19](images/RPi_imager_19.PNG)

We can now set up VNC to access the RPi from our desktop PC.

Type "sudo raspi-config" and hit enter.  We will be presented with the RPi configuration tool.  
Select "3 Interface Options" and press return.

![img_20](images/RPi_imager_20.PNG)

Now navigate down to "I3 VNC" and press return.

![img_21](images/RPi_imager_21.PNG)

Select "Yes" to enable the VNC Server and hit enter.  

![img_22](images/RPi_imager_22.PNG)

VNC server will now be enabled, hit enter.

![img_23](images/RPi_imager_23.PNG)

Finish with the Configuration Tool by selecting "Finish" and hit enter.

![img_24](images/RPi_imager_24.PNG)

Reboot the RPi, type "sudo reboot" and hit enter.  This will close the PuTTY connection.  You can close the Putty window.

![img_25](images/RPi_imager_25.PNG)


### Headless access to RPi via VNC

Using a VNC program like RealVNC (https://www.realvnc.com/en/), connect to your RPi...

Create a new connections and enter the hostname into the VNC Server box, add freindly name in the Name box and select okay.

![img_26](images/RPi_imager_26.PNG)

Open this VNC connection to your RPi, you will get a "VNC server not recognised" window from RealVNC. Select "Continue"

![img_27](images/RPi_imager_27.PNG)

You will now get an "Authentication" window from RealVNC, enter user and password details and select remember password to make it easier to login in future.

![img_28](images/RPi_imager_28.PNG)

You are now remotely accessing your RPi...

![img_29](images/RPi_imager_29.PNG)


### Add additional software to your RPi

We need to add some dependencies to the RPi.

1. pandas

Open a terminal window and type "sudo apt install python3-pandas and hit enter.  You will be asked to type "y" to proceed.  This will install pandas and other dependencies related to pandas.

![img_30](images/RPi_imager_30.PNG)

2. gnuplot

Open the application menu (Raspberry) and select "Preferences" and "Add/Remove Software".

![img_31](images/RPi_imager_31.PNG)

From the "Add/Remove Software window type "gnuplot" into the search bar and hit enter.  When the available packages have been found select the packages in the following image and select "Apply".

![img_32](images/RPi_imager_32.PNG)

You will be asked to enter the pi password.  Enter your pi password and select "Authenticate".  This will then install the gnuplot package and any dependencies required.

![img_33](images/RPi_imager_33.PNG)

Select OK to close the window.


### Get code from github

Open the web browser on the RPi. In the address bar type "https://github.com/UKradioastro/PicoMuon_Python_code" and press enter.

![img_37](images/RPi_imager_37.PNG)

Select the "<> Code" tab and then select "Download ZIP".  This will download all the necessary code/files for the Python code.  Close the web browser.

![img_38](images/RPi_imager_38.PNG)

Open file manager and navigate to the "Downloads" folder - you should see a zip folder of the downloaded files.

![img_39](images/RPi_imager_39.PNG)

Double click on the zip folder to bring up the extraction tool. Select the "extract files" to extract all the files in the zip folder.

![img_40](images/RPi_imager_40.PNG)

You will be asked where you want the files to be extracted to - change the selection to the pi home directory."  Close the extraction tool when finished.

![img_41](images/RPi_imager_41.PNG)

From the open file manager navigate to /home/pi directory and you will see a new folder "PicoMuon_Python_code-main".  Select this folder and right-click mouse and select "Rename".

![img_42](images/RPi_imager_42.PNG)

Change the name of the folder to "UKRAA_muons" and select "OK".

![img_43](images/RPi_imager_43.PNG)

Scripts and folder structure should now be in place to run the code.


### Where is my detector?.

Plug your detector into any of the RPI USB ports - I normally use the blue ports (USB3).

Open a terminal window and type "ls /dev/tty*" and press return.
![img_48](images/RPi_imager_48.PNG)

You are looking for /dev/ttyACM0 - this will be on the RHS of the screen above.

This is the USB address for your attached detector - if you have more than one detector attached you may see /dev/ttyACM1 etc.

If you do not see /dev/ttyACM0, then unplug and plug the detector back in and try again.

As long as we see /dev/ttyACM0 then we do not have to make any changes to the python scripts, because they are looking for ACM0.

### Running the code to get data from the detector.

It is an easy process to set up services to run the code, check it is running and restart the code if it stps.

To do this we need to create the service, then enable the service.

1. Open terminal window
2. Type "sudo nano /etc/systemd/system/muon_ACM0.service" and press enter - this will open nano text editor.
3. Type in the following text...
![img_44](images/RPi_imager_44.PNG)
4. Save (Ctrl + s) and exit (Ctrl + x)
5. Type "sudo chmod 644 /etc/systemd/system/muon_ACM0.service" to change permissions of your created service file and press enter.
![img_45](images/RPi_imager_45.PNG)
6. Type "sudo systemctl daemon-reload" to reload services.
![img_46](images/RPi_imager_46.PNG)
7. Type "sudo systemctl enable muon_ACM0.service" to enable your new service.
![img_47](images/RPi_imager_47.PNG)

The service you have set will automatically start whenever the RPi is started or rebooted.

To check status of your service type:
"sudo systemctl status muon_ACM0.service"

We expect to see...
![img_49](images/RPi_imager_49.PNG)

If we dont see green "enabled" and "active", then we have a typo in the muon_ACM0.service file.

To start your service type:
"sudo systemctl start muon_ACM0.service"

To stop your service type:
"sudo systemctl stop muon_ACM0.service"


### Running the code to process and plot the data from the detector.

The data will be processed to get counts per minute and the frequency of the adc values for the previous day.

A request will be made to NEST to get the previous days recorded neutron count, this data will be overlayed onto the counts per minute graphs.

Three plots will be created:
* counts per minute
* frequency of cunts per minute
* frequency of ADC values recorded

This can be done after midnight automatically using CRON.

1. Open terminal window
2. Type "sudo crontab -e" and press enter - this will open crontab text editor.  The first time it will ask what editor you prefer - I prefer nano.

![img_50](images/RPi_imager_50.PNG)

3. Scroll to bottom and type the following...

![img_51](images/RPi_imager_51.PNG)

4. Save (Ctrl + s) and exit (Ctrl + x).
5. If this went well you will see "crontab: installing new crontab" on the terminal window.

This should now process and graph yesterdays data from the detector overnight.

Plots will appear in the "plots" folder and the "temp" folder.

The "plots" folder hold plots for each day in year/month folder.

The "temp" folder only holds plots for yesterday, updated each day, for pushing to a website/etc.


### Creating simple home intranet web server on your RPi to view your results on your smart phome.

We can create a simple web server on our RPi to be able to view our detector results on our smart phone when connected to our home metwork.

To set up the web server on the RPi, follow the instruction from "tom's HARDWARE" (https://www.tomshardware.com/news/raspberry-pi-web-server,40174.html).  Only need to do first section - upto 9. Build your website.




