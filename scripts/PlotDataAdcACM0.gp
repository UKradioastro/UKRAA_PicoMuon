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
print "PlotDataAdcACM0.gp          : "\
    .system("date +'%Y-%m-%d %H:%M:%S'")\
    ." : Started ACM0 adc plot for "\
    .system("date -d yesterday +'%Y-%m-%d'")

# Set up data paths
pathData = "/home/$USER/UKRAA_PicoMuon/data/processed/adc/ACM0"

# Year folder
YearFolder = "/".system("date -d yesterday +'%Y'")

# YearMonth folder
YearMonthFolder = "/".system("date -d yesterday +'%Y-%m'")

# YearMonthDay file
YmdFile = "/".system("date -d yesterday +'%Y-%m-%d'").".txt"

# date to be processed
date = system("date -d yesterday +'%Y-%m-%d'")

# Path to each data file for graphing
FileData = pathData.YearFolder.YearMonthFolder.YmdFile

# check if FileData exists - 0=exists, 1=doesn't exist, if doesn't exist then exit, with message
is_missing = system("/home/$USER/UKRAA_PicoMuon/scripts/ismissing.sh ".FileData)
if (is_missing == 1) {print "PlotDataAdcACM0.gp          : ".system("date +'%Y-%m-%d %H:%M:%S'")." : ACM0 adc data file missing, so..."; 
    print "PlotDataAdcACM0.gp          : "\
        .system("date +'%Y-%m-%d %H:%M:%S'")\
        ." : **FAILED** to complete ACM0 adc plot for "\
        .system("date -d yesterday +'%Y-%m-%d'")
    exit
}

# FileData exists - good to continue...

# setting output path to include data stamp
# top detector
pathPlot1 = "/home/$USER/UKRAA_PicoMuon/plots/adc/ACM0/".date."_ADC_T_plot.png"
# bottom detector
pathPlot2 = "/home/$USER/UKRAA_PicoMuon/plots/adc/ACM0/".date."_ADC_B_plot.png"
# muons detected
pathPlot3 = "/home/$USER/UKRAA_PicoMuon/plots/adc/ACM0/".date."_ADC_M_plot.png"

# Set separator to ","
set datafile separator ","

# Title for graph
# top detector
GraphTitle1 = "Frequency of top detector adc values for ".system("date -d yesterday +'%A %d %B %Y'")."\n Graph is updated every day at 9.30am \n"
# bottom detector
GraphTitle2 = "Frequency of top detector adc values for ".system("date -d yesterday +'%A %d %B %Y'")."\n Graph is updated every day at 9.30am \n"
# muons detected
GraphTitle3 = "Frequency of muon detected adc values for ".system("date -d yesterday +'%A %d %B %Y'")."\n Graph is updated every day at 9.30am \n"

# Set format types
set format x "%.1f"
set format y "%.1f" 

# Set grid format
set grid xtics nomxtics ytics nomytics noztics nomztics nortics nomrtics \
 nox2tics nomx2tics noy2tics nomy2tics nocbtics nomcbtics
set grid layerdefault linetype 0 linecolor 0 linewidth 0.500 dashtype solid,  linetype 0 linecolor 0 linewidth 0.500 dashtype solid

# Set Legend (Key) above plot
set key outside above center
set key samplen 10
set key nobox

# X-axis tics
set mxtics 2.0
set xtics border out scale 1,0.5 nomirror norotate  autojustify
set xtics norangelimit autofreq
set xtics textcolor rgb "#000000"

# Y-axis tics
set mytics 2.0
set ytics border out scale 1,0.5 nomirror norotate  autojustify
set ytics norangelimit autofreq
set ytics textcolor rgb "#A020F0"

# X-axis label and ranges
set xlabel "Event detector adc value" 
set xlabel textcolor rgb "#000000" norotate
set xrange [0.0:1024.0] noreverse nowriteback

# Y-axis labels and ranges
set ylabel "Frequency of event detector adc value" 
set ylabel textcolor rgb "#A020F0" rotate
set yrange [0.0:*] noreverse nowriteback

# Plot command # top detector
GraphTitle = GraphTitle1
set key title GraphTitle
set output pathPlot1
plot FileData using 1:2 linetype 1 linewidth 1 linecolor rgb "#0000FF" title "Frequency of events ADC in top SiPM" with lines

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# Path to directory to store file
pathPlot = "/home/$USER/UKRAA_PicoMuon/temp/ACM0_T-Adc"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# Plot command # bottom detector
set output pathPlot2
GraphTitle = GraphTitle2
set key title GraphTitle
plot FileData using 1:3 linetype 1 linewidth 1 linecolor rgb "#FF0000" title "Frequency of events ADC in bottom SiPM" with lines

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# Path to directory to store file
pathPlot = "/home/$USER/UKRAA_PicoMuon/temp/ACM0_B-Adc"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# Plot command # muon detector
set output pathPlot3
GraphTitle = GraphTitle3
set key title GraphTitle
plot FileData using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" title "Frequency of events ADC for muons detected" with lines

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# Path to directory to store file
pathPlot = "/home/$USER/UKRAA_PicoMuon/temp/ACM0_C-Adc"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# print to log file
print "PlotDataAdcACM0.gp          : "\
    .system("date +'%Y-%m-%d %H:%M:%S'")\
    ." : Completed ACM0 adc plot for "\
    .system("date -d yesterday +'%Y-%m-%d'")

# This is important because it closes our output file.
set output

# EOF