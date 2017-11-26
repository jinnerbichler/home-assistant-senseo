import logging
import time
import json
import RPi.GPIO as GPIO
from threading import Timer
import paho.mqtt.client as mqtt

MAIN_SWITCH = 21
SINGLE_COFFEE = 20
DOUBLE_COFFEE = 16
LED_INPUT = 26

SWITCH_INTERVAL = 0.5

# LED periods
WARMING_UP_PERIOD = 2.0  # in microseconds
WATER_EMPTY = 0.2  # in microseconds

logger = logging.getLogger('coffeemachine')


# ToDo:
# Setup journalctl to see log output
# Extract config to external file
# Turn on/off machine via MQTT
# Documentation...

class CoffeeMachine:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(MAIN_SWITCH, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(SINGLE_COFFEE, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(DOUBLE_COFFEE, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(LED_INPUT, GPIO.IN)

        # detect changes in LED
        GPIO.add_event_detect(LED_INPUT, GPIO.FALLING, callback=self.led_falling, bouncetime=200)
        self.recent_led_change = time.time()

        self.warmed_up_timer = None

        self.mode = 'single'  # single or double

    def toggle_on_off(self):
        logger.info('Toggling on/off')
        GPIO.output(MAIN_SWITCH, GPIO.LOW)
        time.sleep(SWITCH_INTERVAL)
        GPIO.output(MAIN_SWITCH, GPIO.HIGH)

    def toggle_single_coffee(self):
        logger.info('Toggling single coffee')
        GPIO.output(SINGLE_COFFEE, GPIO.LOW)
        time.sleep(SWITCH_INTERVAL)
        GPIO.output(SINGLE_COFFEE, GPIO.HIGH)

    def toggle_double_coffee(self):
        logger.info('Toggling double coffee')
        GPIO.output(DOUBLE_COFFEE, GPIO.LOW)
        time.sleep(SWITCH_INTERVAL)
        GPIO.output(DOUBLE_COFFEE, GPIO.HIGH)

    def led_falling(self, channel):
        logger.info('LED fell within {} ms'.format(time.time() - self.recent_led_change))
        self.recent_led_change = time.time()

        # handle making coffee timer
        if self.warmed_up_timer:
            self.warmed_up_timer.cancel()
            self.set_coffee_timer()

    def set_coffee_timer(self):

        def time_coffee_making():
            self.warmed_up_timer = None
            if self.mode == 'single':
                self.toggle_single_coffee()
            else:
                self.toggle_double_coffee()

        self.warmed_up_timer = Timer(WARMING_UP_PERIOD * 1000 / 1000, time_coffee_making, ())
        self.warmed_up_timer.start()

    def make_coffee(self):

        logger.info('Starting coffee making coffee with mode {}'.format(self.mode))

        # turn on if neccessary
        if GPIO.input(LED_INPUT) == False:
            logger.info('turning coffee machine on')
            self.toggle_on_off()
            time.sleep(1)

        # schedule making of coffee, which is reset in falling led callback
        self.set_coffee_timer()
        logger.info('Scheduled coffee making after heat up phase')


coffeemachine = CoffeeMachine()


def on_message(client, userdata, msg):
    message = json.loads(msg.payload.decode('utf-8'))
    mode = message['mode']

    logger.info('Received mode {}'.format(mode))

    coffeemachine.mode = mode
    coffeemachine.make_coffee()


def on_connect(client, userdata, flags, rc):
    logger.info('Connected with result code ' + str(rc))
    client.subscribe('/coffee/make')


def setup_mqtt():
    logger.info('Initializing MQTT client')
    client = mqtt.Client(client_id='coffeemachine')
    client.username_pw_set(username='homeassistant', password='*Naboa2015*')
    client.on_message = on_message
    client.on_connect = on_connect
    client.connect('10.0.0.34', 1883, 60)

    logger.info('Starting MQTT loop')
    client.loop_forever()


if __name__ == '__main__':
    setup_mqtt()
