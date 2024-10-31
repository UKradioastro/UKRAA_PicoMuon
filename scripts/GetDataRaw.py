# imports
from datetime import datetime, timezone
import serial

# main
def main():
    ser = serial.Serial(port = '/dev/ttyACM0',
                        baudrate = 115200,
                        bytesize = serial.EIGHTBITS,
                        parity = serial.PARITY_NONE,
                        stopbits = serial.STOPBITS_ONE)
       
    for line in ser:
        outfile = open('/home/pi/UKRAA_muons/data/raw/'
                    + datetime.strftime(datetime.now(timezone.utc), '%Y')
                    + '/'
                    + datetime.strftime(datetime.now(timezone.utc), '%Y-%m')
                    + '/'
                    + datetime.strftime(datetime.now(timezone.utc), '%Y-%m-%d')
                    + '.txt', 'a')
        if line:
            timetowrite = (datetime.strftime(datetime.now(timezone.utc), '%Y-%m-%d')
                        + " "
                        + datetime.strftime(datetime.now(timezone.utc), '%H:%M:%S.%f'))
            texttowrite = (line.decode('utf-8', 'ignore').strip())

            print(timetowrite
                + ','
                + texttowrite
                , file = outfile)
        
                        
if __name__ == "__main__":
    main()