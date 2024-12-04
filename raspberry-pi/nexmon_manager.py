#!/usr/bin/python3
import subprocess
import time
import os
import signal
import re 

class NexmonManager:

	def __init__(self):
		self.pcap = None
		self.band = 20
		self.chan = 7
		self.devices = []
		self.cap_name = None
	
	# This function is called when the topic is "start" to configure Nexmon for the capture
    # PASS THE PARAMS TO NEXMON
	def configure(self, channel=1, devices=[]):
		string_out=""
		self.chan = int(channel)
		self.devices = devices
		# if there are no devices to filter or if they are more than one, run the command without the device filter (in case of more devices, it is applied later on the dataframe)
		if len(devices)==1: 
			proc = subprocess.run(
                		f"./makecsiparams -c {self.chan}/{self.band} -C 1 -N 1 -m {self.devices[0]}",
                		stdout=subprocess.PIPE,
                		stderr=subprocess.PIPE,
                		shell=True,
                		cwd='/home/pi/nexmon/patches/bcm43455c0/7_45_189/nexmon_csi/utils/makecsiparams',
                		text=True
        		)
		else:
			proc = subprocess.run(
                                f"./makecsiparams -c {self.chan}/{self.band} -C 1 -N 1",
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                shell=True,
                                cwd='/home/pi/nexmon/patches/bcm43455c0/7_45_189/nexmon_csi/utils/makecsiparams',
                                text=True
                        )
		string_out = proc.stdout
		print(string_out)

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
		proc2= subprocess.run(f"sudo ifconfig wlan0 up && sudo nexutil -Iwlan0 -s500 -b -l34 -v{string_out}",
			stdout=subprocess.PIPE, 
			stderr=subprocess.PIPE,  
			shell=True,
			cwd='/home/pi/nexmon/patches/bcm43455c0/7_45_189/nexmon_csi/utils/makecsiparams',
			text=True
		)

	def capture_realtime(self, file_name,period=5,file_count=3):
		self.cap_name = file_name
		print(file_name,period,file_count)

		self.pcap = subprocess.Popen(
		["sudo","tcpdump", "-i", "wlan0", "-w", self.cap_name + ".pcap", "udp", "port", "5500","-G",str(period),"-C",str(file_count)],
		cwd='/home/pi/csi-realtime',
		preexec_fn=os.setsid
	)


	# This function is called when the topic is "stop" to stop the capture
	def stop_realtime(self):
		# kill the tcpdump
		os.killpg(os.getpgid(self.pcap.pid), signal.SIGINT)
		print('Capture stopped')

	# This function is called when the topic is "download" to download the .csv file 
	def download(self, file_name):
		self.cap_name = file_name 
		df.main(str(self.cap_name), self.add)
        