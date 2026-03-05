This repo contains the code for a Realtime CSI Sniffer and Visualizer

# Architecture
The system is composed of three components:
- A Rasberry Pi collecting the CSI Samples
- A Python GUI
- IoT devices communicating using Wi-Fi

# System Overview
The CSI values are collected in the Raspberry Pi using the Nexmon CSI tool.
- The capture is controlled through the Python GUI and the two components communicate with MQTT
- When the capture is started, the nexmon csi tool starts and the raspberry runs a python script for realtime collection/aggregation/compression of CSI values.
- Compressed entries are transmitted to the Python GUI using UDP for fast and low-latency data streams.
- The GUI visualizes the compressed CSI samples 
