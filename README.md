<div align=center>
<img src="images/UKRAA_Logo_Black.svg" width=**400** height=**400**/>
</div>


# Python code for the UKRAA PicoMuon
[![License](https://img.shields.io/badge/license-MIT-brightgreen.svg)](/LICENSE)


Set of Python code to run on a RPi4/5 to get, process and present data from the UKRAA PicoMuon detector

This software was written to suit a specific set-up, feel free to use as you see fit.

---

&nbsp;
<!-- =============================================================================== --> 
## Using the code

The code assumes that your UKRAA PicoMuon detector is connected to the RPi4/5 via supplied USB cable and that it is /dev/ttyACM0 - you can check this by using **ls /dev/tty*** in a terminal window on the RPi4/5 and reviewing the response.

The code assumes username is **pi**.  If **pi** is not the username, then you will need to change all occurances of '/home/pi' to '/home/*username*' in the python and gnuplot scripts, where *username* is the username you have selected for your RPi4/5.

The code assumes one detector connected to the RPi4/5 USB and will be **/dev/ttyACM0**, if there are other devices connected to the RPi and your detector is not **/dev/ttyACM0**, then you will need to change **/dev/ttyACM0** to **/dev/*ttyACMx*** in the **GetDataRawACM0.py** python script, where *ttyACMx* is the tty address of you connected detector.

**GetDataRawACM0.py** is run as a service.

Other scripts (Python and gnuplot) are run from **cron**

---

&nbsp;
<!-- =============================================================================== --> 
### Where is my detector?.

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

5. As long as we see **/dev/ttyACM0** then we do not have to make any changes to the python scripts, because they are looking for **ACM0**.

&nbsp;

---
&nbsp;
<!-- =============================================================================== --> 
## Install software on RPi

```
git clone https://github.com/UKradioastro/UKRAA_PicoMuon
cd ~/UKRAA_PicoMuon/install
chmod +x *.sh
sudo bash install.sh
```

---

&nbsp;
<!-- =============================================================================== --> 
## What does the code do?

### GetDataRawACM0.py ###

This code receives the event data from the UKRAA PicoMuon detector via the supplied USB cable and stores it to the raw data folder:

```
└── 📁data
    └── 📁raw
        └── 📁ACM0
            └── 📁2025
                └── 📁2025-01
                    └── 2025-01-16.txt
```

The data will be processed to get counts per minute and the frequency of the adc values for the previous day.

Three plots will be created:
* counts per minute
* frequency of counts per minute
* frequency of ADC values recorded

A request will be made to [NMDB](https://www.nmdb.eu/) via NEST to get the previous days recorded neutron count, this data will be overlayed onto the counts per minute graphs.


This can be done after midnight automatically using **CRON** because the processing of the cpm takes about 6 hours and the processing of the adc values takes about 1 hour on a RPi4.  It takes less time to run these two processes on a RPi5.


---

&nbsp;
<!-- =============================================================================== --> 
### Creating simple home intranet web server on your RPi.

We can create a simple web server on our RPi so that we can view our detector's results on our smart phone when connected to our home network.

To set up the web server on the RPi, follow the instruction from [**tom's HARDWARE**](https://www.tomshardware.com/news/raspberry-pi-web-server,40174.html).  Only need to do first section - upto **9. Build your website**.

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