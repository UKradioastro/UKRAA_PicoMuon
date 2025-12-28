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
print "PlotDataWeekACM0.gp         : "\
    .system("date +'%Y-%m-%d %H:%M:%S'")\
    ." : Started ACM0 weeks % deviation plot from "\
    .system("date -d 'last week' +'%Y-%m-%d'")\
    ." to "\
    .system("date -d yesterday +'%Y-%m-%d'")

# Set up data paths
pathData        = "/home/$USER/UKRAA_PicoMuon/data/processed/week/ACM0"

# Year folder
YearFolder      = "/".system("date -d yesterday +'%Y'")

# YearMonth folder
YearMonthFolder = "/".system("date -d yesterday +'%Y-%m'")

# YearMonthDay file
YmdFile         = "/".system("date -d yesterday +'%Y-%m-%d'").".txt"

# Path to each data file for graphing
FileData        = pathData.YearFolder.YearMonthFolder.YmdFile

# check if FileData exists - 0=exists, 1=doesn't exist, if doesn't exist then exit, with message
is_missing = system("/home/$USER/UKRAA_PicoMuon/scripts/ismissing.sh ".FileData)
if (is_missing == 1) {print "PlotDataWeekACM0.gp         : ".system("date +'%Y-%m-%d %H:%M:%S'")." : ACM0 week data file missing, so..."; 
    print "PlotDataWeekACM0.gp         : "\
        .system("date +'%Y-%m-%d %H:%M:%S'")\
        ." : **FAILED** to complete ACM0 weeks % deviation plot from "\
        .system("date -d 'last week' +'%Y-%m-%d'")\
        ." to "\
        .system("date -d yesterday +'%Y-%m-%d'")
    exit
}

# FileData exists - good to continue...

# Set separator to ","
set datafile separator ","

# undertake stats before setting timeformat and xdata
stats FileData using 4 output prefix "MUON" nooutput
stats FileData using 7 output prefix "NEUTRON" nooutput

# date to be processed
date = system("date -d yesterday +'%Y-%m-%d'")

# Start of X axis time
StartXaxis = system("date -d 'last week' +'%Y-%m-%d'")." 00:00:00"

# End of X axis time
EndXaxis = system("date +'%Y-%m-%d'")." 00:00:00"

# setting output path to include data stamp
# week data
pathPlot3 = "/home/$USER/UKRAA_PicoMuon/plots/week/ACM0/".date."_week_plot.png"

# Title for graph
# muons detected
GraphTitle3 = "% change of muon and neutron count rate from mean count rate for the last 7 days.\n Graph is updated every day at 8.00am \n"

# Set data types
set xdata time

# Set format types
set format x "%a %d" timedate
set format y "%.1f" 
set format y2 "%.1f" 
set timefmt "%Y-%m-%d %H:%M:%S"

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

# Y2-axis tics
set my2tics 2.0
set y2tics border out scale 1,0.5 nomirror norotate  autojustify
set y2tics norangelimit autofreq
set y2tics textcolor rgb "black"

# X-axis label and ranges
set xlabel "Date (%a %d UTC)" 
set xlabel textcolor rgb "black" norotate
set xrange [ StartXaxis : EndXaxis ] noreverse nowriteback

# Y-axis labels and ranges
set ylabel "% change in muon flux" 
set ylabel textcolor rgb "dark-violet" rotate
set yrange [ (((MUON_min/MUON_mean)*100)-100)-5 : (((MUON_max/MUON_mean)*100)-100)+5 ] noreverse nowriteback

# Y2-axis label and ranges - for neutrons
set y2label "% change in neutron flux NMDB Oulu Finland" 
set y2label textcolor rgb "black" rotate
set y2range [ (((NEUTRON_min/NEUTRON_mean)*100)-100)-5 : (((NEUTRON_max/NEUTRON_mean)*100)-100)+5 ] noreverse nowriteback

# set STATS labels on graph
set label 1 sprintf("Mean muon counts per 10 minutes: %0.1f", MUON_mean)
set label 1 at graph 0.02, 0.95 tc default
set label 2 sprintf("Mean neutron counts per 10 minutes: %0.1f", NEUTRON_mean)
set label 2 at graph 0.02, 0.90 tc default


# Plot command 
# for 7 days
GraphTitle = GraphTitle3
set key title GraphTitle
set output pathPlot3
plot FileData using 1:(((($4/MUON_mean)*100)-100)) linetype 1 linewidth 1 linecolor rgb "dark-violet" notitle "5-min averages of muons detected" with lines, \
     FileData using 1:(((($7/NEUTRON_mean)*100)-100)) linetype 1 linewidth 1 linecolor rgb "black" axes x1y2 notitle "Oulu neutron flux (cpm)" with lines

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# Path to directory to store file
pathPlot = "/home/$USER/UKRAA_PicoMuon/temp/ACM0_week_plot"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# print to log file
print "PlotDataWeekACM0.gp         : "\
    .system("date +'%Y-%m-%d %H:%M:%S'")\
    ." : Completed ACM0 weeks % deviation day plot from "\
    .system("date -d 'last week' +'%Y-%m-%d'")\
    ." to "\
    .system("date -d yesterday +'%Y-%m-%d'")

# This is important because it closes our output file.
set output

# EOF