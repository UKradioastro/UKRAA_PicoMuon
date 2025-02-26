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
pathData        = "/home/pi/UKRAA_PicoMuon/data/processed/month/ACM0"

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
stats FileData using 5 output prefix "TEMPERATURE" nooutput
stats FileData using 6 output prefix "PRESSURE" nooutput
stats FileData using 7 output prefix "NEUTRON" nooutput

# date to be processed
date = system("date -d yesterday +'%Y-%m-%d'")

# Start of X axis time
StartXaxis = system("date -d 'last month' +'%Y-%m-%d'")." 00:00:00"

# End of X axis time
EndXaxis = system("date +'%Y-%m-%d'")." 00:00:00"

# setting output path to include data stamp
# Path to directory to store file
# week data
pathPlot3 = "/home/pi/UKRAA_PicoMuon/plots/month/ACM0/".date."_month_weather_plot.png"

# Title for graph
# muons detected
GraphTitle3 = "Pressure and temperature changes for the last month.\n Graph is updated every day at 9.30am \n"

# Set data types
set xdata time

# Set format types
set format x "%d %b %Y" timedate
set format y "%2.0f" 
#set format y2 "%3.0f" 
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
set ytics textcolor rgb "dark-magenta"

# Y2-axis tics
#set my2tics 2.0
#set y2tics border out scale 1,0.5 nomirror norotate  autojustify
#set y2tics norangelimit autofreq
#set y2tics textcolor rgb "grey30"

# X-axis label and ranges
set xlabel "Date (%d %b %Y UTC)" 
set xlabel textcolor rgb "black" norotate
set xrange [ StartXaxis : EndXaxis ] noreverse nowriteback

# Y-axis labels and ranges
set ylabel "Pressure (hPa) N15 London UK" 
set ylabel textcolor rgb "dark-magenta" rotate
set yrange [ (PRESSURE_min - 5) : (PRESSURE_max + 5) ] noreverse nowriteback
#set yrange [ 960 : 1040 ] noreverse nowriteback

# Y2-axis label and ranges - for environment
#set y2label "Temperature (degC) N15 London UK" 
#set y2label textcolor rgb "grey30" rotate
#set y2range [ (TEMPERATURE_min - 2) : (TEMPERATURE_max + 2) ] noreverse nowriteback
#set y2range [*:*] noreverse nowriteback

# set STATS labels on graph
set label 1 sprintf("Mean pressure per 60 minutes: %0.1fhPa", PRESSURE_mean)
set label 1 at graph 0.02, 0.95 tc default
#set label 2 sprintf("Mean neutron counts per 60 minutes: %0.1f", NEUTRON_mean)
#set label 2 at graph 0.02, 0.90 tc default


# Plot command 
# for last month
GraphTitle = GraphTitle3
set key title GraphTitle
set output pathPlot3

plot FileData using 1:6 linetype 1 linewidth 1 linecolor rgb "dark-magenta" notitle "Pressure variation" with lines#, \
     #FileData using 1:5 linetype 1 linewidth 1 linecolor rgb "grey30" axes x1y2 notitle "Temp variation" with lines

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# setting output path to include data stamp

# Path to directory to store file
pathPlot = "/home/pi/UKRAA_PicoMuon/temp/ACM0_month_weather_plot"

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