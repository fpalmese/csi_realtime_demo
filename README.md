This repo contains the code for a Realtime CSI Sniffer and Visualizer, part of the Demo paper accepted at EWSN 2025:
- F. Palmese, A. E. C. Redondi, M. Cesana:"Demo: On-the-fly Extraction and Compression of Network Traffic Traces for Efficient IoT Forensics", EWSN 2025

# Architecture
The system is composed of three components:
- A Rasberry Pi collecting the CSI Samples
- A Python GUI
- IoT devices communicating using Wi-Fi
- An MQTT broker

# System Overview
The CSI values are collected in the Raspberry Pi using the Nexmon CSI tool.
- The capture is controlled through the Python GUI and the two components communicate with MQTT (the broker can be anywhere)
- When the capture is started, the nexmon csi tool starts and the raspberry runs a python script for realtime collection/aggregation/compression of CSI values.
- Compressed entries are transmitted to the Python GUI using UDP for fast and low-latency data streams.
- The GUI visualizes the compressed CSI samples

# GUI Example
The following image shows the GUI with an example of realtime visualization:
<img width="1608" height="758" alt="image" src="https://github.com/user-attachments/assets/d2c8c03f-d139-4b99-985f-ec840dc6f11e" />

# Configuration
- You need to install the nexmon CSI tool in the Raspberry Pi
- You need to configure the MQTT broker address in the GUI program and in the Raspberry Pi mqtt_subscriber.py program
