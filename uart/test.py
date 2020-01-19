from datetime import datetime
import serial

ser = serial.Serial('/dev/ttyUSB1', 115200)

while True:
  print(datetime.now().strftime('%H:%M:%S.%f'), ser.read())