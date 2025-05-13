import time
from threading import Thread
import pigpio
from pigpio_dht import DHT11
import paho.mqtt.client
from typing import NoReturn
import sys

SENSOR_PIN: int = 17
BUTTON_PIN: int = 27
LED_R_PIN: int = 23
LED_B_PIN: int = 24
LED_W_PIN: int = 25

BUTTON_GATE: int = 4

BROKER: str = "mqttbroker.lan"
PORT: int = 1883
SELF_TOPIC_T: str = "final/dragonpi/T"
SELF_TOPIC_H: str = "final/dragonpi/H"
SUBS_TOPIC: str = "final/#"

FLASK_HOST: str = "dragonpi"
FLASK_PORT: int = 8080

others_T: dict[str, int] = {}
others_H: dict[str, int] = {}

sensor_temp_c: int = None
sensor_temp_f: int = None
sensor_humidity: int = None

sender_state: bool = False

button_throttle: int = 0
button_down: bool = False
button_state: bool = False
button_up: bool = False

pi: pigpio.pi = None
sensor_thread: Thread = None
client: paho.mqtt.client.Client = None
dht11: DHT11 = None

# flask api here

try:

    pi = pigpio.pi()

    pi.set_mode(BUTTON_PIN, pigpio.INPUT)
    pi.set_mode(LED_R_PIN, pigpio.OUTPUT)
    pi.set_mode(LED_B_PIN, pigpio.OUTPUT)
    pi.set_mode(LED_W_PIN, pigpio.OUTPUT)

    dht11 = DHT11(SENSOR_PIN, pi=pi)

    def parse_topic(topic: str) -> tuple[bool, str, str, str]:
        parts: list[str] = topic.split("/")
        valid: bool = len(parts) == 3
        return valid, *parts

    def sensor_reader() -> NoReturn:
        while 1:
            output: dict = dht11.read()
            if output["valid"]:
                global sensor_temp_c
                global sensor_temp_f
                global sensor_humidity
                sensor_temp_c = round(output["temp_c"])
                sensor_temp_f = round(output["temp_f"])
                sensor_humidity = round(output["humidity"])
            else:
                continue
            time.sleep(0.1)

    sensor_thread = Thread(sensor_reader)

    client = paho.mqtt.client.Client(paho.mqtt.client.CallbackAPIVersion.VERSION2)

    client.on_connect = lambda client, userdata, flags, code, properties : print((f"erreur de connexion ({code})", "connecté")[code == 0])
    client.connect(BROKER, PORT)

    sensor_thread.start()

    while True:
        ...
        # button logic

        # sender logic

except KeyboardInterrupt as e:
    pass
except Exception as e:
    print(e)
finally:
    if client: client.disconnect()
    if pi: pi.stop()
    sys.exit()
    exit()