<div align=center>
<img src="images/UKRAA_Logo_Black.svg" width=**400** height=**400**/>
</div>


# Python code for the UKRAA PicoMuon
[![License](https://img.shields.io/badge/license-MIT-brightgreen.svg)](/LICENSE)


Set of Python code to run on a RPi4/5 to get, process and present data from the UKRAA PicoMuon detector

This software was written to suit a specific set-up, feel free to use as you see fit.


Instructions for setting up a Raspberry Pi4/5 are included in the **docs** folder

---

&nbsp;
<!-- =============================================================================== --> 
### Can I update to latest version?

There is a section on updating your software to the latest version at the bottom of this README.

&nbsp;

---

&nbsp;
<!-- =============================================================================== --> 
### Where is my detector?

Plug your detector into any of the RPi USB ports - I normally use the blue ports (USB3).

1. Open a terminal window and type the following command and press enter
```
ls /dev/tty*
```

![img_48](images/RPi_imager_48.PNG)

&nbsp;

2. You are looking for **/dev/ttyACM0** - this is on the right hand side of the screen shot above.

&nbsp;

3. This is the USB address for your attached detector - if you have more than one detector attached you may see **/dev/ttyACM1** etc.

&nbsp;

4. If you do not see **/dev/ttyACM0**, then unplug and plug the detector back in and try again.

&nbsp;

5. As long as you see **/dev/ttyACM0** then you do not have to make any changes to the python scripts, because they are looking for **ACM0**.

&nbsp;

---

&nbsp;
<!-- =============================================================================== --> 
## Install the software onto your RPi

1. Log into your Raspberry Pi4/5 using VNC.

&nbsp;

2. Open a terminal window, type the following command and press enter
```
git clone https://github.com/UKradioastro/UKRAA_PicoMuon
```

![img_01](images/RPi_imager_01.PNG)

This downloads the code into a `UKRAA_PicoMuon` directory under the current user's home directory.

---

&nbsp;
<!-- =============================================================================== --> 
## Using the code

The raw data collector resolves serial settings from `config/USB.ini`, with support for stable `/dev/serial/by-id/` device paths configured via `python3 scripts/ConfigureUSB.py` (defaulting gracefully to `/dev/ttyACM0`). The installer uses the account that invoked `sudo`, so the software does not require a user named `pi`. Python and gnuplot scripts resolve paths from the installation directory.

**GetDataRaw.py** is run as the systemd service `PicoMuon.service`. Daily processing and plotting are run by a managed root crontab entry, with jobs executed as the installing user.

---

&nbsp;
<!-- =============================================================================== --> 
## Install the software onto your RPi


1. Open a terminal window and type the following command and press enter
```
cd ~/UKRAA_PicoMuon
```

![img_02](images/RPi_imager_02.PNG)

This takes you to the root of your cloned repository.


2. Type the following command and press enter
```
sudo bash install/install.sh
```

![img_04](images/RPi_imager_04.PNG)

The installer installs the required packages, configures the collector service for your account, and replaces only the PicoMuon block in root's crontab. Daily processing starts at 01:15 local time; until Phase 2 replaces the legacy processing, it can take many hours to finish.

---

&nbsp;
<!-- =============================================================================== --> 
## What does the code do?

The code receives the event data from the UKRAA PicoMuon detector via serial over the supplied USB cable and stores the event data to the raw data folder:

The raw data will be processed overnight, via CRON, to get counts per minute, the frequency of the counts per minute and the frequency of the adc values for your previous day's data.

Processed products are stored directly under `data/` in their own folders (for example, `data/cpm/`, `data/day/`, and `data/adc/`); they are no longer nested under `data/processed/`. Processed data files include a first-line column header, while raw event files retain their existing format.

Three plots will be created:
* counts per minute
* frequency of counts per minute
* frequency of ADC values recorded

A request will be made to [NMDB](https://www.nmdb.eu/) via NEST to get the previous days recorded neutron count, this data will be overlaid onto the day / week / month % deviation counts per minute graphs.

These will appear as the required amount of data is recorded by the detector

A simple web server and web page is set up on your RPi so that you can view your detector's results on your desktop PC and/or smart phone when connected to your home network.

To access the webpage on your desktop PC or your smart phone…

1.	Open your preferred web application (Safari, Chrome, Firefox, etc.).

2.	In the search bar type the following and press enter
```
http://rpi4-UKRAA.local
```

This will take you to the web page for your detector, displaying yesterday’s events graphs.

NOTE: if you have a different **hostname** for your RPi, change the search bar entry to…

**http://_hostname_.local**

Where *hostname* is the hostname for your RPi setup.

---

&nbsp;
<!-- =============================================================================== --> 
## Check GetDataRaw.py is running

1. To check the **status** of your service, type the following command and press enter.
```
sudo systemctl status PicoMuon.service
```

&nbsp;

2. To **start** your service, type the following command and press enter.
```
sudo systemctl start PicoMuon.service
```

&nbsp;

3. To **stop** your service, type the following command and press enter.
```
sudo systemctl stop PicoMuon.service
```

&nbsp;

4. To **enable** your service, type the following command and press enter.
```
sudo systemctl enable PicoMuon.service
```

&nbsp;

5. To **disable** your service, type the following command and press enter.
```
sudo systemctl disable PicoMuon.service
```

&nbsp;

---

&nbsp;
<!-- =============================================================================== --> 
## Updating your software

1. Log into your Raspberry Pi4/5 using VNC.


2. Open your web browser, type the following command into the URL window and press enter
```
https://download-directory.github.io/?url=https%3A%2F%2Fgithub.com%2FUKradioastro%2FUKRAA_PicoMuon%2Ftree%2Fmain%2Fupdate
```

![img_05](images/RPi_imager_05.PNG)

This will download a zip file of the updated code to your RPi **~/Downloads** folder.

![img_06](images/RPi_imager_06.PNG)

Close your web browser.


3. Open **File Manager** and navigate to **~/Downloads**. You should see the zip file you just downloaded.

![img_07](images/RPi_imager_07.PNG)

4. Double click on the downloaded zip file **UKradioastro UKRAA_PicoMuon main update.zip**.  This will open the RPi **xarchiver** utility.

![img_08](images/RPi_imager_08.PNG)

5. Now click on the **extract** icon on the menu ribbon.

![img_09](images/RPi_imager_09.PNG)

6. Change **Extract to:** from **/tmp** to **~/Downloads**, then click on the **Extract** button

![img_10](images/RPi_imager_10.PNG)

Close the RPi xarchiver utility.

7. You should now see a new unzipped folder in the Downloads folder

![img_11](images/RPi_imager_11.PNG)

8. Select **UKradioastro UKRAA_PicoMuon main update** folder and rename **update** (Right click mouse to bring up function).

![img_12](images/RPi_imager_12.PNG)

9. Select the **update** folder and copy (Right click mouse to bring up function).

10. Navigate to the PicoMuon directory, **~/UKRAA_PicoMuon**, and paste the **update** folder

![img_14](images/RPi_imager_14.PNG)

Close the **File Manager** window

11. Open a terminal window and type the following command and press enter
```
cd ~/UKRAA_PicoMuon/update
```

![img_15](images/RPi_imager_15.PNG)

This will take you to the **update** directory inside **~/UKRAA_PicoMuon**

12. Type the following command and press enter
```
chmod +x *.sh
```

![img_16](images/RPi_imager_16.PNG)

This will make the **update.sh** script executable.


13. Type the following command and press enter
```
sudo bash update.sh
```

![img_17](images/RPi_imager_17.PNG)

This will run the update script.

14. That's it!  You should see the following...

![img_18](images/RPi_imager_18.PNG)

The updated code is now set; it will get the data from the detector, process yesterdays data, plot yesterdays data and post yesterdays plots to your intranet web page once per day, at 9.30am in the morning.

&nbsp;

---

&nbsp;
<!-- =============================================================================== --> 
### License

MIT License

Copyright (c) 2024 UKRAA

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the **Software**), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED **AS IS**, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


---

&nbsp;
<!-- =============================================================================== --> 
### Contact us

Please send an e-mail to picomuon@ukraa.com