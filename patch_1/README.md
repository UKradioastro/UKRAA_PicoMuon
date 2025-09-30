<div align=center>
<img src="../images/UKRAA_Logo_Black.svg" width=**400** height=**400**/>
</div>


# Patch#1 for the UKRAA PicoMuon
[![License](https://img.shields.io/badge/license-MIT-brightgreen.svg)](/LICENSE)


Set of code to patch missing NMDB data from 26/July/2025

This software was written to suit a specific set-up, feel free to use as you see fit.

---

&nbsp;

<!-- =============================================================================== --> 
## Installing the patch

1. Log into your Raspberry Pi4/5 using VNC.

2. Open your web browser, type the following command into the URL window and press enter
```
https://download-directory.github.io/?url=https%3A%2F%2Fgithub.com%2FUKradioastro%2FUKRAA_PicoMuon%2Ftree%2Fmain%2Fpatch_1
```

![img_26](../images/RPi_imager_26.PNG)

This will download a zip file of the updated code to your RPi **$HOME/Downloads** folder.

![img_27](../images/RPi_imager_27.PNG)

Close your web browser.


3. Open **File Manager** and navigate to **$HOME/Downloads**. You should see the zip file you just downloaded.

![img_28](../images/RPi_imager_28.PNG)

10. Double click on the downloaded zip file **UKradioastro UKRAA_PicoMuon main patch_1.zip**.  This will open the RPi **xarchiver** utility.

![img_29](../images/RPi_imager_29.PNG)

11. Now click on the **extract** icon on the menu ribbon.

![img_30](../images/RPi_imager_30.PNG)

12. Change **Extract to:** from **/tmp** to **$HOME/Downloads**, then click on the **Extract** button

![img_31](../images/RPi_imager_31.PNG)

Close the RPi xarchiver utility.

13. You should now see a new unzipped folder in the Downloads folder

![img_32](../images/RPi_imager_32.PNG)

14. Select **UKradioastro UKRAA_PicoMuon main patch_1** folder and rename **patch_1** (Right click mouse to bring up function).

![img_33](../images/RPi_imager_33.PNG)

15. Select the **patch_1** folder and copy (Right click mouse to bring up function).

16. Navigate to the PicoMuon directory, **$HOME/UKRAA_PicoMuon**, and paste the **patch_1** folder

![img_34](../images/RPi_imager_34.PNG)

Close the **File Manager** window

17. Open a terminal window and type the following command and press enter
```
cd ~/UKRAA_PicoMuon/patch_1
```

![img_35](../images/RPi_imager_35.PNG)

This will take you to the **patch_1** directory inside **$HOME/UKRAA_PicoMuon**

18. Type the following command and press enter
```
chmod +x *.sh
```

![img_36](../images/RPi_imager_36.PNG)

This will make the **patch_1.sh** script executable.


19. Type the following command and press enter
```
sudo bash patch_1.sh
```

![img_37](../images/RPi_imager_37.PNG)

This will run the patch script.
The patch script will take about 90 minutes on a Raspberry Pi 4 and about 20 minutes on a Raspberry Pi 5.

20. That's it!  You should see the following...

![img_38](../images/RPi_imager_38.PNG)

The patch is now complete; it will populate correct NMDB data for 26th July 2025, process the day data for 26th July 2025 and post to your logfile.
No changes have been made to the week or month data files.
When these are next processed you should see corrected data in these plots when they are posted to your intranet web page at 9.30am in the morning.


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

&nbsp;

---

&nbsp;
<!-- =============================================================================== --> 
### Contact us

Please send an e-mail to picomuon@ukraa.com

&nbsp;

---