import logging
import time
import json
import RPi.GPIO as GPIO
from threading import Timer
import paho.mqtt.client as mqtt
import configparser

MAIN_SWITCH = 21
SINGLE_COFFEE = 20
DOUBLE_COFFEE = 16
LED_INPUT = 26

SWITCH_INTERVAL = 0.5
BOUNCE_TIME = 200  # ms

# LED periods
WARMING_UP_PERIOD = 2.0  # in microseconds
WATER_EMPTY = 0.2  # in microseconds

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('coffeemachine')


# ToDo:
# Extract config to external file
# Documentation...

# noinspection PySimplifyBooleanCheck
class CoffeeMachine:
    def __init__(self):

        GPIO.cleanup()

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(MAIN_SWITCH, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(SINGLE_COFFEE, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(DOUBLE_COFFEE, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(LED_INPUT, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        # detect changes in LED
        GPIO.remove_event_detect(LED_INPUT)
        GPIO.add_event_detect(LED_INPUT, GPIO.FALLING, callback=self.led_changed, bouncetime=BOUNCE_TIME)
        self.recent_led_change = time.time()

        self.warmed_up_timer = None

        self.mode = 'single'  # single or double

        logger.info('Initialized coffee machine.')

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

    def led_changed(self, channel):

        # avoid noise
        time_diff = time.time() - self.recent_led_change
        self.recent_led_change = time.time()
        if time_diff < 0.95:
            return

        led_state = GPIO.input(LED_INPUT)
        logger.info('LED changed within {} ms (state: {})'.format(time_diff, led_state))

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

        self.warmed_up_timer = Timer(WARMING_UP_PERIOD * 2000 / 1000, time_coffee_making, ())
        self.warmed_up_timer.start()

    def make_coffee(self, mode):

        self.mode = mode

        logger.info('Starting coffee making coffee with mode {}'.format(self.mode))

        # turn on if neccessary
        if GPIO.input(LED_INPUT) == False:
            logger.info('turning coffee machine on')
            self.toggle_on_off()
            time.sleep(1)

        # schedule making of coffee, which is reset in falling led callback
        self.set_coffee_timer()
        logger.info('Scheduled coffee making after heat up phase')


if __name__ == '__main__':
    coffeemachine = CoffeeMachine()


    def on_message(client, userdata, msg):

        if msg.topic == '/coffee/toggle_on_off':
            logger.info('Received toggle on off command')
            coffeemachine.toggle_on_off()
        elif msg.topic == '/coffee/make':
            message = json.loads(msg.payload.decode('utf-8'))
            mode = message['mode']

            logger.info('Received mode {}'.format(mode))

            coffeemachine.make_coffee(mode=mode)


    def on_connect(client, userdata, flags, rc):
        # logger.info('Connected with result code ' + str(rc))
        client.subscribe(topic='/coffee/make')
        client.subscribe(topic='/coffee/toggle_on_off')


    logger.info('Initializing MQTT client')
    config = configparser.ConfigParser()
    config.read('config.ini')
    client = mqtt.Client(client_id='coffeemachine')
    client.username_pw_set(username=config['mqtt_username'], password=config['mqtt_password'])
    client.on_message = on_message
    client.on_connect = on_connect
    client.connect(config['mqtt_host'], config['mqtt_port'], keepalive=600)

    logger.info('Starting MQTT loop')
    client.loop_forever()
