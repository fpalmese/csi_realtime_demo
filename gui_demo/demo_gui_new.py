from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QComboBox, QLineEdit, QSpinBox, QCheckBox, QFileDialog, QGroupBox, QFrame, QDoubleSpinBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
import random
import paho.mqtt.client as mqtt
from utils.qtgauge import QTGauge
from threading import Thread
import json,ast
import time
from queue import Queue
from csi_data_handler import data_receive, data_process
import threading

gui_size = (620, 600)

win_style = """
QPushButton {
    background-color: #5E81AC;
    border-radius: 8px;
    padding: 8px 16px;
}
QPushButton:hover {
    background-color: #81A1C1;
}
QPushButton:pressed {
    background-color: #3B4252;
}
"""
hostname = "192.168.2.224"
broker_addr= (hostname,1883)
udp_server_addr = (hostname, 12345)


available_pcaps = ["capture1.pcap", "capture2.pcap"]
available_devices = ["90:9A:4A:61:A2:6E"]
mqtt_topics = ["running_status"]

class MQTTClient:
    def __init__(self, broker_addr=("localhost", 1883), topics=mqtt_topics, callback=None):
        self.client = mqtt.Client()
        self.broker_addr = broker_addr
        self.client.on_connect = self.on_connect
        self.topics = topics
        self.client.on_disconnect = self.on_disconnect
        self.client.on_connect_fail = self.on_disconnect
        self.client.on_socket_close = self.on_disconnect
        self.connected = False
        
        if callback:
            self.client.on_message = callback
            
    def run(self):
        self.client.connect(self.broker_addr[0], self.broker_addr[1], 60)
        print("MQTT Client connected")
        #self.client.loop_forever() #loop_start()
        self.client.loop_start() #loop_start()
        
    def on_connect(self, client, userdata, flags, rc):
        self.connected = True
        # Subscribe to the topic
        self.client.subscribe([(t, 0) for t in self.topics])
        
    def is_connected(self):
        return self.connected

    # if client disconnects set to false
    def on_disconnect(self, client, userdata, rc=0):
        self.connected = False

    def send_msg(self, topic, payload):
        self.client.publish(topic, payload)

    def terminate(self):
        self.client.disconnect()
        self.client.loop_stop()

class DemoGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSI Sniffer")
        self.setFixedSize(*gui_size)
        # read from file winStyle.css
        #with open("style.css", "r") as f:
        #    win_style = f.read()
        self.setStyleSheet(win_style)

        # Variables
        self.config = {
            "connected": False,
            "capture_mode": "LIVE",
            "pcap_file": "",
            "band": "2.4",
            "bandwidth": "20",
            "status": "disconnected",
            "win_duration": 1.0,
            "devices":["90:9A:4A:61:A2:6E"],
            "pca_enabled":True,
            "pca_num":1,
            "sq_enabled":True,
            "sq_bits":1,
            "vq_enabled":True,
            "vq_bits":1,
            "pcap_speed":2
        }

        self.init_ui()
        
        self.toggle_pcap_mode()
        self.toggle_live_mode()
        self.toggle_sq()
        self.toggle_vq()
        self.toggle_pca()

        self.available_pcaps = available_pcaps
        self.available_devices = available_devices

        # set favicon
        self.setWindowIcon(QIcon("c:/Users/fabio/Ricerca/Codice/Demo 2025/eusipco_demo/favicon.ico"))

    def init_ui(self):
        main_layout = QVBoxLayout()

        # Header
        header = QLabel("CSI Sniffer with CSI-PRESS")
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)
        horiz_line = QFrame()
        horiz_line.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(horiz_line)
        
        # Status
        status_layout = QHBoxLayout()
        status_label_desc = QLabel("STATUS:")
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold")
        status_layout.addStretch()
        status_layout.addWidget(status_label_desc)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)
        
        # Refresh button
        refresh_btn_line = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        #self.refresh_btn.clicked.connect(self.refresh_status)
        refresh_btn_line.addStretch()
        refresh_btn_line.addWidget(self.refresh_btn)
        refresh_btn_line.addStretch()
        main_layout.addLayout(refresh_btn_line)

        # --- Settings Frame ---
        settings_layout = QHBoxLayout()

        # Capture Settings
        capture_group = QGroupBox("Capture Settings")
        capture_group.setFixedWidth(int(self.width() * 0.58))
        capture_group.setFixedHeight(220)
        capture_layout = QVBoxLayout()

        mode_layout = QHBoxLayout()
        self.live_radio = QRadioButton("Live")
        self.live_radio.setChecked(True)
        self.live_radio.toggled.connect(self.toggle_live_mode)
        self.pcap_radio = QRadioButton("PCAP")
        self.pcap_radio.toggled.connect(self.toggle_pcap_mode)
        mode_layout.addWidget(QLabel("Capture mode:"))
        mode_layout.addWidget(self.live_radio)
        mode_layout.addWidget(self.pcap_radio)
        mode_layout.addStretch()
        capture_layout.addLayout(mode_layout)

        # PCAP frame
        self.pcap_layout = QHBoxLayout()
        self.pcap_layout.addWidget(QLabel("PCAP file:"))
        self.pcap_name = QComboBox()
        self.pcap_name.addItems(available_pcaps)
        self.pcap_layout.addWidget(self.pcap_name)
        
        self.pcap_layout.addWidget(QLabel("Speed:"))
        self.pcap_speed = QComboBox()
        self.pcap_speed.addItem("1x", 1)
        self.pcap_speed.addItem("2x", 2)
        self.pcap_speed.addItem("4x", 4)
        self.pcap_speed.addItem("10x", 10)
        self.pcap_layout.addWidget(self.pcap_speed)

        capture_layout.addLayout(self.pcap_layout)

        # Band settings
        self.live_layout = QHBoxLayout()
        self.live_layout.addWidget(QLabel("Band:"))
        self.band_cb = QComboBox()
        self.band_cb.addItem("2.4 GHz", 2.4)
        self.band_cb.addItem("5 GHz", 5.0)
        self.band_cb.currentTextChanged.connect(self.update_bandwidth_and_channel_options)
        self.live_layout.addWidget(self.band_cb)
        self.live_layout.addWidget(QLabel("Bandwidth:"))
        self.bandwidth_cb = QComboBox()
        self.bandwidth_cb.addItems(["20", "40"])
        self.bandwidth_cb.currentTextChanged.connect(self.update_bandwidth_and_channel_options)
        self.live_layout.addWidget(self.bandwidth_cb)
        self.live_layout.addWidget(QLabel("Channel:"))
        self.channel_cb = QComboBox()
        self.live_layout.addWidget(self.channel_cb)
        capture_layout.addLayout(self.live_layout)

        # Aggregation window
        agg_layout = QHBoxLayout()
        agg_layout.addWidget(QLabel("Aggregation window (s):"))
        self.agg_spin = QDoubleSpinBox()
        self.agg_spin.setSingleStep(0.05)
        self.agg_spin.setDecimals(2)
        self.agg_spin.setRange(0.1, 10)
        self.agg_spin.setValue(1)
        agg_layout.addWidget(self.agg_spin)
        capture_layout.addLayout(agg_layout)

        # Device selection
        dev_layout = QHBoxLayout()
        dev_layout.addWidget(QLabel("Device:"))
        self.device_cb = QComboBox()
        self.device_cb.addItems(available_devices)
        dev_layout.addWidget(self.device_cb)
        capture_layout.addLayout(dev_layout)

        
        upd_cpt_btn_line = QHBoxLayout()
        self.upd_cpt_btn = QPushButton("Update")
        upd_cpt_btn_line.addStretch()
        upd_cpt_btn_line.addWidget(self.upd_cpt_btn)
        upd_cpt_btn_line.addStretch()
        capture_layout.addLayout(upd_cpt_btn_line)
        
        capture_group.setLayout(capture_layout)
        settings_layout.addWidget(capture_group)
        


        # Compression Settings
        comp_group = QGroupBox("Compression Settings")
        comp_group.setFixedHeight(capture_group.height())
        comp_layout = QVBoxLayout()

        #SQ
        comp_layout.addWidget(QLabel("Value-based"))
        horiz_line = QFrame()
        horiz_line.setFrameShape(QFrame.Shape.HLine)
        comp_layout.addWidget(horiz_line)

        sq_row = QHBoxLayout()
        self.sq_chk = QCheckBox("Scalar Quantization")
        self.sq_chk.toggled.connect(self.toggle_sq)
        sq_row.addWidget(self.sq_chk)
        self.sq_pop_box = QHBoxLayout()
        self.sq_pop_box.addWidget(QLabel("Bits:"))
        self.sq_input = QComboBox()
        self.sq_input.addItems(["1","2","4","8","16"])
        self.sq_pop_box.addWidget(self.sq_input)
        sq_row.addLayout(self.sq_pop_box)
        comp_layout.addLayout(sq_row)

        #VQ
        comp_layout.addWidget(QLabel("Vector-based"))
        horiz_line = QFrame()
        horiz_line.setFrameShape(QFrame.Shape.HLine)
        comp_layout.addWidget(horiz_line)
        
        vq_row = QHBoxLayout()
        self.vq_chk = QCheckBox("Vector Quantization")
        self.vq_chk.toggled.connect(self.toggle_vq)
        vq_row.addWidget(self.vq_chk)
        self.vq_pop_box = QHBoxLayout()
        self.vq_pop_box.addWidget(QLabel("Bits:"))
        self.vq_input = QComboBox()
        self.vq_input.addItems(["1","2","4","8","16"])
        self.vq_pop_box.addWidget(self.vq_input)
        vq_row.addLayout(self.vq_pop_box)
        comp_layout.addLayout(vq_row)

        #PCA
        pca_row = QHBoxLayout()
        self.pca_chk = QCheckBox("PCA")
        self.pca_chk.toggled.connect(self.toggle_pca)
        pca_row.addWidget(self.pca_chk)
        self.pca_pop_box = QHBoxLayout()
        self.pca_pop_box.addWidget(QLabel("Components:"))
        self.pca_input = QComboBox()
        self.pca_input.addItems([str(i) for i in range(2,66,2)])
        self.pca_pop_box.addWidget(self.pca_input)
        pca_row.addLayout(self.pca_pop_box)
        comp_layout.addLayout(pca_row)

        upd_comp_btn_line = QHBoxLayout()
        self.upd_comp_btn = QPushButton("Update")
        upd_comp_btn_line.addStretch()
        upd_comp_btn_line.addWidget(self.upd_comp_btn)
        upd_comp_btn_line.addStretch()
        comp_layout.addLayout(upd_comp_btn_line)


        comp_group.setLayout(comp_layout)
        settings_layout.addWidget(comp_group)
        main_layout.addLayout(settings_layout)

        
        # Gauge Frame
        gauge_group = QGroupBox("Storage Overview (daily)")
        gauge_layout = QHBoxLayout()
        gauge_width = int(self.width() / 3.5)
        self.pcap_gauge = QTGauge(title="PCAP Size", unit="MB",max_value=1000)
        self.feature_gauge = QTGauge(title="Feature Size", unit="KB",max_value=1000)
        self.compressed_gauge = QTGauge(title="Compressed", unit="KB",max_value=1000)
        self.pcap_gauge.setFixedSize(gauge_width, gauge_width)
        self.feature_gauge.setFixedSize(gauge_width, gauge_width)
        self.compressed_gauge.setFixedSize(gauge_width, gauge_width)

        gauge_layout.addWidget(self.pcap_gauge)
        gauge_layout.addWidget(self.compressed_gauge)
        gauge_layout.addWidget(self.feature_gauge)
        gauge_group.setLayout(gauge_layout)
        main_layout.addWidget(gauge_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setMaximumWidth(100)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMaximumWidth(100)
        btn_layout.addWidget(self.stop_btn)

        main_layout.addLayout(btn_layout)



        self.setLayout(main_layout)
        self.update_bandwidth_and_channel_options()

    def toggle_live_mode(self):
        visible = self.live_radio.isChecked()
        for i in range(self.live_layout.count()):
            widget = self.live_layout.itemAt(i).widget()
            if widget is not None:
                widget.setVisible(visible)
    
    def toggle_pcap_mode(self):
        visible = not self.live_radio.isChecked()
        for i in range(self.pcap_layout.count()):
            widget = self.pcap_layout.itemAt(i).widget()
            if widget is not None:
                widget.setVisible(visible)

    def update_bandwidth_and_channel_options(self):
        band = self.band_cb.currentText()
        bw = self.bandwidth_cb.currentText()
        channels = []
        if band == "2.4 GHz":
            if bw == "20":
                channels = [str(ch) for ch in range(1, 15)]
            else:
                channels = [str(ch) for ch in range(3, 12)]
        else:
            if bw == "20":
                channels = [str(ch) for ch in range(36, 165, 4)]
            elif bw == "40":
                channels = [str(ch) for ch in range(38, 163, 8)]
            else:
                channels = ["42", "58", "106", "122", "138", "155"]
        self.channel_cb.clear()
        self.channel_cb.addItems(channels)
        
    def toggle_sq(self):
        chk = self.sq_chk.isChecked()
        index = self.sq_input.currentIndex()
        if chk:
            self.sq_input.setCurrentIndex(index if index != -1 else 0)
        else:
            self.sq_input.setCurrentIndex(-1)
            
        for i in range(self.sq_pop_box.count()):
            widget = self.sq_pop_box.itemAt(i).widget()
            if widget is not None:
                widget.setEnabled(chk)

    def toggle_vq(self):
        chk = self.vq_chk.isChecked()
        index = self.vq_input.currentIndex()
        if chk:
            self.vq_input.setCurrentIndex(index if index != -1 else 0)
            # disable pca chk
            self.pca_chk.setChecked(False)
        else:
            self.vq_input.setCurrentIndex(-1)
        # disable edit of vq_pop_box
        for i in range(self.vq_pop_box.count()):
            widget = self.vq_pop_box.itemAt(i).widget()
            if widget is not None:
                widget.setEnabled(chk)
                
    def toggle_pca(self):
        chk = self.pca_chk.isChecked()
        index = self.pca_input.currentIndex()
        if chk:
            self.pca_input.setCurrentIndex(index if index != -1 else 0)
            # disable vq chk
            self.vq_chk.setChecked(False)
        else:
            self.pca_input.setCurrentIndex(-1)
            
        # disable edit of pca pop box
        for i in range(self.pca_pop_box.count()):
            widget = self.pca_pop_box.itemAt(i).widget()
            if widget is not None:
                widget.setEnabled(chk)

    def update_status_label(self, text,color="black"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold")
        
    def update_gui_status(self,status):
        if status:
            self.update_status_label("Running","green")
            self.set_storage_data(0,0,0)
            self.disable_gui(disable_compression=False,disable_time=False)
        else:
            self.update_status_label("Stopped","red")
            self.enable_gui()
            
    def update_gui(self,config):
        
        if not config:
            self.mark_offline()
            self.set_running_app(False)

        '''config = {"duration":0.5, "cap_mode":"LIVE", "proc_type":1,"devices":4, "channel": 1, "band":2.4, "bandwidth":20}'''
        self.update_gui_status(config.get("status",False))

        #update live/pcap mode
        cap_mode = config.get("capture_mode","LIVE")
        if  cap_mode == "LIVE":
            self.live_radio.setChecked(True)
            self.pcap_radio.setChecked(False)
            
            #update values for band, bandwidth and channel
            band_value = str(config.get("band", 2.4)) + " GHz"
            index = self.band_cb.findText(band_value)
            if index != -1:
                self.band_cb.setCurrentIndex(index)
            bw_value = str(config.get("bandwidth", 20))
            index = self.bandwidth_cb.findText(bw_value)
            if index != -1:
                self.bandwidth_cb.setCurrentIndex(index)
            ch_value = str(config.get("channel", 1))
            index = self.channel_cb.findText(ch_value)
            if index != -1:
                self.channel_cb.setCurrentIndex(index)

        elif cap_mode == "PCAP":
            self.pcap_radio.setChecked(True)
            #update pcap file input
            self.pcap_name.setCurrentText(config.get("input_pcap",""))
        
        # update available pcapsd
        if "pcap_files" in config:
            self.pcap_name.clear()
            self.available_pcaps = config["pcap_files"]
            self.pcap_name.addItems(self.available_pcaps)

        if "available_devices" in config:
            self.device_cb.clear()
            self.available_devices = config["available_devices"]
            self.device_cb.addItems(self.available_devices)

        if "device_select" in config:
            dev_index = int(config.get("device_select", 1)) - 1
            self.device_cb.setCurrentIndex(dev_index)
            
        print(config)
        if "pcap_speed" in config:
            text_value = str(config.get("pcap_speed", 2))+"x"
            self.pcap_speed.setCurrentText(text_value)

        # aggregation window
        self.agg_spin.setValue(config.get("win_duration", 1))

        #SQ
        self.sq_chk.setChecked(config.get("sq_enabled", False))
        sq_bits = str(config.get("sq_bits", "1"))
        self.sq_input.setCurrentText(sq_bits)
        
        #VQ
        self.vq_chk.setChecked(config.get("vq_enabled", False))
        vq_bits = str(config.get("vq_bits", 1))
        index = self.vq_input.findText(vq_bits)
        if index != -1:
            self.vq_input.setCurrentIndex(index)
        #PCA
        self.pca_chk.setChecked(config.get("pca_enabled", False))
        pca_num = str(config.get("pca_num", 2))
        index = self.pca_input.findText(pca_num)
        if index != -1:
            self.pca_input.setCurrentIndex(index)

        self.toggle_live_mode()
        self.toggle_pcap_mode()

    def disable_gui(self,disable_compression=True,disable_time = True):
        # disable all elements in the gui except stop button
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        self.pcap_radio.setEnabled(False)
        self.live_radio.setEnabled(False)
        self.band_cb.setEnabled(False)
        self.bandwidth_cb.setEnabled(False)
        self.channel_cb.setEnabled(False)
        self.pcap_name.setEnabled(False)
        self.device_cb.setEnabled(False)
        
        if disable_time:
            self.agg_spin.setEnabled(False)
        
        if disable_compression:
            self.sq_chk.setEnabled(False)
            self.sq_input.setEnabled(False)
            self.vq_chk.setEnabled(False)
            self.vq_input.setEnabled(False)
            self.pca_chk.setEnabled(False)
            self.pca_input.setEnabled(False)
            

    def enable_gui(self):
        # enable all elements in the gui
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.upd_comp_btn.setEnabled(True)
        self.upd_cpt_btn.setEnabled(True)
        
        self.pcap_radio.setEnabled(True)
        self.live_radio.setEnabled(True)
        self.band_cb.setEnabled(True)
        self.bandwidth_cb.setEnabled(True)
        self.channel_cb.setEnabled(True)
        self.pcap_name.setEnabled(True)
        self.device_cb.setEnabled(True)
        self.agg_spin.setEnabled(True)
        
        self.sq_chk.setEnabled(True)
        self.vq_chk.setEnabled(True)
        self.pca_chk.setEnabled(True)
        self.sq_input.setEnabled(True)
        self.vq_input.setEnabled(True)
        self.pca_input.setEnabled(True)

        self.toggle_sq()
        self.toggle_vq()
        self.toggle_pca()
    
    def mark_offline(self,message="SNIFFER OFFLINE"):
        self.disable_gui()
        self.update_status_label(message,"red")
        self.stop_btn.setEnabled(False)
        self.upd_comp_btn.setEnabled(False)
        self.upd_cpt_btn.setEnabled(False)

    def fix_storage_unit(self,size):
        unit = "KB"
        if size > 1024*1024:
            unit = "GB"
            size = size / (1024*1024)
        elif size > 1024:
            size = size / 1024
            unit = "MB"
        return size, unit

    def set_storage_data(self,pcap_size=None,feature_size=None,comp_size=None):
        if pcap_size is not None:
            size, unit = self.fix_storage_unit(pcap_size)
            self.pcap_gauge.set_unit(unit)
            self.pcap_gauge.set_value(size)
            
        if feature_size is not None:
            size, unit = self.fix_storage_unit(feature_size)
            self.feature_gauge.set_unit(unit)
            self.feature_gauge.set_value(size)
            
        if comp_size is not None:
            size, unit = self.fix_storage_unit(comp_size)
            self.compressed_gauge.set_unit(unit)
            self.compressed_gauge.set_value(size)

    def get_configs(self):
        configs = {}
        configs["duration"] = float(self.agg_spin.value())
        configs["proc_type"] = 2
        configs["cap_mode"] = "LIVE" if self.live_radio.isChecked() else "PCAP"
        configs["devices"] = int(self.device_cb.currentIndex()) + 1
        configs["pcap_speed"] = int(self.pcap_speed.currentData())
        
        if configs["cap_mode"] == "LIVE":
            configs["band"] = float(self.band_cb.currentData())
            configs["bandwidth"] = int(self.bandwidth_cb.currentText())
            configs["channel"] = int(self.channel_cb.currentText())
        else:
            configs["input_pcap"] = self.pcap_name.currentText()
        
        configs["sq_enabled"] = self.sq_chk.isChecked()
        if configs["sq_enabled"]:
            configs["sq_bits"] = int(self.sq_input.currentText())
            
        configs["vq_enabled"] = self.vq_chk.isChecked()
        if configs["vq_enabled"]:
            configs["vq_bits"] = int(self.vq_input.currentText())
            
        configs["pca_enabled"] = self.pca_chk.isChecked()
        if configs["pca_enabled"]:
            configs["pca_num"] = int(self.pca_input.currentText())

        return configs
    
    def get_compression_configs(self):
        configs = {}
        configs["sq_enabled"] = self.sq_chk.isChecked()
        if configs["sq_enabled"]:
            configs["sq_bits"] = int(self.sq_input.currentText())

        configs["vq_enabled"] = self.vq_chk.isChecked()
        if configs["vq_enabled"]:
            configs["vq_bits"] = int(self.vq_input.currentText())

        configs["pca_enabled"] = self.pca_chk.isChecked()
        if configs["pca_enabled"]:
            configs["pca_num"] = int(self.pca_input.currentText())
        return configs
    
class DemoApp():
    def __init__(self,broker_addr=broker_addr,udp_server_addr=udp_server_addr):
        self.mqtt_client = MQTTClient(broker_addr=broker_addr,callback=self.on_message)
        self.app = QApplication([])
        self.gui = DemoGUI()
        self.mqtt_thread = None #for gui controls
        self.data_rx_thread = None #for receiving data from nexmon
        self.data_processor_thread = None #for data processing from queue
        self.last_online = 0
        self.aggregation_window = 0
        self.pcap_speed = 2
        self.capture_mode = "LIVE"
        self.compression_settings = {}
        self.setup_gui_listeners()

        # for threads
        self.data_queue = Queue()        
        self.running = threading.Event()
        
        
    def setup_gui_listeners(self):
        # link refresh button
        self.gui.refresh_btn.clicked.connect(self.refresh_status)
        self.gui.start_btn.clicked.connect(self.start_capture)
        self.gui.stop_btn.clicked.connect(self.stop_capture)
        self.gui.upd_cpt_btn.clicked.connect(self.update_csi_realtime)
        self.gui.upd_comp_btn.clicked.connect(self.update_compression)

    def run(self):
        self.mqtt_thread = Thread(target=self.mqtt_client.run)
        self.mqtt_thread.start()
        #self.data_rx_thread = Thread(target=data_receive, args=(udp_server_addr,self.data_queue,self.active,))
        #self.data_rx_thread.start()

        #self.data_processor_thread = Thread(target=data_process, args=(self.data_queue,self.running))
        #self.data_processor_thread.start()

        time.sleep(0.1)
        self.refresh_status()
        self.gui.show()
        self.app.exec()

        #terminate client
        self.terminate()
        

    def on_message(self,client, userdata, message):
        
        if message.topic == "running_status":
            try:
                payload = message.payload.decode("utf-8")
            except:
                payload = ""
            # parse json with ast
            if payload == "" and time.time() - self.last_online > 1:
                self.gui.mark_offline()
                self.set_running_app(False)
                return
            try:
                config = json.loads(payload)
            except Exception as e:
                return
            self.last_online = time.time()
            
            # update app stuff
            self.aggregation_window = config.get("win_duration",1)
            self.capture_mode = config.get("capture_mode","LIVE")
            self.compression_settings = {
                "sq_enabled":config.get("sq_enabled",False),
                "sq_bits":int(config.get("sq_bits",1)),
                "vq_enabled":config.get("vq_enabled",False),
                "vq_bits":int(config.get("vq_bits",1)),
                "pca_enabled":config.get("pca_enabled",False),
                "pca_num":int(config.get("pca_num",1))
            }
            self.pcap_speed = config.get("pcap_speed",2)
            
            self.set_running_app(config.get("status",False))
            
            # update gui
            self.gui.update_gui(config)
            #print(config)

    def refresh_status(self):
        if not self.mqtt_client.is_connected():
            self.gui.mark_offline("SERVER OFFLINE")
            self.set_running_app(False)
            return
        self.mqtt_client.send_msg("get_current_status", "")

        # set a timer of 0.5s, when it fires if last_online is null then return
        QTimer.singleShot(1000, self.check_last_online)

    def check_last_online(self):
        if self.last_online is None or time.time() - self.last_online > 1:
            print(self.last_online)
            self.gui.mark_offline()
            self.set_running_app(False)

    def start_capture(self):
        configs = self.gui.get_configs()
        self.aggregation_window = configs.get("duration",1.0)
        self.pcap_speed = configs.get("pcap_speed",2)
        self.capture_mode = configs.get("cap_mode","LIVE")
        
        print("STARTING CAPTURE WITH CONFIGS:", configs)
        self.mqtt_client.send_msg("start_csi_realtime", json.dumps(configs))
        self.gui.update_gui_status(True)
        self.set_running_app(True)
        
    def stop_capture(self):
        self.mqtt_client.send_msg("stop_csi_realtime", "realtime")
        self.gui.update_gui_status(False)
        self.set_running_app(False)
    
    def set_running_app(self,status=True):
        # app already in correct running status
        if status == self.running.is_set():
            return 

        if status:
            self.running.set()
            self.data_rx_thread = Thread(target=data_receive, args=(udp_server_addr,self.data_queue,self.running))
            self.data_rx_thread.start()
        
            show_gt = self.capture_mode == "PCAP"
            self.data_processor_thread = Thread(target=data_process, args=(self.data_queue,self.running,self.update_storage_info,show_gt))
            self.data_processor_thread.start()
            
        else:
            self.running.clear()
            self.data_queue.put("")
            if self.data_rx_thread:
                try:
                    self.data_rx_thread.join()
                except Exception as e:
                    pass
                self.data_rx_thread = None
                
            if self.data_processor_thread:
                try:
                    self.data_processor_thread.join()
                except Exception as e:
                    pass
                self.data_processor_thread = None

    def update_csi_realtime(self):
        # if started you can only update aggr window
        if self.running.is_set():
            self.update_aggregation_window()
        else:
            capt_configs = self.gui.get_configs()
            self.mqtt_client.send_msg("save_csi_realtime",json.dumps(capt_configs))
            self.compression_settings = self.gui.get_compression_configs()

    def update_aggregation_window(self):
        agg_val = float(self.gui.agg_spin.value())
        pcap_speed = int(self.gui.pcap_speed.currentData())

        agg_changed = (agg_val != float(self.aggregation_window))
        pcap_speed_changed = (pcap_speed != self.pcap_speed)
        
        # both changed
        if agg_changed and pcap_speed_changed:
            self.mqtt_client.send_msg("set_pcap_speed_duration",json.dumps({"duration":agg_val,"pcap_speed":pcap_speed}))
            self.aggregation_window = agg_val
            self.pcap_speed = pcap_speed

        elif agg_changed:
            self.mqtt_client.send_msg("set_csi_duration",str(agg_val))
            self.aggregation_window = agg_val
        
        elif pcap_speed_changed:
            self.mqtt_client.send_msg("set_pcap_speed",str(pcap_speed))
            self.pcap_speed = pcap_speed

    def update_compression(self):
        configs = self.gui.get_compression_configs()
        self.mqtt_client.send_msg("set_compression", json.dumps(configs))
        self.compression_settings = configs
        
    def terminate(self):
        self.set_running_app(False)
        self.mqtt_client.terminate()
        
        self.mqtt_thread.join()
        
        time.sleep(0.1)
        print("START")
        if self.data_rx_thread:
            print("killing data_rx")
            self.data_rx_thread.join()
            print("killed data_rx")
            
        if self.data_processor_thread:
            print("killing data_px")
            self.data_processor_thread.join()
            print("killed data_px")

        print("END")

    def update_storage_info(self, num_packets, num_carriers):
        # update the daily computation

        sq_enabled = self.compression_settings.get("sq_enabled", False)
        vq_enabled = self.compression_settings.get("vq_enabled", False)
        pca_enabled = self.compression_settings.get("pca_enabled", False)
        pck_rate = num_packets / self.aggregation_window  # packets per second
        pcap_rate = 32 * pck_rate * num_carriers # bps
        pcap_size = pcap_rate * 86400 / (8*1024) # KB

        if sq_enabled or vq_enabled or pca_enabled:
            comp_rate = pck_rate
            if vq_enabled:
                comp_rate = comp_rate * self.compression_settings.get("vq_bits",1)
            elif pca_enabled:
                comp_rate = comp_rate * self.compression_settings.get("pca_num",1)
            else:
                comp_rate = comp_rate * num_carriers
            
            if sq_enabled:
                comp_rate = comp_rate * self.compression_settings.get("sq_bits",1)
            else:
                comp_rate = comp_rate * 32
        else:
            comp_rate = pcap_rate
        comp_size = comp_rate * 86400 / 8192  # in KB
        feature_size = ((86400 / self.aggregation_window)*32 )/ (8192)  # in KB
        #print(pcap_size, feature_size, comp_size)
        self.gui.set_storage_data(pcap_size, feature_size, comp_size)

if __name__ == "__main__":
    """
    app = QApplication([])
    gui = DemoGUI()
    gui.show()
    config = {"duration":0.5, "cap_mode":"LIVE", "proc_type":2,"devices":4, "channel": 1, "band":2.4, "bandwidth":20}
    app.exec()
    """
    
    
    demo_app = DemoApp()
    demo_app.run()
