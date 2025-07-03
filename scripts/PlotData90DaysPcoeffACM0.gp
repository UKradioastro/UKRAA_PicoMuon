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

# Set print to <stdout>
set print "-"

# print to log file
print "PlotData90DaysPcoeffACM0.gp : "\
    .system("date +'%Y-%m-%d %H:%M:%S'")\
    ." : Started ACM0 90 days pressure coefficient plot from "\
    .system("date -d '90 days ago' +'%Y-%m-%d'")\
    ." to "\
    .system("date -d yesterday +'%Y-%m-%d'")

# Set up data paths
pathData        = "/home/pi/UKRAA_PicoMuon/data/processed/3month/ACM0"

# Year folder
YearFolder      = "/".system("date -d yesterday +'%Y'")

# YearMonth folder
YearMonthFolder = "/".system("date -d yesterday +'%Y-%m'")

# YearMonthDay file
YmdFile         = "/".system("date -d yesterday +'%Y-%m-%d'").".txt"

# Path to each data file for graphing
FileData        = pathData.YearFolder.YearMonthFolder.YmdFile

# check if FileData exists - 0=exists, 1=doesn't exist, if doesn't exist then exit, with message
is_missing = system("/home/pi/UKRAA_PicoMuon/scripts/ismissing.sh ".FileData)
if (is_missing == 1) {print "PlotData90DaysPcoeffACM0.gp : ".system("date +'%Y/%M/%d %H:%M:%S'")." : ACM0 3month data file missing, so..."; 
    print "PlotData90DaysPcoeffACM0.gp : "\
        .system("date +'%Y/%M/%d %H:%M:%S'")\
        ." : **FAILED** to complete ACM0 90 days pressure coefficient plot from "\
        .system("date -d '90 days ago' +'%Y-%m-%d'")\
        ." to "\
        .system("date -d yesterday +'%Y-%m-%d'")
    exit
}

# FileData exists - good to continue...

# Set separator to ","
set datafile separator ","

# undertake stats before setting timeformat and xdata
stats FileData using 4 output prefix "MUON" nooutput
stats FileData using 5 output prefix "TEMPERATURE" nooutput
stats FileData using 6 output prefix "PRESSURE" nooutput
stats FileData using 7 output prefix "NEUTRON" nooutput

# date to be processed
date = system("date -d yesterday +'%Y-%m-%d'")

# setting output path to include data stamp
# 90 days pressure coefficient data
pathPlot3 = "/home/pi/UKRAA_PicoMuon/plots/3month/ACM0/".date."_90_days_pressure_coefficient_plot.png"

# Title for graph
GraphTitle3 = "Pressure correction factor for the last 90 days.\n Graph is updated every day at 9.30am \n"

# Set format types
set format x "%.1f"
set format y "%.1f" 

# Set grid format
set grid xtics nomxtics ytics nomytics noztics nomztics nortics nomrtics \
 nox2tics nomx2tics noy2tics nomy2tics nocbtics nomcbtics
set grid layerdefault linetype 0 linecolor 0 linewidth 0.500 dashtype solid, \
                      linetype 0 linecolor 0 linewidth 0.500 dashtype solid

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
set xlabel "Pressure - mean pressure (hPa)" 
set xlabel textcolor rgb "black" norotate
set xrange [*:*] noreverse nowriteback

# Y-axis labels and ranges
set ylabel "Change of pressure/mean pressure (%)" 
set ylabel textcolor rgb "dark-violet" rotate
set yrange [*:*] noreverse nowriteback


# least square fit
set print "/home/pi/UKRAA_PicoMuon/data/environment/coefficient/".date."_90_days_pressure_coefficient.txt"            # Define a filename to save the values
c = 0
f(x) = a0*x + c
set fit nolog quiet
#set fit logfile "/home/pi/UKRAA_PicoMuon/data/environment/coefficient/".date."_pressure_coefficient.txt" quiet
fit f(x) FileData using ($6-PRESSURE_mean):((($4-MUON_mean)/MUON_mean)*100) via a0
print sprintf("%s,%0.6f,%0.6f,%4.2f", date, a0, a0_err, PRESSURE_mean)              # Print the gradient into file
unset print                          # Turn off the print

# set STATS labels on graph
set label 1 sprintf("Mean muon counts per 24 hours: %0.1f", MUON_mean)
set label 1 at graph 0.02, 0.95 tc default
set label 2 sprintf("Mean presure for 90 days: %0.1fhPa", PRESSURE_mean)
set label 2 at graph 0.02, 0.90 tc default
set label 3 sprintf("Barametric coefficient: %0.6f+/-%0.5f%", a0, a0_err)
set label 3 at graph 0.02, 0.85 tc default


# Plot command 
# for last month
GraphTitle = GraphTitle3
set key title GraphTitle
set output pathPlot3
plot FileData using ($6-PRESSURE_mean):((($4-MUON_mean)/MUON_mean)*100) with points pointsize 3 notitle, \
     f(x) with line title sprintf("Least square fit: f(x)=a0*x+b, a0=%g",a0)

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# setting output path to include data stamp

# Path to directory to store file
pathPlot = "/home/pi/UKRAA_PicoMuon/temp/ACM0_90_days_pressure_coefficient_plot"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# Set print to <stdout>
set print "-"

# print to log file
print "PlotData90DaysPcoeffACM0.gp : "\
    .system("date +'%Y-%m-%d %H:%M:%S'")\
    ." : Completed ACM0 90 days pressure coefficient plot from "\
    .system("date -d '90 days ago' +'%Y-%m-%d'")\
    ." to "\
    .system("date -d yesterday +'%Y-%m-%d'")

# This is important because it closes our output file.
set output

# EOF