#!/usr/bin/env python3

#imports
import datetime as dt
import csv
import os
import shutil

# print message to log file to say started
print('ProcessData90DaysACM0.py    :',
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
      ': Started ACM0 90 days % deviation data processing, from',
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(90), '%Y-%m-%d'),
      'to',
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))


# Set path for data file structure

# raw data file source
for i in range(1, 91):
    globals()['RawDataFile%s' % i] = '$HOME/UKRAA_PicoMuon/data/processed/day/ACM0/' \
                                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(i), '%Y') \
                                     + '/' \
                                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(i), '%Y-%m') \
                                     + '/' \
                                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(i), '%Y-%m-%d') \
                                     + '.txt'
 

# Set file headers for data file structure
ThreeMonthFieldNames = ['DateTime',
                        'Position_T',
                        'Position_B',
                        'Position_M',
                        'temperature',
                        'pressure',
                        'neutrons']


# create 90 days worth of data
ThreeMonthPath = '$HOME/UKRAA_PicoMuon/data/processed/3month/ACM0/' \
                + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
                + "/" \
                + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m')

# check if the specific path exists
pathExists = os.path.exists(ThreeMonthPath)
if not pathExists:
    # create directory structure
    os.makedirs(ThreeMonthPath)
    print('ProcessData90DaysACM0.py    :',
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
          ': New ACM0 3month directory created :',
          ThreeMonthPath)


# 90 days data file name
ThreeMonthDataFile = '$HOME/UKRAA_PicoMuon/data/processed/3month/ACM0/' \
               + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
               + "/" \
               + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m') \
               + "/temp.txt"

# merge day data to make 90 days data file
if os.path.exists(RawDataFile90):
    with open(ThreeMonthDataFile,'wb') as wfd:
        for f in [RawDataFile90,RawDataFile89,RawDataFile88,RawDataFile87,RawDataFile86,
                  RawDataFile85,RawDataFile84,RawDataFile83,RawDataFile82,RawDataFile81,
                  RawDataFile80,RawDataFile79,RawDataFile78,RawDataFile77,RawDataFile76,
                  RawDataFile75,RawDataFile74,RawDataFile73,RawDataFile72,RawDataFile71,
                  RawDataFile70,RawDataFile69,RawDataFile68,RawDataFile67,RawDataFile66,
                  RawDataFile65,RawDataFile64,RawDataFile63,RawDataFile62,RawDataFile61,
                  RawDataFile60,RawDataFile59,RawDataFile58,RawDataFile57,RawDataFile56,
                  RawDataFile55,RawDataFile54,RawDataFile53,RawDataFile52,RawDataFile51,
                  RawDataFile50,RawDataFile49,RawDataFile48,RawDataFile47,RawDataFile46,
                  RawDataFile45,RawDataFile44,RawDataFile43,RawDataFile42,RawDataFile41,
                  RawDataFile40,RawDataFile39,RawDataFile38,RawDataFile37,RawDataFile36,
                  RawDataFile35,RawDataFile34,RawDataFile33,RawDataFile32,RawDataFile31,
                  RawDataFile30,RawDataFile29,RawDataFile28,RawDataFile27,RawDataFile26,
                  RawDataFile25,RawDataFile24,RawDataFile23,RawDataFile22,RawDataFile21,
                  RawDataFile20,RawDataFile19,RawDataFile18,RawDataFile17,RawDataFile16,
                  RawDataFile15,RawDataFile14,RawDataFile13,RawDataFile12,RawDataFile11,
                  RawDataFile10,RawDataFile9,RawDataFile8,RawDataFile7,RawDataFile6,
                  RawDataFile5,RawDataFile4,RawDataFile3,RawDataFile2,RawDataFile1]:
            with open(f,'rb') as fd:
                shutil.copyfileobj(fd, wfd)

else:
    print('ProcessData90DaysACM0.py    :',
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
          ': Not enough ACM0 day files are available yet to process 90 days % deviation data...')
    print('ProcessData90DaysACM0.py    :',
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
          ': **FAILED** to process ACM0 90 days % deviation data, from',
          dt.datetime.strftime(dt.datetime.now() - dt.timedelta(90), '%Y-%m-%d'),
          'to',
          dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))
    exit()
  
# Processed data path
ProcessedPath = '$HOME/UKRAA_PicoMuon/data/processed/3month/ACM0/'\
                + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
                + "/" \
                + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m')

# check if the specific path exists
pathExists = os.path.exists(ProcessedPath)
if not pathExists:
    # create directory structure
    os.makedirs(ProcessedPath)
    print('ProcessData90DaysACM0.py    :',
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
          ': New ACM0 3month directory created :',
          ProcessedPath)

# Processed data file name
ProcessedDataFile = "$HOME/UKRAA_PicoMuon/data/processed/3month/ACM0/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
                     + "/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m') \
                     + "/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d') \
                     + ".txt"

# =============================================================================
# Main program

StartTime_str = dt.datetime.strftime(dt.datetime.now() - dt.timedelta(90), '%Y-%m-%d') \
                + ' 00:00:00.000000'

StartTime_datetime = dt.datetime.strptime(StartTime_str, '%Y-%m-%d %H:%M:%S.%f')

EndTime_str = dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d') \
              + ' 23:59:59.999999'

EndTime_datetime = dt.datetime.strptime(EndTime_str, '%Y-%m-%d %H:%M:%S.%f')

# define what the time change will be
minute = dt.timedelta(
    days         =  0,
    seconds      =  0,
    microseconds =  0,
    milliseconds =  0,
    minutes      =  0,
    hours        =  24,
    weeks        =  0)

# set up variable to use in loop
ProcessedTime = StartTime_datetime - minute

# number of 24 hours in 90 days
n = 90

# open file to store data in and append to end
ProcessedData = open(file=ProcessedDataFile,
                     mode='a',
                     encoding='UTF-8')

for i in range(1, n + 1):
    # add a minute to each time value from 00:00:00 to 23:59:00
    ProcessedTime = ProcessedTime + minute
    
    StartBinTime = ProcessedTime

    EndBinTime = StartBinTime + minute

    # using csv.DictReader
    ThreeMonthFile = open(file=ThreeMonthDataFile,
                     mode='r',
                     encoding='UTF-8')
    
    ThreeMonthCSV_reader = csv.DictReader(ThreeMonthFile,
                                          ThreeMonthFieldNames)

    # set counters to zero (remember 'NaN' is a float)
    count_T     = 0.0
    count_B     = 0.0
    count_M     = 0.0
    temperature = 0.0
    pressure    = 0.0
    count_N     = 0.0

    for ThreeMonthLine in ThreeMonthCSV_reader:
        # try to get raw data after start StartBinTime
        # convert string to dt.datetime.datetime format
        ThreeMonthDatetime = dt.datetime.strptime(ThreeMonthLine['DateTime'], '%Y-%m-%d %H:%M:%S')
        
        # search file for data between two time points
        if (ThreeMonthDatetime >= StartBinTime) and (ThreeMonthDatetime < EndBinTime):
            # increase relevant counter
            count_T = count_T + float(ThreeMonthLine['Position_T'])
            count_B = count_B + float(ThreeMonthLine['Position_B'])
            count_M = count_M + float(ThreeMonthLine['Position_M'])
            temperature = temperature + float(ThreeMonthLine['temperature'])
            pressure = pressure + float(ThreeMonthLine['pressure'])
            count_N = count_N + float(ThreeMonthLine['neutrons'])

    # close open MonthFile
    ThreeMonthFile.close()

    # no need for 'nan' as already included in day data
    # check if there is some top counts data
    if (count_T != 0.0):
        ProcessedCPM_T = '{:.0f}'.format(count_T)
    else:
        ProcessedCPM_T = float('nan')
    # check if there is some bottom counts data
    if (count_B != 0.0):
        ProcessedCPM_B = '{:.0f}'.format(count_B)
    else:
        ProcessedCPM_B = float('nan')
    # check if there is some coincidence counts data
    if (count_M != 0.0):
        ProcessedCPM_M = '{:.0f}'.format(count_M)
    else:
        ProcessedCPM_M = float('nan')

    # check if there is some count data
    if ((count_T + count_B + count_M) != 0):
        ProcessedTemp  = '{:.1f}'.format(temperature / (12.0 * 24.0))
        ProcessedPres  = '{:.1f}'.format(pressure / (12.0 * 24.0))
    else:
        ProcessedTemp = float('nan')
        ProcessedPres = float('nan')

    # check if there is some neutron counts data
    if (count_N > (400.0 * (12.0 * 24.0))):
        ProcessedCPM_N = '{:.3f}'.format(count_N)
    else:
        ProcessedCPM_N = float('nan')

    # write to file
    ProcessedData.write(str(ProcessedTime))          # Data time date
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_T))         # Top detector count over 24 hours
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_B))         # Bottom detector count over 24 hours
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_M))         # Muon count over 24 hours
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedTemp))          # Detector temperature over 24 hours
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedPres))          # Detector pressure over 24 hours
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_N))         # Neutron count over 24 hours
    ProcessedData.write("\n")                        # new line

# close open ProcessedData file
ProcessedData.close()

# =============================================================================
# Message to log file at end of program

# print message to log file to say completed
print('ProcessData90DaysACM0.py    :',
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
      ': Completed ACM0 90 days % deviation data processing, from',
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(90), '%Y-%m-%d'),
      'to',
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))

# =============================================================================
# END of program