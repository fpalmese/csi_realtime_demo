#!/usr/bin/python3
import paho.mqtt.client as mqtt
import time
from nexmon_manager import NexmonManager
import subprocess
from csi_parser import CsiParser
import matplotlib.pyplot as plt
import pickle
import json

#CAPTURE DEFAULTS, SHOULD BE ADAPTED FROM THE GUI

#device = "A0:9F:10:7F:B3:68" #Wi-Fi Camera
#devices = ["A0:9F:10:7F:B3:68"] #Wi-Fi Camera
#devices = ["2C:3A:E8:1C:BC:71"] #ESP8266
#devices = ["2C:3A:E8:1C:BC:71"] #ESP32
all_devs = ["a0:9f:10:7f:b3:68","2c:3a:e8:1c:bc:71","40:4c:ca:4c:17:dc"] #both
channel = 1

# COLLECTION PARAMETERS #
started = False
rotation_period = 10
num_files = 2
eval_period = 0.5
nm = NexmonManager()
cp = CsiParser()

# COMPRESSION PARAMETERS #
num_components = 0
sq_bits = 0



# MQTT PARAMETERS #
broker_address = "localhost"  # Broker address
port = 1883  # Broker port
mqtt_client = mqtt.Client()  # create new instance

def realtime_callback(value):
	result = mqtt_client.publish("csi_realtime_value",value)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe([("start_csi_realtime", 1), ("stop_csi_realtime", 1), ("set_csi_duration", 1),("set_verbose", 1),("set_processing_type",1)])


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
			input_vals = json.loads(message.payload.decode())
			win_duration = float(input_vals.get("duration",0.5))
			capture_mode = input_vals.get("cap_mode","LIVE")
			proc_type = int(input_vals.get("proc_type",1))
			device_select = int(input_vals.get("devices",0))
		except Exception as e:
			print(e)

		devices = [all_devs[device_select-1]] if device_select > 0 else all_devs
		cp.set_devices(devices)
		cp.set_duration(win_duration)
		cp.set_processing_type(proc_type)
		cp.set_capture_mode(capture_mode)

		started = True
		nm.configure(channel, devices = devices)
		#nm.capture_realtime(file_name="realtime_test",period=rotation_period,file_count=num_files)
		cp.start(callback=realtime_callback)

		
	if (message.topic == 'stop_csi_realtime' and started==True):
		print("should stop")
		#nm.stop_realtime()
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


mqtt_client.on_connect = on_connect  # attach function to callback
mqtt_client.on_message = on_message  # attach function to callback
mqtt_client.connect(broker_address, port=port)  # connect to broker

mqtt_client.loop_forever()
