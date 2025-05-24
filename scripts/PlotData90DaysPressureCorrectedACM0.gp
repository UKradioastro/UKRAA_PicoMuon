#!/usr/bin/gnuplot -persist
#
#    
#    	G N U P L O T
#    	Version 5.2 patchlevel 6    last modified 2019-01-01 
#    
#    	Copyright (C) 1986-1993, 1998, 2004, 2007-2018
#    	Thomas Williams, Colin Kelley and many others
#    
#    	gnuplot home:     http://www.gnuplot.info
#    	faq, bugs, etc:   type "help FAQ"
#    	immediate help:   type "help"  (plot window: hit 'h')

# Reset gnuplot variables
reset

# Set terminal 
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# Set up data paths
pathData        = "/home/pi/UKRAA_muons/data/processed/3month/ACM0"

# Year folder
YearFolder = "/".system("date -d yesterday +'%Y'")

# YearMonth folder
YearMonthFolder = "/".system("date -d yesterday +'%Y-%m'")

# YearMonthDay file
YmdFile = "/".system("date -d yesterday +'%Y-%m-%d'").".txt"

# Path to each data file for graphing
FileData        = pathData.YearFolder.YearMonthFolder.YmdFile

# Set separator to ","
set datafile separator ","

# undertake stats before setting timeformat and xdata
stats FileData using 4 output prefix "MUON" nooutput
stats FileData using 5 output prefix "PRESSURE" nooutput
stats FileData using 6 output prefix "TEMPERATURE" nooutput
stats FileData using 7 output prefix "NEUTRON" nooutput

# least square fit
c = 0
f(x) = a0*x + c
set fit nolog quiet
fit f(x) FileData using ($6-PRESSURE_mean):((($4-MUON_mean)/MUON_mean)*100) via a0


# date to be processed
date = system("date -d yesterday +'%Y-%m-%d'")

# Start of X axis time
StartXaxis = system("date -d '90 days ago' +'%Y-%m-%d'")." 00:00:00"

# End of X axis time
EndXaxis = system("date +'%Y-%m-%d'")." 00:00:00"

# setting output path to include data stamp
# Path to directory to store file
# week data
pathPlot3 = "/home/pi/UKRAA_muons/plots/3month/ACM0/".date."_90_days_pressure_corrected_plot.png"

# Title for graph
# muons detected
GraphTitle3 = "% change of muon and neutron count rate from mean count rate for the last 90 days.\n Graph is updated every day at 9.30am \n"

# Set data types
set xdata time

# Set format types
set format x "%d %b %Y" timedate
set format y "%.1f" 
set timefmt "%Y-%m-%d %H:%M:%S"

# Set grid format
set grid xtics nomxtics ytics nomytics noztics nomztics nortics nomrtics \
 nox2tics nomx2tics noy2tics nomy2tics nocbtics nomcbtics
set grid layerdefault linetype 0 linecolor 0 linewidth 0.500 dashtype solid,  linetype 0 linecolor 0 linewidth 0.500 dashtype solid

# Set Legend (Key) above plot
set key outside above center
set key samplen 10
set key nobox

# X-axis tics
set xtics border out scale 1,0.5 nomirror norotate  autojustify
set xtics autofreq
set xtics textcolor rgb "black"
set xtics font ",8"

# Y-axis tics
set mytics 2.0
set ytics border out scale 1,0.5 nomirror norotate  autojustify
set ytics norangelimit autofreq
set ytics textcolor rgb "dark-violet"

# X-axis label and ranges
set xlabel "Date (%d %b %Y UTC)" 
set xlabel textcolor rgb "black" norotate
set xrange [ StartXaxis : EndXaxis ] noreverse nowriteback

# Y-axis labels and ranges
set ylabel "% change in muon flux N15 London UK" 
set ylabel textcolor rgb "dark-violet" rotate
#set yrange [ (((MUON_min/MUON_mean)*100)-100)-5 : (((MUON_max/MUON_mean)*100)-100)+5 ] noreverse nowriteback
set yrange [*:*] noreverse nowriteback

# set STATS labels on graph
set label 1 sprintf("Mean muon counts per 60 minutes: %0.1f", MUON_mean)
set label 1 at graph 0.02, 0.95 tc default
#set label 2 sprintf("Mean neutron counts per 60 minutes: %0.1f", NEUTRON_mean)
#set label 2 at graph 0.02, 0.90 tc default

# Plot command 
# for last month
GraphTitle = GraphTitle3
set key title GraphTitle
set output pathPlot3
plot FileData using 1:((a0*($6-PRESSURE_mean))*MUON_mean) linetype 1 linewidth 1 linecolor rgb "dark-violet" notitle "60-min averages of muons detected" with lines

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# setting output path to include data stamp

# Path to directory to store file
pathPlot = "/home/pi/UKRAA_muons/temp/ACM0_90_days_Pressure_Corrected_plot"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# print to log file
set print "-"
print "Completed month plot for ".system("date -d yesterday +'%Y-%m-%d'")." at ".system("date +'%H:%M:%S'")." on ".system("date +'%A %d %B %Y'")

# This is important because it closes our output file.
set output

# EOF