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
YearFolder01 = "/".system("date -d yesterday +'%Y'")
YearFolder02 = "/".system("date -d '2 days ago' +'%Y'")
YearFolder03 = "/".system("date -d '3 days ago' +'%Y'")
YearFolder04 = "/".system("date -d '4 days ago' +'%Y'")
YearFolder05 = "/".system("date -d '5 days ago' +'%Y'")
YearFolder06 = "/".system("date -d '6 days ago' +'%Y'")
YearFolder07 = "/".system("date -d '7 days ago' +'%Y'")
YearFolder08 = "/".system("date -d '8 days ago' +'%Y'")
YearFolder09 = "/".system("date -d '9 days ago' +'%Y'")
YearFolder10 = "/".system("date -d '10 days ago' +'%Y'")
YearFolder11 = "/".system("date -d '11 days ago' +'%Y'")
YearFolder12 = "/".system("date -d '12 days ago' +'%Y'")
YearFolder13 = "/".system("date -d '13 days ago' +'%Y'")
YearFolder14 = "/".system("date -d '14 days ago' +'%Y'")
YearFolder15 = "/".system("date -d '15 days ago' +'%Y'")
YearFolder16 = "/".system("date -d '16 days ago' +'%Y'")
YearFolder17 = "/".system("date -d '17 days ago' +'%Y'")
YearFolder18 = "/".system("date -d '18 days ago' +'%Y'")
YearFolder19 = "/".system("date -d '19 days ago' +'%Y'")
YearFolder20 = "/".system("date -d '20 days ago' +'%Y'")
YearFolder21 = "/".system("date -d '21 days ago' +'%Y'")
YearFolder22 = "/".system("date -d '22 days ago' +'%Y'")
YearFolder23 = "/".system("date -d '23 days ago' +'%Y'")
YearFolder24 = "/".system("date -d '24 days ago' +'%Y'")
YearFolder25 = "/".system("date -d '25 days ago' +'%Y'")
YearFolder26 = "/".system("date -d '26 days ago' +'%Y'")
YearFolder27 = "/".system("date -d '27 days ago' +'%Y'")
YearFolder28 = "/".system("date -d '28 days ago' +'%Y'")
YearFolder29 = "/".system("date -d '29 days ago' +'%Y'")
YearFolder30 = "/".system("date -d '30 days ago' +'%Y'")
YearFolder31 = "/".system("date -d '31 days ago' +'%Y'")

# YearMonth folder
YearMonthFolder01 = "/".system("date -d yesterday +'%Y-%m'")
YearMonthFolder02 = "/".system("date -d '2 days ago' +'%Y-%m'")
YearMonthFolder03 = "/".system("date -d '3 days ago' +'%Y-%m'")
YearMonthFolder04 = "/".system("date -d '4 days ago' +'%Y-%m'")
YearMonthFolder05 = "/".system("date -d '5 days ago' +'%Y-%m'")
YearMonthFolder06 = "/".system("date -d '6 days ago' +'%Y-%m'")
YearMonthFolder07 = "/".system("date -d '7 days ago' +'%Y-%m'")
YearMonthFolder08 = "/".system("date -d '8 days ago' +'%Y-%m'")
YearMonthFolder09 = "/".system("date -d '9 days ago' +'%Y-%m'")
YearMonthFolder10 = "/".system("date -d '10 days ago' +'%Y-%m'")
YearMonthFolder11 = "/".system("date -d '11 days ago' +'%Y-%m'")
YearMonthFolder12 = "/".system("date -d '12 days ago' +'%Y-%m'")
YearMonthFolder13 = "/".system("date -d '13 days ago' +'%Y-%m'")
YearMonthFolder14 = "/".system("date -d '14 days ago' +'%Y-%m'")
YearMonthFolder15 = "/".system("date -d '15 days ago' +'%Y-%m'")
YearMonthFolder16 = "/".system("date -d '16 days ago' +'%Y-%m'")
YearMonthFolder17 = "/".system("date -d '17 days ago' +'%Y-%m'")
YearMonthFolder18 = "/".system("date -d '18 days ago' +'%Y-%m'")
YearMonthFolder19 = "/".system("date -d '19 days ago' +'%Y-%m'")
YearMonthFolder20 = "/".system("date -d '20 days ago' +'%Y-%m'")
YearMonthFolder21 = "/".system("date -d '21 days ago' +'%Y-%m'")
YearMonthFolder22 = "/".system("date -d '22 days ago' +'%Y-%m'")
YearMonthFolder23 = "/".system("date -d '23 days ago' +'%Y-%m'")
YearMonthFolder24 = "/".system("date -d '24 days ago' +'%Y-%m'")
YearMonthFolder25 = "/".system("date -d '25 days ago' +'%Y-%m'")
YearMonthFolder26 = "/".system("date -d '26 days ago' +'%Y-%m'")
YearMonthFolder27 = "/".system("date -d '27 days ago' +'%Y-%m'")
YearMonthFolder28 = "/".system("date -d '28 days ago' +'%Y-%m'")
YearMonthFolder29 = "/".system("date -d '29 days ago' +'%Y-%m'")
YearMonthFolder30 = "/".system("date -d '30 days ago' +'%Y-%m'")
YearMonthFolder31 = "/".system("date -d '31 days ago' +'%Y-%m'")

# YearMonthDay file
YmdFile01 = "/".system("date -d yesterday +'%Y-%m-%d'").".txt"
YmdFile02 = "/".system("date -d '2 days ago' +'%Y-%m-%d'").".txt"
YmdFile03 = "/".system("date -d '3 days ago' +'%Y-%m-%d'").".txt"
YmdFile04 = "/".system("date -d '4 days ago' +'%Y-%m-%d'").".txt"
YmdFile05 = "/".system("date -d '5 days ago' +'%Y-%m-%d'").".txt"
YmdFile06 = "/".system("date -d '6 days ago' +'%Y-%m-%d'").".txt"
YmdFile07 = "/".system("date -d '7 days ago' +'%Y-%m-%d'").".txt"
YmdFile08 = "/".system("date -d '8 days ago' +'%Y-%m-%d'").".txt"
YmdFile09 = "/".system("date -d '9 days ago' +'%Y-%m-%d'").".txt"
YmdFile10 = "/".system("date -d '10 days ago' +'%Y-%m-%d'").".txt"
YmdFile11 = "/".system("date -d '11 days ago' +'%Y-%m-%d'").".txt"
YmdFile12 = "/".system("date -d '12 days ago' +'%Y-%m-%d'").".txt"
YmdFile13 = "/".system("date -d '13 days ago' +'%Y-%m-%d'").".txt"
YmdFile14 = "/".system("date -d '14 days ago' +'%Y-%m-%d'").".txt"
YmdFile15 = "/".system("date -d '15 days ago' +'%Y-%m-%d'").".txt"
YmdFile16 = "/".system("date -d '16 days ago' +'%Y-%m-%d'").".txt"
YmdFile17 = "/".system("date -d '17 days ago' +'%Y-%m-%d'").".txt"
YmdFile18 = "/".system("date -d '18 days ago' +'%Y-%m-%d'").".txt"
YmdFile19 = "/".system("date -d '19 days ago' +'%Y-%m-%d'").".txt"
YmdFile20 = "/".system("date -d '20 days ago' +'%Y-%m-%d'").".txt"
YmdFile21 = "/".system("date -d '21 days ago' +'%Y-%m-%d'").".txt"
YmdFile22 = "/".system("date -d '22 days ago' +'%Y-%m-%d'").".txt"
YmdFile23 = "/".system("date -d '23 days ago' +'%Y-%m-%d'").".txt"
YmdFile24 = "/".system("date -d '24 days ago' +'%Y-%m-%d'").".txt"
YmdFile25 = "/".system("date -d '25 days ago' +'%Y-%m-%d'").".txt"
YmdFile26 = "/".system("date -d '26 days ago' +'%Y-%m-%d'").".txt"
YmdFile27 = "/".system("date -d '27 days ago' +'%Y-%m-%d'").".txt"
YmdFile28 = "/".system("date -d '28 days ago' +'%Y-%m-%d'").".txt"
YmdFile29 = "/".system("date -d '29 days ago' +'%Y-%m-%d'").".txt"
YmdFile30 = "/".system("date -d '30 days ago' +'%Y-%m-%d'").".txt"
YmdFile31 = "/".system("date -d '31 days ago' +'%Y-%m-%d'").".txt"

# Path to each data file for graphing
FileData01        = pathData.YearFolder01.YearMonthFolder01.YmdFile01
FileData02        = pathData.YearFolder02.YearMonthFolder02.YmdFile02
FileData03        = pathData.YearFolder03.YearMonthFolder03.YmdFile03
FileData04        = pathData.YearFolder04.YearMonthFolder04.YmdFile04
FileData05        = pathData.YearFolder05.YearMonthFolder05.YmdFile05
FileData06        = pathData.YearFolder06.YearMonthFolder06.YmdFile06
FileData07        = pathData.YearFolder07.YearMonthFolder07.YmdFile07
FileData08        = pathData.YearFolder08.YearMonthFolder08.YmdFile08
FileData09        = pathData.YearFolder09.YearMonthFolder09.YmdFile09
FileData10        = pathData.YearFolder10.YearMonthFolder10.YmdFile10
FileData11        = pathData.YearFolder11.YearMonthFolder11.YmdFile11
FileData12        = pathData.YearFolder12.YearMonthFolder12.YmdFile12
FileData13        = pathData.YearFolder13.YearMonthFolder13.YmdFile13
FileData14        = pathData.YearFolder14.YearMonthFolder14.YmdFile14
FileData15        = pathData.YearFolder15.YearMonthFolder15.YmdFile15
FileData16        = pathData.YearFolder16.YearMonthFolder16.YmdFile16
FileData17        = pathData.YearFolder17.YearMonthFolder17.YmdFile17
FileData18        = pathData.YearFolder18.YearMonthFolder18.YmdFile18
FileData19        = pathData.YearFolder19.YearMonthFolder19.YmdFile19
FileData20        = pathData.YearFolder20.YearMonthFolder20.YmdFile20
FileData21        = pathData.YearFolder21.YearMonthFolder21.YmdFile21
FileData22        = pathData.YearFolder22.YearMonthFolder22.YmdFile22
FileData23        = pathData.YearFolder23.YearMonthFolder23.YmdFile23
FileData24        = pathData.YearFolder24.YearMonthFolder24.YmdFile24
FileData25        = pathData.YearFolder25.YearMonthFolder25.YmdFile25
FileData26        = pathData.YearFolder26.YearMonthFolder26.YmdFile26
FileData27        = pathData.YearFolder27.YearMonthFolder27.YmdFile27
FileData28        = pathData.YearFolder28.YearMonthFolder28.YmdFile28
FileData29        = pathData.YearFolder29.YearMonthFolder29.YmdFile29
FileData30        = pathData.YearFolder30.YearMonthFolder30.YmdFile30
FileData31        = pathData.YearFolder31.YearMonthFolder31.YmdFile31
FileEnvironment = pathEnvironment.YearFolder01.YearMonthFolder01.YmdFile01
FileNeutron01     = pathNeutron.YearFolder01.YearMonthFolder01.YmdFile01
FileNeutron02     = pathNeutron.YearFolder02.YearMonthFolder02.YmdFile02
FileNeutron03     = pathNeutron.YearFolder03.YearMonthFolder03.YmdFile03
FileNeutron04     = pathNeutron.YearFolder04.YearMonthFolder04.YmdFile04
FileNeutron05     = pathNeutron.YearFolder05.YearMonthFolder05.YmdFile05
FileNeutron06     = pathNeutron.YearFolder06.YearMonthFolder06.YmdFile06
FileNeutron07     = pathNeutron.YearFolder07.YearMonthFolder07.YmdFile07
FileNeutron08     = pathNeutron.YearFolder08.YearMonthFolder08.YmdFile08
FileNeutron09     = pathNeutron.YearFolder09.YearMonthFolder09.YmdFile09
FileNeutron10     = pathNeutron.YearFolder10.YearMonthFolder10.YmdFile10
FileNeutron11     = pathNeutron.YearFolder11.YearMonthFolder11.YmdFile11
FileNeutron12     = pathNeutron.YearFolder12.YearMonthFolder12.YmdFile12
FileNeutron13     = pathNeutron.YearFolder13.YearMonthFolder13.YmdFile13
FileNeutron14     = pathNeutron.YearFolder14.YearMonthFolder14.YmdFile14
FileNeutron15     = pathNeutron.YearFolder15.YearMonthFolder15.YmdFile15
FileNeutron16     = pathNeutron.YearFolder16.YearMonthFolder16.YmdFile16
FileNeutron17     = pathNeutron.YearFolder17.YearMonthFolder17.YmdFile17
FileNeutron18     = pathNeutron.YearFolder18.YearMonthFolder18.YmdFile18
FileNeutron19     = pathNeutron.YearFolder19.YearMonthFolder19.YmdFile19
FileNeutron20     = pathNeutron.YearFolder20.YearMonthFolder20.YmdFile20
FileNeutron21     = pathNeutron.YearFolder21.YearMonthFolder21.YmdFile21
FileNeutron22     = pathNeutron.YearFolder22.YearMonthFolder22.YmdFile22
FileNeutron23     = pathNeutron.YearFolder23.YearMonthFolder23.YmdFile23
FileNeutron24     = pathNeutron.YearFolder24.YearMonthFolder24.YmdFile24
FileNeutron25     = pathNeutron.YearFolder25.YearMonthFolder25.YmdFile25
FileNeutron26     = pathNeutron.YearFolder26.YearMonthFolder26.YmdFile26
FileNeutron27     = pathNeutron.YearFolder27.YearMonthFolder27.YmdFile27
FileNeutron28     = pathNeutron.YearFolder28.YearMonthFolder28.YmdFile28
FileNeutron29     = pathNeutron.YearFolder29.YearMonthFolder29.YmdFile29
FileNeutron30     = pathNeutron.YearFolder30.YearMonthFolder30.YmdFile30
FileNeutron31     = pathNeutron.YearFolder31.YearMonthFolder31.YmdFile31

# date to be processed
date = system("date -d yesterday +'%Y-%m-%d'")

# Start of X axis time
StartXaxis = system("date -d '-1 month' +'%Y-%m-%d'")." 00:00:00"

# End of X axis time
EndXaxis = system("date +'%Y-%m-%d'")." 00:00:00"

# setting output path to include data stamp
# Path to directory to store file
# muons detected
pathPlot3 = "/home/pi/UKRAA_muons/plots/cpm/ACM0/".date."_CPM_M_plot_month.png"

# set output path to Plot folder
#set output pathPlot

# Set separator to ","
set datafile separator ","

# Title for graph
# muons detected
GraphTitle3 = "Muon cpm data from ".system("date -d '-1 month' +'%A %d %B %Y'")." to ".system("date -d yesterday +'%A %d %B %Y'")."\n Graph is updated every day at 9.30am \n"

# Set data types
set xdata time

# Set format types
set format x "%d/%m" timedate
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
#set mxtics 1.0
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
set xlabel "Date (UTC)" 
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

# Plot command # muon detector
GraphTitle = GraphTitle3
set key title GraphTitle
set output pathPlot3
plot FileData01 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" title "Cpm of muon detected" with lines, \
     FileData02 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData03 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData04 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData05 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData06 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData07 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData08 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData09 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData10 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData11 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData12 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData13 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData14 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData15 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData16 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData17 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData18 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData19 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData20 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData21 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData22 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData23 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData24 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData25 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData26 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData27 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData28 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData29 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData30 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileData31 using 1:4 linetype 1 linewidth 1 linecolor rgb "#00FF00" notitle with lines, \
     FileNeutron01 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 title "Oulu neutron flux (cpm)" with lines, \
     FileNeutron02 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron03 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron04 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron05 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron06 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron07 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron08 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron09 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron10 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron11 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron12 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron13 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron14 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron15 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron16 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron17 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron18 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron19 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron20 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron21 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron22 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron23 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron24 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron25 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron26 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron27 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron28 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron29 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron30 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines, \
     FileNeutron31 using 1:5 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 notitle with lines
#     FileEnvironment using 1:6 linetype 1 linewidth 2 linecolor rgb "grey30" axes x1y2 title "Air temperature degC" with lines

# Replot to terminal and create .png image with data tag for future upload to web page
set terminal pngcairo enhanced font "DejaVuSansCondensed, 10" rounded size 640,540 

# setting output path to include data stamp

# Path to directory to store file
pathPlot = "/home/pi/UKRAA_muons/temp/ACM0_C-Cpm_month"

# set output path to Plot folder
set output pathPlot.".png"

# replot graph to Plot folder with added date tag
replot
# end replot

# This is important because it closes our output file.
set output

# EOF