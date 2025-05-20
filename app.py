import time
from threading import Thread
import pigpio
from pigpio_dht import DHT11
import paho.mqtt.client
from typing import NoReturn
import sys
from flask import Flask, jsonify, request


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

button_throttle: int = BUTTON_GATE
button_down: bool = False
button_state: bool = True
button_up: bool = False

pi: pigpio.pi = None
sensor_thread: Thread = None
client: paho.mqtt.client.Client = None
dht11: DHT11 = None

# flask api here
app = Flask(__name__)

@app.route('/donnees',methods=['GET'])
def donnees():
    return jsonify({
        "T": int(sensor_temp_c),
        "H": int(sensor_humidity)
    })

@app.route("/etat", methods=["POST"])
def set_etat():
    global sender_state
    json = request.get_json()
    if "etat" in json:
        if json["etat"] == 1:
            sender_state = True
            pi.write(LED_W_PIN, 1)
        elif json["etat"] == 0:
            sender_state = False
            pi.write(LED_W_PIN, 0)    
    return jsonify({'Etat': json["etat"]}),200

def start_rest():
    app.run(host=FLASK_HOST,port=FLASK_PORT)

start_rest_thread = Thread(None, start_rest)

try:

    pi = pigpio.pi()

    pi.set_mode(BUTTON_PIN, pigpio.INPUT)
    pi.set_mode(LED_R_PIN, pigpio.OUTPUT)
    pi.set_mode(LED_B_PIN, pigpio.OUTPUT)
    pi.set_mode(LED_W_PIN, pigpio.OUTPUT)

    dht11 = DHT11(SENSOR_PIN, pi=pi, timeout_secs=5)

    def parse_topic(topic: str) -> tuple[bool, str, str, str]:
        parts: list[str] = topic.split("/")
        valid: bool = len(parts) == 3
        return valid, *parts

    def sensor_reader() -> NoReturn:
        while 1:
            try:
                output: dict = dht11.read()
                if output["valid"]:
                    print("new valid reading!")
                    global sensor_temp_c
                    global sensor_temp_f
                    global sensor_humidity
                    sensor_temp_c = round(output["temp_c"])
                    sensor_temp_f = round(output["temp_f"])
                    sensor_humidity = round(output["humidity"])
                else:
                    continue
            except TimeoutError:
                print("sensor error!")
            time.sleep(0.1)

    sensor_thread = Thread(None, sensor_reader)

    client = paho.mqtt.client.Client(paho.mqtt.client.CallbackAPIVersion.VERSION2)

    client.on_connect = lambda client, userdata, flags, code, properties : print((f"erreur de connexion ({code})", "connecté")[code == 0])
    client.connect(BROKER, PORT)

    def getmsg(cl, userdata, msg):
        datatype = msg.topic.split("/")[2]
        host = msg.topic.split("/")[1]
        try:
            data = int(msg.payload.decode())
        except ValueError:
            data = False
        print(msg.topic.split("/")[1], msg.topic.split("/")[2], "Reçu:", msg.payload.decode())
        if host != FLASK_HOST:
            if datatype == "H":
                others_H[host] = data
            if datatype == "T":
                others_T[host] = data
        if sensor_temp_c != None:
            ismaxT = True
            for T in others_T.values():
                ismaxT = ismaxT and sensor_temp_c >= T
            ismaxH = True
            for H in others_H.values():
                ismaxH = ismaxH and sensor_humidity >= H
            
            pi.write(LED_R_PIN, int(ismaxT))
            pi.write(LED_B_PIN, int(ismaxH))
        
    
    client.on_message = getmsg
    client.subscribe(SUBS_TOPIC)
    client.loop_start()

    sensor_thread.start()
    start_rest_thread.start()
    last = time.time()
    lastsend = time.time()

    while True:
        button_down = False
        button_up = False
        btn = pi.read(BUTTON_PIN)
        # print(btn)
        button_throttle += (-1,1)[btn]
        button_throttle = min(BUTTON_GATE, max(0, button_throttle))
        now = time.time()
        diff = 0
        if button_throttle == 0 and button_state:
            button_down = True
            button_state = False
            print("down")
            diff = now - last
            last = now
        elif button_throttle == BUTTON_GATE and not button_state:
            button_up = True
            button_state = True
            print(sensor_temp_c, sensor_humidity, sep=" | ")
            print("up")
            diff = now - last
            last = now
            if diff > 2.0:
                sender_state = not sender_state
                pi.write(LED_W_PIN, int(sender_state))
                print("envoi changé : ", sender_state)
            else:
                print("envoi immédiat")
                client.publish(SELF_TOPIC_H, str(sensor_humidity))
                client.publish(SELF_TOPIC_T, str(sensor_temp_c))
        
        if now - lastsend > 30:
            lastsend = now
            print("envoi automatique")
            client.publish(SELF_TOPIC_H, str(sensor_humidity))
            client.publish(SELF_TOPIC_T, str(sensor_temp_c))

except KeyboardInterrupt as e:
    pass
except Exception as e:
    print(e)
finally:
    if client: client.disconnect()
    if pi: pi.stop()
    sys.exit()
    exit()