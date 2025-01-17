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

# Clear gnuplot terminal
#clear

# Set terminal 
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# Set up data paths
pathData        = "/home/pi/UKRAA_muons/data/processed/cpm/ACM0"
pathEnvironment = "/home/pi/UKRAA_muons/data/environment"
pathNeutron     = "/home/pi/UKRAA_muons/data/neutrons"

# Year folder
YearFolder = "/".system("date -d yesterday +'%Y'")

# YearMonth folder
YearMonthFolder = "/".system("date -d yesterday +'%Y-%m'")

# YearMonthDay file
YmdFile = "/".system("date -d yesterday +'%Y-%m-%d'").".txt"

# Path to each data file for graphing
FileData        = pathData.YearFolder.YearMonthFolder.YmdFile
FileEnvironment = pathEnvironment.YearFolder.YearMonthFolder.YmdFile
FileNeutron     = pathNeutron.YearFolder.YearMonthFolder.YmdFile

# date to be processed
date = system("date -d yesterday +'%Y-%m-%d'")

# Start of X axis time
StartXaxis = system("date -d '-1 day' +'%Y-%m-%d'")." 00:00:00"

# End of X axis time
EndXaxis = system("date +'%Y-%m-%d'")." 00:00:00"

# Path to each data file for graphing
#FileMuon = "/home/pi/UKRAA_muons/data/".date."/".date."_processed_CPM.txt"

# setting output path to include data stamp
# Path to directory to store file
# top detector
pathPlot1 = "/home/pi/UKRAA_muons/plots/cpm/ACM0/".date."_CPM_T_plot.png"
# bottom detector
pathPlot2 = "/home/pi/UKRAA_muons/plots/cpm/ACM0/".date."_CPM_B_plot.png"
# muons detected
pathPlot3 = "/home/pi/UKRAA_muons/plots/cpm/ACM0/".date."_CPM_M_plot.png"

# set output path to Plot folder
#set output pathPlot

# Set separator to ","
set datafile separator ","

# Title for graph
# top detector
GraphTitle1 = "Top SiPM counts per minute data for ".system("date -d yesterday +'%A %d %B %Y'")."\n Graph is updated every day at 9.30am \n"
# bottom detector
GraphTitle2 = "Bottom SiPM counts per minute data for ".system("date -d yesterday +'%A %d %B %Y'")."\n Graph is updated every day at 9.30am \n"
# muons detected
GraphTitle3 = "Muon counts per minute data for ".system("date -d yesterday +'%A %d %B %Y'")."\n Graph is updated every day at 9.30am \n"

# Set data types
set xdata time

# Set format types
set format x "%H:%M" timedate
set format y "%.1f" 
set format y2 "%.1f" 
set timefmt "%Y-%m-%d %H:%M:%S"

# Set grid format
set grid xtics nomxtics ytics nomytics noztics nomztics nortics nomrtics \
 nox2tics nomx2tics noy2tics nomy2tics nocbtics nomcbtics
set grid layerdefault linetype 0 linecolor 0 linewidth 0.500 dashtype solid,  linetype 0 linecolor 0 linewidth 0.500 dashtype solid

# Set Legend (Key) above plot
set key outside above center
set key samplen 10
#set key title GraphTitle
set key nobox

# X-axis tics
set mxtics 2.0
set xtics border out scale 1,0.5 nomirror norotate  autojustify
set xtics norangelimit 7200
set xtics textcolor rgb "black"
set xtics font ",8"

# Y-axis tics
set mytics 2.0
set ytics border out scale 1,0.5 nomirror norotate  autojustify
set ytics norangelimit autofreq
set ytics textcolor rgb "dark-violet"

# Y2-axis tics
set my2tics 2.0
set y2tics border out scale 1,0.5 nomirror norotate  autojustify
set y2tics norangelimit autofreq
set y2tics textcolor rgb "black"

# X-axis label and ranges
set xlabel "Time (UTC)" 
set xlabel textcolor rgb "black" norotate
set xrange [ StartXaxis : EndXaxis ] noreverse nowriteback

# Y-axis labels and ranges
set ylabel "Radiation counts (cpm)" 
#set ylabel "Muon counts (cpm)" 
set ylabel textcolor rgb "dark-violet" rotate
set yrange [ 0.00000 : * ] noreverse nowriteback
#set yrange [ 0.00000 : 20.00000 ] noreverse nowriteback

# Y2-axis label and ranges - for environment
#set y2label "Temperature (degC)" 
#set y2label textcolor rgb "black" rotate
#set y2range [ -5.00000 : 40.00000 ] noreverse nowriteback

# Y2-axis label and ranges - for neutrons
set y2label "Neutron flux Oulu Finland (cpm)" 
set y2label textcolor rgb "black" rotate
set y2range [ 0.00000 : 200.00000 ] noreverse nowriteback

# Plot command # top detector
GraphTitle = GraphTitle1
set key title GraphTitle
set output pathPlot1
plot FileData using 1:2 linetype 1 linewidth 1 linecolor rgb "#0000FF" title "Cpm of events detected by top detector" with lines, \
     FileNeutron using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 title "Oulu neutron flux (cpm)" with lines
#     FileEnvironment using 1:6 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 title "Air temperature degC" with lines

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# setting output path to include data stamp

# Path to directory to store file
pathPlot = "/home/pi/UKRAA_muons/temp/ACM0_T-Cpm"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# Plot command # bottom detector
GraphTitle = GraphTitle2
set key title GraphTitle
set output pathPlot2
plot FileData using 1:3 linetype 1 linewidth 1 linecolor rgb "#FF0000" title "Cpm of events detected by bottom detector" with lines, \
     FileNeutron using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 title "Oulu neutron flux (cpm)" with lines
#     FileEnvironment using 1:6 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 title "Air temperature degC" with lines

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# setting output path to include data stamp

# Path to directory to store file
pathPlot = "/home/pi/UKRAA_muons/temp/ACM0_B-Cpm"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# Plot command # muon detector
GraphTitle = GraphTitle3
set key title GraphTitle
set output pathPlot3
plot FileData using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" title "Cpm of muon detected" with lines, \
     FileNeutron using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 title "Oulu neutron flux (cpm)" with lines
#     FileEnvironment using 1:6 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 title "Air temperature degC" with lines

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# setting output path to include data stamp

# Path to directory to store file
pathPlot = "/home/pi/UKRAA_muons/temp/ACM0_C-Cpm"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# print to log file
set print "-"
print "Completed CPM plot for ".system("date -d yesterday +'%Y-%m-%d'")." at ".system("date +'%H:%M:%S'")." on ".system("date +'%A %d %B %Y'")

# This is important because it closes our output file.
set output

# EOF