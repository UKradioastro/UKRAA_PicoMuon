# imports
import datetime as dt
import serial
import os

# main
def main():
    # set up usb serial variables
    ser = serial.Serial(port = '/dev/ttyACM0',
                        baudrate = 115200,
                        bytesize = serial.EIGHTBITS,
                        parity = serial.PARITY_NONE,
                        stopbits = serial.STOPBITS_ONE)
       
    for line in ser:
        # path for data storage
        path = '/home/pi/UKRAA_PicoMuon/data/raw/ACM0/'\
                + dt.datetime.strftime(dt.datetime.now(dt.timezone.utc), '%Y')\
                + '/'\
                + dt.datetime.strftime(dt.datetime.now(dt.timezone.utc), '%Y-%m')
        
        # check if the specific path exists
        pathExists = os.path.exists(path)
        if not pathExists:
            # create directory structure
            os.makedirs(path)

        # output file to write data to
        outfile = open('/home/pi/UKRAA_PicoMuon/data/raw/ACM0/'
                    + dt.datetime.strftime(dt.datetime.now(dt.timezone.utc), '%Y')
                    + '/'
                    + dt.datetime.strftime(dt.datetime.now(dt.timezone.utc), '%Y-%m')
                    + '/'
                    + dt.datetime.strftime(dt.datetime.now(dt.timezone.utc), '%Y-%m-%d')
                    + '.txt', 'a')
        
        # if data, write to file
        if line:
            timetowrite = (dt.datetime.strftime(dt.datetime.now(dt.timezone.utc), '%Y-%m-%d')
                        + " "
                        + dt.datetime.strftime(dt.datetime.now(dt.timezone.utc), '%H:%M:%S.%f'))
            texttowrite = (line.decode('utf-8', 'ignore').strip())

            print(timetowrite
                + ','
                + texttowrite
                , file = outfile)
        
                        
if __name__ == "__main__":
    main()