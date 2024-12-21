from threading import Thread
from scapy.all import sniff, UDP, IP
from scapy.config import conf
import time
import numpy as np
import matplotlib.pyplot as plt
import json

#csi_columns_to_exclude = [0,7,21,28,29,30,31,32,33,34,35,43,57] #indexes: 0,7,21,28,29,30,31  -32,-31,-30,-29, -21, -7
nonnull_subcarriers = list(range(1,7))+list(range(8,21))+list(range(22,28))+list(range(36,43))+list(range(44,57))+list(range(58,64))
ordered_subcarriers = list(range(32,64))+list(range(32))
ordered_nonnull_subcarriers = list(range(36,43))+list(range(44,57))+list(range(58,64))+list(range(1,7))+list(range(8,21))+list(range(22,28))


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
    def __init__(self, device, win_time=0,duration=3):
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

    def process1(self,subcarriers,compression_params = {}, verbose = False):
        s_t = time.time()
        if verbose:
            print(f'Window time: {self.time}, Packets: {len(self.packets)}, Duration: {self.duration}')
        #print(f"Seq. Number: {int.from_bytes(list(bytes(self.packets[0]['UDP'].payload))[10:12], byteorder='little')}") 
        
        ampl_matrix = np.array([parse_packet(p) for p in self.packets])
        #print(ampl_matrix[0,:])
        #csi_aggr = np.mean(np.std(np.delete(ampl_matrix, csi_columns_to_exclude, axis=1), axis=0))
        #csi_aggr = np.mean(np.std(ampl_matrix[:,subcarriers], axis=0))
        csi_aggr = np.mean(np.mean(ampl_matrix[:,subcarriers], axis=0))

        if verbose:
            print(f"Window PX time: {time.time() - s_t} seconds")
        return f"{self.device},{self.time},{csi_aggr}"

    def process2(self,subcarriers,compression_params = {},verbose = False):

        s_t = time.time()
        if verbose:
            print(f'Window time: {self.time}, Packets: {len(self.packets)}, Duration: {self.duration}')
        
        ampl_matrix = np.array([parse_packet(p) for p in self.packets])
        ret_matrix = ampl_matrix[:,ordered_nonnull_subcarriers]
        res = json.dumps(ret_matrix.tolist())

        if verbose:
            print(f"Window PX time: {time.time() - s_t} seconds")


        return res

    def process(self,subcarriers = nonnull_subcarriers,type=1,compression_params = {},verbose=False):
        return self.process1(subcarriers = subcarriers,compression_params = compression_params,verbose = verbose) if type==1 else self.process2(subcarriers = subcarriers,compression_params = compression_params,verbose = verbose)


#define the CSI collection and parsing. Initialize an object and call the start method to run, stop method to interrupt
class CsiParser:
    def __init__(self):
        #PARAMS
        self.capture_mode = "LIVE"
        self.iface = "wlan0"
        self.input_pcap = "6passagesNOFOV.pcap" #self.input_pcap = "presence20minsNOFOV.pcap"
        self.win_duration = 0.5
        self.subcarriers = nonnull_subcarriers
        self.devices = []
        self.proc_type = 1
        
        #COMPRESSION PARAMS
        self.sq_bits = 0
        self.vq_bits = 0
        self.num_pca = 0


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


    def start(self,callback):
        self.callback=callback
        print("Starting capture")
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
        print("TERMINATED SUCCESSFULLY")

    # Function to handle each packet
    def handle_packet_sniff(self,packet):
        sender = bytes_to_mac(list(bytes(packet["UDP"].payload))[4:10])
        #setup initial time
        if self.start_time == 0:
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

    #function to sniff packets. You sniff from wlan0 but you can potentially read a PCAP file
    def collector_function(self):
        if self.capture_mode == "LIVE":
            #sniff(iface=self.iface,filter="udp port 5500", prn=self.handle_packet_sniff, store=0, stop_filter=lambda x: not self.run_collection)
            sniff(opened_socket = self.listen_socket, prn=self.handle_packet_sniff, store=0, stop_filter=lambda x: not self.run_collection)
        #sniff(offline="test.pcap",filter="udp port 5500", prn=self.handle_packet_sniff, store=0, stop_filter=lambda x: not self.run_collection)
        elif self.capture_mode == "PCAP":
            sniff(offline=self.input_pcap,filter="udp port 5500", prn=self.handle_packet_sniff, store=0, stop_filter=lambda x: not self.run_collection)
       
    
    #function to process the queue of windows
    def processor_function(self):
        #wait for new windows, or terminate
        while self.run_processing:
            #keep going until you have new windows to process
            while len(self.window_queue) > 0:
                win = self.window_queue.pop(0)

                res = win.process(self.subcarriers,verbose = self.verbose,type = self.proc_type)
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

    def set_subcarriers(self, subcarriers = nonnull_subcarriers):
        self.subcarriers = subcarriers

    def set_devices(self, devices):
        self.devices = [d.lower() for d in devices]
        
    def set_callback(self, callback):
        self.callback = callback

    def set_verbose(self, verbose):
        self.verbose = verbose

    def set_proc_type(self, proc_type):
        self.proc_type = proc_type

    def configure(self, devices = None, win_duration = None,proc_type = None, capture_mode = None,input_pcap = None, sq_bits = None, vq_bits = None, num_pca = None):
        print(devices,win_duration,proc_type,capture_mode,input_pcap)
        if devices is not None:
            self.devices = devices
        if win_duration is not None:
            self.win_duration = win_duration
        if proc_type is not None:
            self.proc_type = proc_type
        if capture_mode is not None:
            self.capture_mode = capture_mode
        if input_pcap is not None:
            self.input_pcap = input_pcap
        if sq_bits is not None:
            self.sq_bits = sq_bits
        if vq_bits is not None:
            self.vq_bits = vq_bits
        if num_pca is not None:
            self.num_pca = num_pca

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
                "sq_bits":self.sq_bits,"vq_bits":self.vq_bits,"num_pca":self.num_pca
                }

