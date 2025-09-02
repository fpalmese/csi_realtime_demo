from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM,timeout
import sys
import cv2
import numpy as np
from matplotlib import cm
import matplotlib
matplotlib.use("Agg")   # headless, no GUI
import json
import threading
from matplotlib import pyplot as plt
import random 

#macro-image:
macro_image_size = (2000,1500)
csi_spectrum_size = (1550,750)
plot_image_size = (2000, 700)
csi_x_shift = 250

min_csi_val = 0
max_csi_val = 200

#csi spectrum settings
#spectrum_x_axis_len = 300 # size of image
align_csi = False
color_map_name = "viridis"

# plot settings
shift_csi_aggr = True
x_observe_period = 90
guard_seconds = 0
show_gt = True
legend_position = 1
plot_size = (20, 7)
font_size = 16


def get_gt(min_time, max_time):
    if min_time < 0:
        min_time = 0
    if max_time < 0:
        max_time = 0
    gt_vals = [30,60]
    gt_period = 68.339591
    cycles_min = int(min_time / gt_period)
    cycles_max = int(max_time / gt_period)

    # gt is true for x=30,60, 30+gt_period, 60+gt_period, 30+2*gt_period, 60+2*gt_period, ...
    # show all gts in range min_time max_time
    return [(x + cycles * gt_period) for x in gt_vals for cycles in range(cycles_min, cycles_max + 1)]

# producer thread
def data_receive_udp(udp_server_addr, data_queue, enable = threading.Event()):
    # udp listener main function
    udp_socket = socket(AF_INET, SOCK_DGRAM)
    udp_socket.settimeout(3)
    udp_connected = False
    
    while (not udp_connected):
        udp_socket.sendto("CONNECT".encode("UTF-8"), udp_server_addr)
        try:
            msg, _ = udp_socket.recvfrom(2048)
            if msg.decode("UTF-8") == "CONNACK":
                udp_connected = True
        except (timeout, ConnectionResetError):
            print("UDP Server unavailable")
            sys.exit(0)
            return
        finally:
            udp_socket.settimeout(1)
    
    while enable.is_set():
        try:
            new_data, _ = udp_socket.recvfrom(10000000)
            data_queue.put(new_data.decode("UTF-8"))
            print("RX")
        except Exception as e:
            continue
    udp_socket.close()
    print("END OF RX THREAD")


# producer thread
def data_receive(tcp_server_addr, data_queue, enable = threading.Event()):
    # tcp listener main function
    tcp_socket = socket(AF_INET, SOCK_STREAM)
    tcp_socket.settimeout(3)
    tcp_connected = False

    while (not tcp_connected):
        try:
            tcp_socket.connect(tcp_server_addr)
            tcp_connected = True
            tcp_socket.settimeout(1)
        except Exception as e:
            print("TCP Server unavailable: ",e)
            sys.exit(0)
            return
        
    buffer = ""
    while enable.is_set():
        try:
            #new_data = tcp_socket.recv(10000000)
            chunk = tcp_socket.recv(10000000).decode("utf-8")
            if not chunk:
                continue
            buffer += chunk
            while "\n" in buffer:
                msg, buffer = buffer.split("\n", 1)
                data_queue.put(msg)
        except Exception as e:
            continue
    
    tcp_socket.close()
    print("END OF RX THREAD")

def init_plot():
    fig = plt.figure(figsize=plot_size, dpi=200)
    ax = fig.add_subplot(111)
    plt.text(0.5, 0.5, "Initializing...", fontsize=font_size, ha='center', va='center')
    return fig, ax
def init_csi_image(color_map):
    image = ((color_map(np.zeros((csi_spectrum_size[1], csi_spectrum_size[0])))[:, :, :3]) * 255).astype(np.uint8)
    # add "Initalizing" text in image
    cv2.putText(image, "Initializing...", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    return image

def plt_to_image(fig):
    fig.canvas.draw()
    img = np.frombuffer(fig.canvas.get_renderer().buffer_rgba(), dtype=np.uint8)
    img = img.reshape(fig.canvas.get_width_height()[::-1] + (4,))
    img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    plt_image = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    plt_image = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    plt_image = cv2.resize(plt_image, (plot_image_size[0], plot_image_size[1]), interpolation=cv2.INTER_AREA)
    return plt_image

def adapt_matrix_duration_change(matrix,old_unit,new_unit):
    if old_unit == new_unit:
        return matrix
    
    factor = int(old_unit / new_unit)
    
    if factor > 1:
        matrix = np.repeat(matrix, factor, axis=1)
    return matrix

def data_process(data_queue,enable=threading.Event(), gui_callback = None,show_gt=False):
    #plot part
    current_fig, current_ax = init_plot()
    plt.grid()
    plt_image = plt_to_image(current_fig)
    
    #spectrum part
    last_matrix = None
    color_map = cm.get_cmap(color_map_name)
    csi_spectrum_image = init_csi_image(color_map)
    aggr_window = 1
    window_unit = None #associated to each col in the image
    last_csi_time = 0
    
    #init global figure (all white)
    to_show_image = 255*np.ones((macro_image_size[1], macro_image_size[0], 3), np.uint8)

    #empty image of macro size
    all_csi_aggr = []
    all_times = []

    def update_image(win_time, np_matrix, win_duration):
        nonlocal last_matrix, aggr_window, window_unit, last_csi_time
        if window_unit is None:
                window_unit = aggr_window
        if win_duration != aggr_window:
            aggr_window = win_duration
            new_window_unit = np.round(np.gcd(int(window_unit*20), int(aggr_window*20))/20, 2) # MCD, la cadenza è a 0.5
            #new_window_unit = np.round(np.lcm(int(window_unit*20), int(aggr_window*20))/20, 2) #MCM, la cadenza è a 0.5
            if last_matrix is not None and window_unit != new_window_unit:
                last_matrix = adapt_matrix_duration_change(last_matrix, window_unit,new_window_unit)
            window_unit = new_window_unit
        if last_matrix is None:
            matrix_len = int(x_observe_period / window_unit)
            last_matrix = np.zeros((np_matrix.shape[1], matrix_len))
            
        n_units = int(round(aggr_window / window_unit))
        
        #scroll per window
        scroll_n = int(round((win_time - last_csi_time) / win_duration))
        last_matrix = np.roll(last_matrix, -scroll_n*n_units, axis=1)
        to_append = np_matrix.transpose().std(axis=1).repeat(n_units, axis=1)
        last_matrix[:,-n_units:] = to_append
        
        norm_matrix = (last_matrix - min_csi_val) / (max_csi_val - min_csi_val)
        # all over the threshold is set to threshold
        
        
        # transform matrix to color_map (skip displaying last column (last window unit))
        to_display = norm_matrix[:,:-n_units] if align_csi else norm_matrix
        csi_spectrum_image = color_map(to_display)[:, :, :3]
        csi_spectrum_image = cv2.resize(csi_spectrum_image, (csi_spectrum_size[0], csi_spectrum_size[1]), interpolation=cv2.INTER_AREA)
        csi_spectrum_image = (csi_spectrum_image * 255).astype(np.uint8)
        
        last_csi_time = win_time
        return csi_spectrum_image
    
    def update_image_aggr(times,csi_aggrs):
        nonlocal current_fig, current_ax
        min_x = times[-1]-x_observe_period - guard_seconds
        max_x = times[-1] + guard_seconds
        
        current_ax.clear()
        current_ax.plot(times, csi_aggrs, label="CSI Aggr", marker='o',ms=8)
        current_ax.autoscale(enable=True, axis='x', tight=False)
        
        gt_xs = get_gt(min_x, max_x) if show_gt else []
        for i, gt_val in enumerate(gt_xs):
            label = "Ground-Truth" if i == 0 else None
            #current_ax.axvline(1.5 + gt_val, color='r', linestyle='--', label=label,lw=1)
            current_ax.axvline(3 + gt_val, color='r', linestyle='--',lw=1)
            #current_ax.axvline(4.5 + gt_val, color='r', linestyle='--',lw=1)
            # color a bit an area
            #current_ax.fill_betweenx(current_ax.get_ylim(), 1.5 + gt_val, 4.5 + gt_val, color='r', alpha=0.1)
            current_ax.axvspan(1.5 + gt_val, 4.5 + gt_val, color='r', alpha=0.1)

        #fix plot
        current_ax.legend(loc=legend_position,fontsize=font_size)
        current_ax.grid()
        current_ax.set_xlim(min_x, max_x)
        current_ax.tick_params(axis='both', which='major', labelsize=font_size)
        current_ax.tick_params(axis='both', which='minor', labelsize=font_size)

        plt_image = plt_to_image(current_fig)
        return plt_image
        
    while enable.is_set():
        # Fetch all available data from the queue
        while not data_queue.empty():
            new_data = data_queue.get()
            try:
                json_data = json.loads(new_data)
                matrix_received = json_data.get("data", [])
                win_duration = float(json_data.get("duration", 1.0))
                win_time = float(json_data.get("time", 0))
                np_matrix = np.matrix(matrix_received)
                if gui_callback is not None:
                    gui_callback(np_matrix.shape[0], np_matrix.shape[1])
                csi_spectrum_image = update_image(win_time,np_matrix, win_duration)
                
                csi_aggr = float(json_data.get("csi_aggr", 0))
                orig_csi_aggr = float(json_data.get("orig_csi_aggr", 0))
                print(win_time,csi_aggr)
                
                all_csi_aggr.append(csi_aggr)
                all_times.append(win_time + (win_duration*shift_csi_aggr))
                plt_image = update_image_aggr(all_times,all_csi_aggr)

                
            except Exception as e:
                print("Error decoding JSON:", e)
                continue
            
        
        # compose the to_show_image
        # upper part of the image is the plt_image
        if plt_image is not None:
            to_show_image[:plt_image.shape[0], :plt_image.shape[1]] = plt_image

        # lower part of the image is the csi_spectrum_image
        if csi_spectrum_image is not None:
            to_show_image[plt_image.shape[0]:plt_image.shape[0] + csi_spectrum_size[1],csi_x_shift:csi_x_shift+csi_spectrum_size[0]] = csi_spectrum_image
        # Show the captured image
        if to_show_image is not None:
            cv2.imshow("Real-time monitor",to_show_image)

        # wait for the key and come out of the loop
        cv2.waitKey(10)
        
    cv2.destroyAllWindows()
    print("END OF PX THREAD")
    