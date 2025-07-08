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
print "PlotDataFreqACM0.gp         : "\
    .system("date +'%Y/%M/%d %H:%M:%S'")\
    ." : Started ACM0 frequency plot for "\
    .system("date -d yesterday +'%Y-%m-%d'")

# Set up data paths
pathData = "/home/pi/UKRAA_PicoMuon/data/processed/cpm/ACM0"

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
is_missing = system("/home/pi/UKRAA_PicoMuon/scripts/ismissing.sh ".FileData)
if (is_missing == 1) { print "PlotDataFreqACM0.gp         : ".system("date +'%Y/%M/%d %H:%M:%S'").": ACM0 frequency data file missing, so..."; 
    print "PlotDataFreqACM0.gp         : "\
        .system("date +'%Y/%M/%d %H:%M:%S'")\
        ." : **FAILED** to complete ACM0 frequency plot for "\
        .system("date -d yesterday +'%Y-%m-%d'")
    exit
}

# FileData exists - good to continue...

# setting output path to include data stamp
# top detector
pathPlot1 = "/home/pi/UKRAA_PicoMuon/plots/freq/ACM0/".date."_Freq_T_plot.png"
# bottom detector
pathPlot2 = "/home/pi/UKRAA_PicoMuon/plots/freq/ACM0/".date."_Freq_B_plot.png"
# muons detected
pathPlot3 = "/home/pi/UKRAA_PicoMuon/plots/freq/ACM0/".date."_Freq_M_plot.png"


# Set separator to ","
set datafile separator ","

# Title for graph
# top detector
GraphTitle1 = "Frequency of top SiPM counts per minute data for ".system("date -d yesterday +'%A %d %B %Y'")."\n Graph is updated every day at 9.30am \n"
# bottom detector
GraphTitle2 = "Frequency of bottom SiPM counts per minute data for ".system("date -d yesterday +'%A %d %B %Y'")."\n Graph is updated every day at 9.30am \n"
# muons detected
GraphTitle3 = "Frequency of muon counts per minute data for ".system("date -d yesterday +'%A %d %B %Y'")."\n Graph is updated every day at 9.30am \n"

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
set xlabel "Events counts per minute (cpm)" 
set xlabel textcolor rgb "#000000" norotate
set xrange [0.0:*] noreverse nowriteback

# Y-axis labels and ranges
set ylabel "Frequency of events counts per minute" 
set ylabel textcolor rgb "#A020F0" rotate
set yrange [0.0:*] noreverse nowriteback

#set key off
set border 3

# Add a vertical dotted line at x=0 to show centre (mean) of distribution.
set yzeroaxis

# Each bar is half the (visual) width of its x-range.
set boxwidth 0.8 absolute
set style fill solid 1.0 noborder

bin_width = 0.1;

bin_number(x) = floor(x/bin_width)

rounded(x) = bin_width * ( bin_number(x) + 0.0 )

# Plot command # top detector
set output pathPlot1
GraphTitle = GraphTitle1
set key title GraphTitle
plot FileData using (rounded($2)):(1) smooth frequency with boxes linecolor "#0000FF" title "Frequency of events cpm for top detector"

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# Path to directory to store file
pathPlot = "/home/pi/UKRAA_PicoMuon/temp/ACM0_T-Freq"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# Plot command # bottom detector
set output pathPlot2
GraphTitle = GraphTitle2
set key title GraphTitle
plot FileData using (rounded($3)):(1) smooth frequency with boxes linecolor "#FF0000" title "Frequency of events cpm for bottom detector"

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# Path to directory to store file
pathPlot = "/home/pi/UKRAA_PicoMuon/temp/ACM0_B-Freq"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# Plot command # muon detector
set output pathPlot3
GraphTitle = GraphTitle3
set key title GraphTitle
plot FileData using (rounded($4)):(1) smooth frequency with boxes linecolor "#00FF00" title "Frequency of events cpm for muons"

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# Path to directory to store file
pathPlot = "/home/pi/UKRAA_PicoMuon/temp/ACM0_C-Freq"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# print to log file
print "PlotDataFreqACM0.gp         : "\
    .system("date +'%Y/%M/%d %H:%M:%S'")\
    ." : Completed ACM0 frequency plot for "\
    .system("date -d yesterday +'%Y-%m-%d'")

# This is important because it closes our output file.
set output

# EOF