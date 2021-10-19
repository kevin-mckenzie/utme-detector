import time
import random
import busio
import digitalio
import board
import RPi.GPIO as GPIO
from sps30 import SPS30
from scd30_i2c import SCD30
from time import sleep
from PIL import Image, ImageFont, ImageDraw
from adafruit_rgb_display.rgb import color565
from adafruit_rgb_display import ili9341
import subprocess
import adafruit_sgp30

sleep(1)
i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
sgp = adafruit_sgp30.Adafruit_SGP30(i2c)
sps = SPS30(1)
scd = SCD30()

GPIO.setmode(GPIO.BCM)
GPIO.setup(18,GPIO.OUT)
GPIO.setmode(GPIO.BCM)
GPIO.setup(14,GPIO.OUT)
# Configuratoin for CS and DC pins (these are FeatherWing defaults on M0/M4):
cs_pin = digitalio.DigitalInOut(board.D8)
dc_pin = digitalio.DigitalInOut(board.D25)
reset_pin = digitalio.DigitalInOut(board.D24)
# Config for display baudrate (default max is 24mhz):
BAUDRATE = 24000000

# Setup SPI bus using hardware SPI:
spi = busio.SPI(clock=board.SCLK, MOSI=board.MOSI, MISO=board.MISO)

# Create the ILI9341 display:
display = ili9341.ILI9341(spi, cs=cs_pin, dc=dc_pin, rst = reset_pin, baudrate=BAUDRATE)
sps.start_measurement()
sgp.iaq_init()
sleep(1)
# Main loop:
for i in range(100):
    time.sleep(2)
    GPIO.output(18,GPIO.HIGH)
    #GPIO.output(14,GPIO.HIGH)
    titties = Image.open('white.jpg')
    titties = titties.resize((240,320), Image.ANTIALIAS)
    # Fill the screen red, green, blue, then black:
    # Clear the screen a random color
    draw = ImageDraw.Draw(titties)
    # font = ImageFont.truetype(<font-file>, <font-size>)
    font = ImageFont.truetype("sans-serif.ttf", 12)
    sps.read_measured_values()
    m_time = str(subprocess.check_output(['sudo', 'hwclock', '-r']))
    draw.text((0, 10),m_time, fill = (255,0,0,255), font=font, color = 'black')
    if scd.get_data_ready():
        m = scd.read_measurement()
        if m is not None:
            scd_read = f"CO2: {m[0]:.2f}ppm, temp: {m[1]:.2f}'C, rh: {m[2]:.2f}%"
            draw.text((0, 50),scd_read, fill = (255,0,0,255), font=font)
    if sps.dict_values['pm2p5'] is not None:
        sps_read = "PM2.5 Value in µg/m3: " + str(sps.dict_values['pm2p5'])
        draw.text((0, 75),sps_read, fill = (255,0,0,255), font=font)
    sgp_read = "eCO2 = %d ppm \t TVOC = %d ppb" % (sgp.eCO2, sgp.TVOC)
    draw.text((0, 100),sgp_read, fill = (255,0,0,255), font=font)
    # draw.text((x, y),"Sample Text",(r,g,b))
    display.image(titties)
    time.sleep(2)
    GPIO.output(18,GPIO.LOW)
    GPIO.output(14,GPIO.LOW)
    time.sleep(1)