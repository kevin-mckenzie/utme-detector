import time, busio, digitalio, board, subprocess, adafruit_sgp30, os, csv
from PIL import Image, ImageFont, ImageDraw, ImageOps
import RPi.GPIO as GPIO
from sps30 import SPS30
from scd30_i2c import SCD30
from adafruit_rgb_display.rgb import color565
from adafruit_rgb_display import ili9341
import pandas as pd

#give sensors time to warm up to avoid errors
time.sleep(1)

#initialize sensor instances and i2c configuration
i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
sgp = adafruit_sgp30.Adafruit_SGP30(i2c)
sps = SPS30(1)
scd = SCD30()

#set up pins for fans, button, and display LED
GPIO.setmode(GPIO.BCM)
GPIO.setup(18,GPIO.OUT)
GPIO.setmode(GPIO.BCM)
GPIO.setup(14,GPIO.OUT)
GPIO.setmode(GPIO.BCM)
GPIO.setup(5, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.output(14,GPIO.HIGH)
GPIO.output(18,GPIO.HIGH)

# Set up display pins and instance
cs_pin = digitalio.DigitalInOut(board.D8)
dc_pin = digitalio.DigitalInOut(board.D25)
reset_pin = digitalio.DigitalInOut(board.D24)
BAUDRATE = 24000000
spi = busio.SPI(clock=board.SCLK, MOSI=board.MOSI, MISO=board.MISO)
display = ili9341.ILI9341(spi, cs=cs_pin, dc=dc_pin, rst = reset_pin, baudrate=BAUDRATE)
font = ImageFont.truetype("/home/pi/Documents/utme-detector/sans-serif.ttf", 20)


#start measurement for sensors that need initializiation before data can be requested from them
sps.start_measurement()
sgp.iaq_init()

#delay one more second for screen to boot and data to be ready for retrieval
time.sleep(1)


recording = False
df = None
# Main loop:
while True:
    #refresh background image each loop
    bg= Image.open('/home/pi/Documents/utme-detector/bg.jpg')
    bg= bg.resize((240,320), Image.ANTIALIAS)
    draw = ImageDraw.Draw(bg)
    
    #make call to RTC each loop and save timestamp
    try:
        rtc_time = str(subprocess.check_output(['sudo', 'hwclock', '-r']))
        #micahels script required the date time to be in this specific format
        time_for_file = rtc_time[2:12] + 'T' + rtc_time[13:25] + 'Z'
        timestamp = rtc_time[13:24]
    except: #if the hwclock is not working, then get sudo date from terminal
        rtc_time = str(subprocess.check_output(['sudo', 'date', '--iso-8601=seconds']))
        time_for_file = rtc_time[2:-9] + '.000Z'
        timestamp = rtc_time[13:21]+ '.00'
    
    #loop is on 2 second delay
    time.sleep(2)
    '''
    This if block checks if the button is being pressed.
    If it is, a new dataframe is created that will store data each loop.
    If not, the block is skipped.
    If the button has been pressed previously, the data is saved as a CSV and stored locally,
    and then deletes the saved data from RAM.
    '''
    input_state = GPIO.input(5)
    if input_state == False:
        if recording == False:
            recording = True
            #rtc_time = str(subprocess.check_output(['sudo', 'hwclock', '-r']))
            date = rtc_time[2:12]
            df = pd.DataFrame(columns = ['Timestamp',
                                         'CO2',
                                         'T',
                                         'RH',
                                         'TVOC',
                                         'PM1.0',
                                         'PM2.5',
                                         'PM4.0',
                                         'PM10.0',
                                         'PMSize'])
        elif recording == True:
            recording = False
            file_datetime = date + '-' + df.iloc[0]['Timestamp']
            file_datetime = file_datetime[:-3]#last second fix to solve issue where windows cannot read files due to period in the name
            filename_csv = file_datetime + '.csv'
            filename = '/home/pi/Documents/utme-detector/data/' + filename_csv
            #reformat file for Michael's script
            df_transposed = df.T
            df_transposed.to_csv(path_or_buf = filename, index = True, header = False) #save file as CSV
            data = open('/home/pi/Documents/utme-detector/data/' + filename_csv , 'a') 
            data.write('title,' + file_datetime + '\n' )
            data.write('start,' + time_for_file)
            os.fsync(data) #THIS IS A VERY IMPORTANT LINE WHICH PREVENTS DEVICE FROM DELETING DATA WHEN TURNED OFF AFTER RECORDING IS DONE
            data.close()
            df = None
        time.sleep(2)
    
    #check if new data is ready for scd30, and if it is, display it
    if scd.get_data_ready():
        #read measurement if ready, otherwise skip to next sensor
        m = scd.read_measurement()
        if m is not None:
            #temperature and room humidity are combined as one text object
            T_RH = str(m[1])[:4] + '       ' + str(m[2])[:5]
            #paste T and RH to display
            txt=Image.new('L', (300,30))
            d = ImageDraw.Draw(txt)
            d.text( (0, 0), T_RH,  font=font, fill=255)
            w=txt.rotate(270,  expand=1)
            bg.paste( ImageOps.colorize(w, (0,0,0), (255,255,255)), (44,138),  w)

            #get CO2
            CO2 = str(m[0])[:6]
            #CO2 safety indicator
            if float(CO2) > 5000:
                color = (255,0,0)
            elif float(CO2) < 3000:
                color = (0,128,0)
            else:
                color = (255,255,0)
            #paste CO2 reading to display
            txt=Image.new('L', (300,30))
            d = ImageDraw.Draw(txt)
            d.text( (0, 0), CO2,  font=font, fill=255)
            w=txt.rotate(270,  expand=1)
            bg.paste( ImageOps.colorize(w, (0,0,0), color), (44,23),  w)

    #check for available PM data then paste to screen if ready
    sps.read_measured_values()
    if sps.dict_values['pm2p5'] and sps.dict_values['typical']is not None:
        pm25 = str(float(sps.dict_values['pm2p5']))[:5]
        #safety indicator, numbers taken from google and converted from mg/m3 to ppb
        if float(pm25) > 150.5:
            color = (255,0,0)
        elif float(pm25) < 55.4:
            color = (0,128,0)
        else:
            color = (255,255,0)
        pm_size = str(float(sps.dict_values['typical']))[:5]
        
        #paste PM data to display
        txt=Image.new('L', (60,30))
        d = ImageDraw.Draw(txt)
        d.text( (0, 0), pm25,  font=font, fill=255)
        w=txt.rotate(270,  expand=1)
        bg.paste( ImageOps.colorize(w, (0,0,0), color), (148,230),  w)
        
        txt=Image.new('L', (160,30))
        d = ImageDraw.Draw(txt)
        d.text( (0, 0), pm_size,  font=font, fill=255)
        w=txt.rotate(270,  expand=1)
        bg.paste( ImageOps.colorize(w, (0,0,0), (0,128,0)), (148,133),  w) #colored green because it looks better
    
    #retrieve TVOC sensor reading
    TVOC = str(sgp.TVOC)
    #safety indicator.  References: https://www.advsolned.com/how-tvoc-affects-indoor-air-quality-effects-on-wellbeing-and-health/ https://www.teesing.com/en/page/library/tools/ppm-mg3-converter#mg/m3%20to%20PPM%20converter
    if float(TVOC) > 310:
        color = (255,0,0)
    elif float(TVOC) < 155:
        color = (0,128,0)
    else:
        color = (255,255,0)
    #past TVOC data to display image
    txt=Image.new('L', (160,30))
    d = ImageDraw.Draw(txt)
    d.text( (0, 0), TVOC,  font=font, fill=255)
    w=txt.rotate(270,  expand=1)
    bg.paste( ImageOps.colorize(w, (0,0,0), color), (148,32),  w)
    
    if recording == True:
        #if recording, add a row of data to the dataframe
        data_series = pd.Series({'Timestamp': timestamp,
                                 'CO2': CO2,
                                 'T': m[1],
                                 'RH': m[2],
                                 'TVOC': TVOC,
                                 'PM1.0': sps.dict_values['pm1p0'],
                                 'PM2.5': sps.dict_values['pm2p5'],
                                 'PM4.0': sps.dict_values['pm4p0'],
                                 'PM10.0': sps.dict_values['pm10p0'],
                                 'PMSize': sps.dict_values['typical']})
        df = df.append(data_series[df.columns], ignore_index = True)

        #prints recording indicator if data is currently recording
        txt=Image.new('L', (160,30))
        d = ImageDraw.Draw(txt)
        d.text( (0, 0), 'Recording',  font=font, fill=255)
        w=txt.rotate(270,  expand=1)
        bg.paste( ImageOps.colorize(w, (0,0,0), (255,0,0)), (205,100),  w)

    #displayt image on display with all data printed on
    display.image(bg)
