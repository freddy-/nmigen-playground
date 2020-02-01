from datetime import datetime
import serial
import io

ser = serial.Serial('/dev/ttyUSB1', 115200)

while True:
  ser.write(b'c')
  print(datetime.now().strftime('%H:%M:%S.%d'), ser.read())