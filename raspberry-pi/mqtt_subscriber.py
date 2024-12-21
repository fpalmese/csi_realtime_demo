#!/usr/bin/python3
import paho.mqtt.client as mqtt
import time
from nexmon_manager import NexmonManager
import subprocess
from csi_parser import CsiParser
import matplotlib.pyplot as plt
import pickle
import json
from websockets.sync.server import serve
import asyncio
from threading import Thread
from socket import *

#CAPTURE DEFAULTS, SHOULD BE ADAPTED FROM THE GUI

#device = "A0:9F:10:7F:B3:68" #Wi-Fi Camera
#devices = ["A0:9F:10:7F:B3:68"] #Wi-Fi Camera
#devices = ["2C:3A:E8:1C:BC:71"] #ESP8266
#devices = ["2C:3A:E8:1C:BC:71"] #ESP32
all_devs = ["a0:9f:10:7f:b3:68","2c:3a:e8:1c:bc:71","40:4c:ca:4c:17:dc"] #both
device_select = 1

# COLLECTION PARAMETERS #
started = False

#MANAGER OBJECTS
nm = NexmonManager()
cp = CsiParser()

# COMPRESSION PARAMETERS #
num_components = 0
sq_bits = 0

# MQTT PARAMETERS #
broker_address = "localhost"  # Broker address
port = 1883  # Broker port
mqtt_client = mqtt.Client()  # create new instance

#UDP SERVER INFO (to send the results)
connected_client = None
server_port = 12345
sending_socket = socket(AF_INET,SOCK_DGRAM)


def udp_server_func():
	global connected_client
	server_socket = socket(AF_INET,SOCK_DGRAM)
	server_socket.bind(("",server_port))
	connected = False
	while(True):
		msg,address = server_socket.recvfrom(2048)
		if msg.decode("UTF-8") == "CONNECT":
			connected_client = address
			connected = True
		server_socket.sendto("CONNACK".encode("UTF-8"),address)


def realtime_callback(value):
	#result = mqtt_client.publish("csi_realtime_value",value)
	#if current_ws is not None:
	#	current_ws.send(value)
	if connected_client is not None:
		sending_socket.sendto(value.encode("UTF-8"),connected_client)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe([("#",1)])

def configure_params(config_params):
	global band,bandwidth,channel,device_select
	
	#parse the input params from the payload
	capture_mode = config_params.get("cap_mode","LIVE")
	band = float(config_params.get("band",2.4))
	bandwidth = int(config_params.get("bandwidth",20))
	channel = int(config_params.get("channel",1))
	input_pcap = config_params.get("input_pcap",None)
	win_duration = float(config_params.get("duration",0.5))
	proc_type = int(config_params.get("proc_type",1))
	device_select = int(config_params.get("devices",1))
	#to be fixed based on input
	devices = [all_devs[device_select-1]] if device_select > 0 else all_devs

	#configure and start nexmon
	nm.configure(channel = channel, band = band, bandwidth = bandwidth, devices = devices)

	#configure and start csi collection
	cp.configure(devices = devices,win_duration = win_duration,proc_type = proc_type, capture_mode = capture_mode, input_pcap = input_pcap)


def on_message(client, userdata, message):
	global started
	print("Message received: " + message.topic + " : " + str(message.payload.decode()))
	if (message.topic == 'start_csi_realtime' and started==False):
		# PREPARE THE CONFIGURATION (with standard values)
		proc = subprocess.run("cat /sys/class/net/wlan0/carrier",
        		stdout=subprocess.PIPE,
        		stderr=subprocess.PIPE,
        		shell=True,
        		text=True
        	)
		if (proc.returncode!=0):
        		print ("Connecting")
        		time.sleep(10)

		try:
			input_params = json.loads(message.payload.decode())
		except Exception as e:
			print("Empty Start")
			input_params = {}

		configure_params(input_params)

		nm.start()
		cp.start(callback=realtime_callback)
		started = True
	
	if (message.topic == 'save_csi_realtime' and started==False):
		print("updating collection params")
		try:	
			input_params = json.loads(message.payload.decode())
		except Exception as e:
			print("Empty Save, ",e)
			input_params = {}

		configure_params(input_params)

	if (message.topic == 'stop_csi_realtime' and started==True):
		print("should stop")
		cp.stop()
		started = False

	if (message.topic == 'set_csi_duration'):
		duration = float(message.payload.decode())
		print("new duration: ",duration)
		cp.set_duration(duration)

	if (message.topic == 'set_verbose'):
		payload = int(message.payload.decode())
		cp.set_verbose(payload != 0)

	if (message.topic == 'set_processing_type'):
		payload = int(message.payload.decode())
		cp.set_processing_type(payload)

	if (message.topic == 'get_current_status'):
		res = cp.get_params()
		res.update(nm.get_params())
		res["status"] = started
		res["device_select"] = device_select
		msg = json.dumps(res)
		#msg = f'\{"status":{started},"devices":{cp_params.devices},"band":{nm_params.band},"bandwidth":{nm_params.bandwidth},"channel":{nm_params.channel},"capture_mode":{cp_params.capture_mode},"proc_type":{cp_params.proc_type}\}'
		time.sleep(0.1)
		mqtt_client.publish("running_status",msg,retain=True)
		time.sleep(0.05)
		mqtt_client.publish("running_status","",retain=True)

#start udp server to send back the response (client will connect)
udp_thread = Thread(target=udp_server_func)
udp_thread.start()

#set mqtt client
mqtt_client.on_connect = on_connect  # attach function to callback
mqtt_client.on_message = on_message  # attach function to callback
mqtt_client.connect(broker_address, port=port)  # connect to broker
mqtt_client.loop_forever()
