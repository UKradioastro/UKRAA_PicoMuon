# imports
from datetime import datetime, timezone
import serial
from picomuon_common import build_raw_day_path, get_base_path, open_raw_file
from picomuon_common import log_error
from picomuon_metadata import RawEventWriter
from GetDataRaw import parse_and_validate_line
from picomuon_detectors import select_detector

# main
def main():
    base_path = get_base_path()
    select_detector(base_path, None)
    writer = RawEventWriter(base_path)

    # set up usb serial variables
    ser = serial.Serial(port = '/dev/ttyACM0',
                        baudrate = 115200,
                        bytesize = serial.EIGHTBITS,
                        parity = serial.PARITY_NONE,
                        stopbits = serial.STOPBITS_ONE,
                        exclusive = True)
       
    for line in ser:
        # if data write to file
        if line:
            now = datetime.now(timezone.utc)
            timetowrite = now.strftime('%Y-%m-%d %H:%M:%S.%f')
            texttowrite = (line.decode('utf-8', 'ignore').strip())
            if parse_and_validate_line(texttowrite) is None:
                log_error("GetDataRawACM0.py", f"Malformed raw row rejected: {texttowrite[:80]!r}")
                continue
            with open_raw_file(build_raw_day_path(base_path, now, "ACM0")) as outfile:
                writer.write(outfile, timetowrite, texttowrite)
        
                        
if __name__ == "__main__":
    main()