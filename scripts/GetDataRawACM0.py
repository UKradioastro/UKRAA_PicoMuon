# imports
from datetime import datetime, timezone
import serial
from picomuon_common import build_raw_day_path, get_base_path, open_raw_file

# main
def main():
    base_path = get_base_path()

    # set up usb serial variables
    ser = serial.Serial(port = '/dev/ttyACM0',
                        baudrate = 115200,
                        bytesize = serial.EIGHTBITS,
                        parity = serial.PARITY_NONE,
                        stopbits = serial.STOPBITS_ONE)
       
    for line in ser:
        # if data write to file
        if line:
            now = datetime.now(timezone.utc)
            timetowrite = now.strftime('%Y-%m-%d %H:%M:%S.%f')
            texttowrite = (line.decode('utf-8', 'ignore').strip())
            with open_raw_file(build_raw_day_path(base_path, now, "ACM0")) as outfile:
                print(timetowrite + ',' + texttowrite, file=outfile)
        
                        
if __name__ == "__main__":
    main()