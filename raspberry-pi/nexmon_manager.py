#!/usr/bin/python3
import subprocess
import time
import os
import signal
import re 

class NexmonManager:
	def __init__(self):
		self.band = 2.4
		self.bandwidth = 20
		self.channel = 1
		self.devices = []

	def configure(self, channel=1, band = 2.4, bandwidth = 20, devices=[]):
		if channel is not None:
			self.channel = int(channel)
		if band is not None:
			self.band = float(band)
		if bandwidth is not None:
			self.bandwidth = int(bandwidth)
		if devices is not None:
			self.devices = devices

	# This function is called when the topic is "start" to configure Nexmon for the capture
    # PASS THE PARAMS TO NEXMON
	def start(self, channel=1, band = 2.4, bandwidth = 20, devices=[]):
		# if there are no devices to filter or if they are more than one, run the command without the device filter (in case of more devices, it is applied later on the dataframe)
		cmd_string = f"./makecsiparams -c {self.channel}/{self.bandwidth} -C 1 -N 1"
		if len(devices)==1: 
			cmd_string = cmd_string + f" -m {self.devices[0]}"
		print(cmd_string)
		proc = subprocess.run(cmd_string,
                		stdout=subprocess.PIPE,
                		stderr=subprocess.PIPE,
                		shell=True,
                		cwd='/home/pi/nexmon/patches/bcm43455c0/7_45_189/nexmon_csi/utils/makecsiparams',
                		text=True
        		)
		csi_params_string = proc.stdout
		print(f"CSI Params: {csi_params_string}")

		wpa = subprocess.run(
			f"sudo pkill wpa_supplicant",
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			shell=True,
			cwd='/home/pi/nexmon/patches/bcm43455c0/7_45_189/nexmon_csi/utils/makecsiparams',
			text=True
		)

		monitor_mode = subprocess.run("sudo iw phy `iw dev wlan0 info | gawk '/wiphy/ {printf \"phy\" $2}'` interface add mon0 type monitor && sudo ifconfig mon0 up",
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			shell=True,
			cwd='/home/pi/nexmon/patches/bcm43455c0/7_45_189/nexmon_csi/utils/makecsiparams',
			text=True
		)
		
		proc2= subprocess.run(f"sudo ifconfig wlan0 up && sudo nexutil -Iwlan0 -s500 -b -l34 -v{csi_params_string}",
			stdout=subprocess.PIPE, 
			stderr=subprocess.PIPE,  
			shell=True,
			cwd='/home/pi/nexmon/patches/bcm43455c0/7_45_189/nexmon_csi/utils/makecsiparams',
			text=True
		)

	def get_params(self):
		return {"band":self.band, "bandwidth":self.bandwidth, "channel":self.channel,"devices":self.devices}