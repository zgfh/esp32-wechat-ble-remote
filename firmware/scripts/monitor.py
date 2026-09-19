"""Stream serial logs; only restart MicroPython with --reset. Ctrl+C exits locally."""
import argparse
import datetime
import time
from pathlib import Path
import serial
from serial.tools import list_ports

parser = argparse.ArgumentParser()
parser.add_argument('--port')
mode = parser.add_mutually_exclusive_group()
mode.add_argument('--reset', action='store_true', help='Restart the app before monitoring (disconnects BLE)')
mode.add_argument('--no-reset', action='store_true', help='Listen only (the default)')
args = parser.parse_args()
ports = [p.device for p in list_ports.comports() if p.vid in (0x303A, 0x1A86, 0x10C4) and p.device.startswith('/dev/cu.')]
if not args.port and len(ports) != 1:
    parser.error('Cannot select one ESP32/USB-UART port; pass --port /dev/cu.usbmodem...')
port = args.port or ports[0]
log_dir = Path(__file__).resolve().parents[2] / 'simulation-logs'
log_dir.mkdir(exist_ok=True)
log_path = log_dir / ('esp32-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.log')
print('Port:', port, '\nLog:', log_path, '\nCtrl+C exits the monitor; the ESP32 keeps running.', flush=True)
try:
    with serial.Serial(port, 115200, timeout=0.3) as uart, log_path.open('a') as log:
        if args.reset:
            print("Restart requested: the following KeyboardInterrupt is expected; wait for BLE ready.", flush=True)
            uart.write(b'\r\x03\x03')
            time.sleep(0.15)
            uart.write(b'\x02\x04')  # friendly REPL, then soft reset
        else:
            print('Listening only: no restart commands sent. Existing startup logs are not replayed.', flush=True)
        while True:
            data = uart.readline()
            if data:
                line = datetime.datetime.now().strftime('[%H:%M:%S] ') + data.decode(errors='replace').rstrip()
                print(line, flush=True)
                log.write(line + '\n'); log.flush()
except KeyboardInterrupt:
    print('\nMonitor closed; ESP32 continues running.')
except serial.SerialException as error:
    raise SystemExit('Serial unavailable: ' + str(error))
