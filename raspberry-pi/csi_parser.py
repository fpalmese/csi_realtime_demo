from threading import Thread
from scapy.all import sniff, UDP, IP
from scapy.config import conf
import time
import numpy as np
import matplotlib.pyplot as plt
import json
# 0 to 32 are correct
# 33 to 64 are -32 to -1
# e.g. 33 = -32, 34 = -31, 35 = -30, 36 = -29, 37 = -28
#csi_columns_to_exclude = [0,7,21,28,29,30,31,32,33,34,35,43,57] #indexes: 0,7,21,28,29,30,31  -32,-31,-30,-29, -21, -7
nonnull_subcarriers = list(range(1,7))+list(range(8,21))+list(range(22,28))+list(range(36,43))+list(range(44,57))+list(range(58,64))
ordered_subcarriers = list(range(32,64))+list(range(32))

ordered_nonnull_subcarriers = list(range(36,43))+list(range(44,57))+list(range(58,64))+list(range(1,7))+list(range(8,21))+list(range(22,28)) # 
all_subcarriers = list(range(64)) # ALL (-32,0,31)

#selected_subcarriers = list(range(37,64)) + list(range(1,29))
selected_subcarriers = ordered_nonnull_subcarriers
selected_subcarriers = all_subcarriers

#init min array for csi (64 size)
compute_min_max = False
csi_min_global = np.array([np.inf]*64)
csi_max_global = np.array([-np.inf]*64)
csi_range_global = np.array([0]*64)

start_time = 0

pck_rate = 20

#convert the byte list to a string containing the mac
def bytes_to_mac(byteList):
    if len(byteList) != 6:
        string = ""
    else:
        string = str(format(byteList[0],'02x'))
        for i in range(1,6):
            string = string + ":" + str(format(byteList[i],'02x'))
    return string

#function to shape two bytes as signed int in littl endian
def int_shaper(byte0,byte1):
    return int.from_bytes([byte0,byte1], byteorder='little',signed=True)

def csi_from_bytes(payload_bytes):
    int_shaper_vectorized = np.vectorize(int_shaper)
    byte_array = np.array(payload_bytes,dtype=np.uint8)
    reshaped = byte_array.reshape(64, 4)
    real_parts = int_shaper_vectorized(reshaped[:,0],reshaped[:,1])
    imag_parts = int_shaper_vectorized(reshaped[:,2],reshaped[:,3])
    #csi_vector = real_parts + 1j * imag_parts
    return real_parts,imag_parts

def parse_packet(packet):
        #print(packet.time)
        #list_bytes = list(bytes(packet["UDP"].payload))
        #print(f"First two bytes: {hex(list_bytes[0]),hex(list_bytes[1])}")
        #print(f"Mac address: {bytes_to_mac(list_bytes[4:10])}")
        #print(f"Seq. Number: {int.from_bytes(list_bytes[10:12], byteorder='little')}")
        #print(list_bytes[18:])
        try:
            real, imag = csi_from_bytes(list(bytes(packet["UDP"].payload))[18:18+256]) #parse the csi from the payload bytes (byte 18 on)
            ampl = np.sqrt(real**2 + imag**2)
        except Exception as e:
            print("ERROR: ",e)
            return np.array([0 for i in range(64)])
        #print(ampl)
        return ampl

class TimeWindow:
    def __init__(self, device, win_time=0,duration=3.0):
        self.device = device
        self.packets = []
        self.time = win_time
        self.duration = duration

    def set_time(self, new_time):
        self.time = new_time

    def set_duration(self, new_duration):
        self.duration = new_duration

    def add_packet(self,packet):
        self.packets.append(packet)
    
    def build_csi_matrix(self):
        return np.array([parse_packet(p) for p in self.packets])
    
    def apply_compression(self,matrix,compression_params = {}):
        if not matrix.size or not compression_params:
            return matrix
    
        sq_enabled = compression_params.get("sq_enabled",False)
        if sq_enabled:
            sq_bits = int(compression_params.get("sq_bits",0))
            if sq_bits > 0:
            # Normalize to [0, 1]
                normed = (matrix - csi_min_global) / csi_range_global
                
                # Handle division by zero
                normed = np.nan_to_num(normed)
                
                # Scale to levels
                q_matrix = np.round(normed * (2 ** sq_bits - 1)).astype(int)
                matrix = np.clip(q_matrix, 0, 2 ** sq_bits -1)  # safety
    
        vq_enabled = compression_params.get("vq_enabled",False)
        
        if vq_enabled:
            # Apply vector quantization (VQ) here
            pass
        
        pca_enabled = compression_params.get("pca_enabled",False)
        if pca_enabled:
            pass
        
        return matrix

    def process1(self,subcarriers = selected_subcarriers,compression_params = {}, verbose = False):
        s_t = time.time()
        if verbose:
            print(f'Window time: {self.time}, Packets: {len(self.packets)}, Duration: {self.duration}')
        #print(f"Seq. Number: {int.from_bytes(list(bytes(self.packets[0]['UDP'].payload))[10:12], byteorder='little')}")

        ampl_matrix = self.build_csi_matrix()
        #print(ampl_matrix[0,:])
        #csi_aggr = np.mean(np.std(np.delete(ampl_matrix, csi_columns_to_exclude, axis=1), axis=0))
        #csi_aggr = np.mean(np.std(ampl_matrix[:,subcarriers], axis=0))
        csi_aggr = np.mean(np.mean(ampl_matrix[:,subcarriers], axis=0))

        if verbose:
            print(f"Window PX time: {time.time() - s_t} seconds")
        return f"{self.device},{self.time},{csi_aggr}"

    def process2_old(self,subcarriers = selected_subcarriers,compression_params = {},verbose = False):

        s_t = time.time()
        if verbose:
            print(f'Window time: {self.time}, Packets: {len(self.packets)}, Duration: {self.duration}')

        ampl_matrix = self.build_csi_matrix()

        ret_matrix = ampl_matrix[:,subcarriers]
        res = json.dumps(ret_matrix.tolist())

        if verbose:
            print(f"Window PX time: {time.time() - s_t} seconds")
            
        return res
    
    def process2(self,subcarriers = selected_subcarriers,compression_params = {},verbose = False):
        global csi_min_global, csi_max_global, csi_range_global
        s_t = time.time()
        if verbose:
            print(f'Window time: {self.time}, Packets: {len(self.packets)}, Duration: {self.duration}')
        
        ampl_matrix = self.build_csi_matrix()
        compression_matrix = self.apply_compression(ampl_matrix, compression_params)
        
        ret_matrix = compression_matrix[:,subcarriers]
        orig_csi_aggr = np.mean(np.std(ampl_matrix[:,subcarriers], axis=0))
        csi_aggr_compressed = np.mean(np.std(ret_matrix, axis=0))

        # compute min for each col and update global\
        if compute_min_max:
            csi_min_global = np.minimum(csi_min_global, np.min(ampl_matrix, axis=0))
            csi_max_global = np.maximum(csi_max_global, np.max(ampl_matrix, axis=0))
            csi_range_global = csi_max_global - csi_min_global
        res_json = {
                    "device":self.device,
                    "duration":self.duration,
                    "time":str(self.time-start_time),
                    "data":ret_matrix.tolist(),
                    "csi_aggr":str(csi_aggr_compressed),
                    "orig_csi_aggr":str(orig_csi_aggr)
                    }
        res = json.dumps(res_json)

        if verbose:
            print(f"Window PX time: {time.time() - s_t} seconds")
        
        return res

    def process(self,subcarriers = selected_subcarriers,type=1,compression_params = {},verbose=False):
        return self.process1(subcarriers = subcarriers,compression_params = compression_params,verbose = verbose) if type==1 else self.process2(subcarriers = subcarriers,compression_params = compression_params,verbose = verbose)


#define the CSI collection and parsing. Initialize an object and call the start method to run, stop method to interrupt
class CsiParser:
    def __init__(self):
        #PARAMS
        self.capture_mode = "LIVE"
        self.iface = "wlan0"
        self.input_pcap = "6passagesNOFOV.pcap" #self.input_pcap = "presence20minsNOFOV.pcap"
        self.win_duration = 0.5
        self.subcarriers = selected_subcarriers
        self.devices = []
        self.proc_type = 1
        self.from_pcap = self.capture_mode == "PCAP"
        #COMPRESSION PARAMS
        self.compression_params = {}
        self.pcap_speed = 2  #default
        self.sleep_time = 1 / (self.pcap_speed * pck_rate)

        #VARIABLES AND PROCESSES
        self.run_collection = False #variable to control the csi collection (sniff thread)
        self.run_processing = False #variable to control the csi processing (queue consumer thread)
        self.listen_socket = None
        self.collector_thread = None #csi collection
        self.processor_thread = None #csi processing
        self.current_window = {} #active window
        self.window_queue = [] #queued windows
        self.verbose = True
        self.callback = None
        self.start_time = 0
        self.last_pck_time = 0
        self.cyclic_time = 0
        
    def start(self,callback):
        global csi_min_global, csi_max_global, compute_min_max,csi_range_global
        # load min/max global from file (if there) otherwise set to null
        try:
            with open('csi_min_global.json', 'r') as f:
                csi_min_global = np.array(json.load(f))
        except FileNotFoundError as e:
            compute_min_max = True
        try:
            with open('csi_max_global.json', 'r') as f:
                csi_max_global = np.array(json.load(f))
        except FileNotFoundError:
            compute_min_max = True
        
        if not compute_min_max:
            csi_range_global = csi_max_global - csi_min_global
            
        self.start_time = 0
        self.cyclic_time = 0
        self.callback=callback
        print("Starting capture: compute_min_max is ",compute_min_max)
        self.run_collection = True
        self.run_processing = True
        self.listen_socket = conf.L2socket(iface=self.iface,filter="udp port 5500")
        self.collector_thread = Thread(target=self.collector_function)
        self.processor_thread = Thread(target=self.processor_function)
        #self.current_window = TimeWindow(duration=self.win_duration)
        self.current_window = {mac:TimeWindow(device=mac,duration=self.win_duration) for mac in self.devices}
        self.collector_thread.start()
        self.processor_thread.start()

    def stop(self):
        
        print("Stopping capture")
        #wait for colletion to conclude
        self.run_collection = False
        if self.collector_thread is not None:
            self.collector_thread.join(0.2)
            self.listen_socket.close()
        print("joined")
        #flash last window before stopping
        for cw in self.current_window.values():
            if len(cw.packets) >0:
                self.window_queue.insert(0,cw)

        #wait for processing to conclude
        self.run_processing = False
        if self.processor_thread is not None:
            self.processor_thread.join()
        
        self.collector_thread = None
        self.processor_thread = None
        self.current_window = {}
        self.callback = None
        self.listen_socket = None
        self.start_time = 0
        self.window_queue = []
        self.cyclic_time = 0
        if compute_min_max:
            # dump to files
            with open('csi_min_global.json', 'w') as f:
                json.dump(csi_min_global.tolist(), f)
            with open('csi_max_global.json', 'w') as f:
                json.dump(csi_max_global.tolist(), f)

        print("TERMINATED SUCCESSFULLY")

    # Function to handle each packet
    def handle_packet_sniff(self,packet):
        global start_time
        packet.time = self.cyclic_time + packet.time
        
        self.last_pck_time = packet.time
        sender = bytes_to_mac(list(bytes(packet["UDP"].payload))[4:10])

        #setup initial time
        if self.start_time == 0:
            start_time = packet.time
            self.start_time = packet.time

        if sender in self.devices or len(self.devices) == 0:
            if sender not in self.current_window:
                self.current_window[sender] = TimeWindow(device=sender, duration=self.win_duration)

            #if window is old!
            if packet.time > self.current_window[sender].time + self.win_duration:
                #if window was not empty, flush it and reset
                if(len(self.current_window[sender].packets)!=0):
                    self.window_queue.insert(0,self.current_window[sender])
                    self.current_window[sender] = TimeWindow(device=sender, duration=self.win_duration)
                #adjust time of the window
                #self.current_window.set_time(packet.time)
                self.current_window[sender].set_time(self.start_time + np.floor((packet.time - self.start_time)/self.win_duration)*self.win_duration)
            #add the packet to the correct window
            self.current_window[sender].add_packet(packet)

            if self.from_pcap and self.pcap_speed < 10:
                time.sleep(self.sleep_time)

    #function to sniff packets. You sniff from wlan0 but you can potentially read a PCAP file
    def collector_function(self):
        if self.capture_mode == "LIVE":
            #sniff(iface=self.iface,filter="udp port 5500", prn=self.handle_packet_sniff, store=0, stop_filter=lambda x: not self.run_collection)
            sniff(opened_socket = self.listen_socket, prn=self.handle_packet_sniff, store=0, stop_filter=lambda x: not self.run_collection)
        #sniff(offline="test.pcap",filter="udp port 5500", prn=self.handle_packet_sniff, store=0, stop_filter=lambda x: not self.run_collection)
        elif self.capture_mode == "PCAP":
            while self.run_collection:
                sniff(offline=self.input_pcap,filter="udp port 5500", prn=self.handle_packet_sniff, store=0, stop_filter=lambda x: not self.run_collection)
                self.cyclic_time = (self.last_pck_time - self.start_time)
                print(f"\n\nCyclic time: {self.cyclic_time}")
                # reinit self.current_window = {mac:TimeWindow(device=mac,duration=self.win_duration) for mac in self.devices}
                time.sleep(0.05)
                # dump csi_min_global and csi_max_global objects for next uses
                with open('csi_min_global.json', 'w') as f:
                    json.dump(csi_min_global.tolist(), f)
                with open('csi_max_global.json', 'w') as f:
                    json.dump(csi_max_global.tolist(), f)
            
    #function to process the queue of windows
    def processor_function(self):
        #wait for new windows, or terminate
        while self.run_processing:
            #keep going until you have new windows to process
            while len(self.window_queue) > 0:
                win = self.window_queue.pop(0)

                res = win.process(self.subcarriers,verbose = self.verbose,type = self.proc_type, compression_params = self.compression_params)
                #res = win.process2(self.subcarriers,verbose = self.verbose)
                
                self.callback(res)

    def set_capture_mode(self, capture_mode="LIVE"):
        self.capture_mode = capture_mode

    def set_iface(self, iface="wlan0"):
        self.iface = iface

    def set_input_pcap(self, input_pcap=None):
        self.input_pcap = input_pcap

    def set_duration(self, duration):
        self.win_duration = duration
    
    def set_pcap_speed(self,speed):
        self.pcap_speed = speed
        self.sleep_time = 1 / (self.pcap_speed * pck_rate)

    def set_subcarriers(self, subcarriers = selected_subcarriers):
        self.subcarriers = subcarriers

    def set_devices(self, devices):
        self.devices = [d.lower() for d in devices]
        
    def set_callback(self, callback):
        self.callback = callback

    def set_verbose(self, verbose):
        self.verbose = verbose

    def set_proc_type(self, proc_type):
        self.proc_type = proc_type

    def set_compression(self, compression_params):
        self.compression_params = compression_params
        
    def configure(self, devices = None, win_duration = None,proc_type = None, capture_mode = None,input_pcap = None, compression_params = None, pcap_speed = None):
        print(devices,win_duration,proc_type,capture_mode,input_pcap,compression_params,pcap_speed)
        
        if devices is not None:
            self.devices = devices
            
        if win_duration is not None:
            self.win_duration = win_duration
            
        if proc_type is not None:
            self.proc_type = proc_type
            
        if capture_mode is not None:
            self.capture_mode = capture_mode
            self.from_pcap = self.capture_mode == "PCAP"
            
        if input_pcap is not None:
            self.input_pcap = input_pcap
            
        if compression_params is not None:
            self.compression_params = compression_params
            
        if pcap_speed is not None:
            self.pcap_speed = pcap_speed
            self.sleep_time = 1 / (self.pcap_speed * pck_rate)


    def reset(self):
        self.devices = []
        self.win_duration = 3
        self.proc_type = 1
        self.capture_mode = "LIVE"

    def get_params(self):
        return {"capture_mode":self.capture_mode,"iface":self.iface,
                "proc_type":self.proc_type,"win_duration":self.win_duration,
                "subcarriers":self.subcarriers,"devices":self.devices,
                "input_pcap":self.input_pcap,
                "sq_enabled":self.compression_params.get("sq_enabled",False),
                "vq_enabled":self.compression_params.get("vq_enabled",False),
                "pca_enabled":self.compression_params.get("pca_enabled",False),
                "sq_bits":self.compression_params.get("sq_bits",0),
                "vq_bits":self.compression_params.get("vq_bits",0),
                "pca_num":self.compression_params.get("pca_num",0),
                "pcap_speed":self.pcap_speed
                }

