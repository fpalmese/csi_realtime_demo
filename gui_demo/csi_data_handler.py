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
from screeninfo import get_monitors
from matplotlib import gridspec
#screen_resolution:
monitors = get_monitors()
screen_res = (min(m.width for m in monitors), min(m.height for m in monitors))

image_dpi = 100
plot_sizes = [(14, 4.5), (14, 5.5)]


grid_color = (40, 40, 40)  # light gray
grid_color = (10, 10, 10)  # light gray

# adapted sizes
min_csi_val = 0
max_csi_val = 8000

#csi spectrum settings
#spectrum_x_axis_len = 300 # size of image
align_csi = False
color_map_name = "viridis"  # "viridis" "plasma" "inferno" "magma" "cividis" "twilight" "twilight_shifted" "hsv"
subcarriers = list(range(-32,32))
csi_aggr_fun = "mean"

# plot settings
shift_csi_aggr = True
x_observe_period = 60
guard_seconds = 0
show_gt = True
legend_position = 1
plot_size = (20, 7)
font_size = 16


def adapt_sizes(screen_res):
    global image_dpi,plot_sizes
    if screen_res == (1920,1080):
        print("Using 1920x1080 resolution")
        image_dpi = 80
        plot_sizes = [(14, 4.5), (14, 7.2)]
    
    elif screen_res == (2880,1800):
        print("Using 2880x1800 resolution")
        image_dpi = 140
        plot_sizes = [(14, 4.5), (14, 6.4)]

adapt_sizes(screen_res)
    
    
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

import matplotlib.pyplot as plt


def init_macro_image(color_map):
    plot_size1 = plot_sizes[0]
    plot_size2 = plot_sizes[1]

    fig = plt.figure(figsize=(plot_size1[0], plot_size1[1]+plot_size2[1]), dpi=image_dpi)

    # create a 2-row, 2-column grid (last column reserved for colorbar)
    gs = gridspec.GridSpec(2, 2, width_ratios=[40, 1], height_ratios=[plot_size1[1], plot_size2[1]], figure=fig,wspace=0.05)

    # main plots
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0])

    # colorbar axis (aligned with ax2)
    cax = fig.add_subplot(gs[1, 1])

    ax1.set_title("CSI Aggregate Value")

    # Example: attach colormap image to ax2
    empty_matrix = np.zeros((x_observe_period, 64))  # replace with actual data
    im = ax2.imshow(empty_matrix, cmap=color_map, vmin=0, vmax=1,
              aspect='auto', extent=[0, x_observe_period, 64, 0])
    fig.colorbar(im, cax=cax)

    macro_image = plt_to_image(fig)

    return fig, (ax1, ax2), macro_image



def plt_to_image(fig):
    fig.canvas.draw()
    img = np.frombuffer(fig.canvas.get_renderer().buffer_rgba(), dtype=np.uint8)
    img = img.reshape(fig.canvas.get_width_height()[::-1] + (4,))
    img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    plt_image = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    #plt_image = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    #plt_image = cv2.resize(plt_image, (plot_image_size[0], plot_image_size[1]), interpolation=cv2.INTER_AREA)
    return plt_image

def adapt_matrix_duration_change(matrix,old_unit,new_unit):
    if old_unit == new_unit:
        return matrix

    factor = int(round(old_unit / new_unit))

    if factor > 1:
        matrix = np.repeat(matrix, factor, axis=1)
    return matrix


def matrix_to_image(ax,matrix, color_map, show_grid_x=True, show_grid_y=True):
    n_rows, n_cols = matrix.shape
    
    # extent matches matrix dimensions
    ax.imshow(matrix, cmap=color_map, vmin=0, vmax=1,
              aspect='auto', extent=[0, n_cols, n_rows, 0])

    #ax.set_position([0, 0, 1, 1])  # fill whole figure
    # labels
    ax.set_ylabel("Subcarriers", fontsize=font_size)
    if show_grid_x:
        ax.set_xticks(np.arange(n_cols+1))   # grid lines at cell edges
        ax.xaxis.grid(True, color=np.array(grid_color)/255, linestyle='--', linewidth=0.5)
        ax.set_xticklabels([])  # hide labels

    if show_grid_y:
        ax.set_yticks(np.arange(n_rows+1))
        ax.yaxis.grid(True, color=np.array(grid_color)/255, linestyle='--', linewidth=0.5)
        y_ticks_labels = range(-32, 32, 4)
        ax.set_yticklabels([str(i) if i in y_ticks_labels else "" for i in range(-32,33)], va='top')  # set label position to bottom
    return ax

def data_process(data_queue,enable=threading.Event(), gui_callback = None,show_gt=False):
    #plot part
    
    #spectrum part
    last_matrix = None
    color_map = cm.get_cmap(color_map_name)
    #csi_spectrum_image = init_csi_image(color_map)
    aggr_window = 1
    window_unit = None #associated to each col in the image
    last_csi_time = 0
    
    #init macro figure (all white)
    current_fig, current_axes, macro_image = init_macro_image(color_map)

    #empty image of macro size
    all_csi_aggr = []
    all_times = []

    
    def update_image(current_ax, win_time, np_matrix, win_duration):
        nonlocal last_matrix, aggr_window, window_unit, last_csi_time
        current_ax.clear()
        if window_unit is None:
                window_unit = win_duration
        if win_duration != aggr_window:
            aggr_window = win_duration
            
            new_window_unit = np.round(np.gcd(int(round(window_unit*20)), int(round(aggr_window*20)))/20, 2) # MCD, la cadenza è a 0.05
            if last_matrix is not None and window_unit != new_window_unit:
                last_matrix = adapt_matrix_duration_change(last_matrix, window_unit,new_window_unit)
            window_unit = new_window_unit
            
        if last_matrix is None:
            matrix_len = int(round(x_observe_period / window_unit))
            last_matrix = np.zeros((np_matrix.shape[1], matrix_len))
            
        n_units = int(round(aggr_window / window_unit))
        
        #scroll per window
        scroll_n = int(round((win_time - last_csi_time) / win_duration))  
        last_matrix = np.roll(last_matrix, -scroll_n*n_units, axis=1)
        if csi_aggr_fun == "mean":
            to_append = np_matrix.transpose().mean(axis=1).repeat(n_units, axis=1)
        elif csi_aggr_fun == "std":
            to_append = np_matrix.transpose().std(axis=1).repeat(n_units, axis=1)
        #print("MAX:",to_append.max(),"MIN:",to_append.min(),"SIZE:",to_append.shape,"unit:",window_unit)
        last_matrix[:,-n_units:] = to_append
        
        #update last_csi_time
        last_csi_time = win_time

        # get min/max per row
        min_csi = np.where(last_matrix == 0, np.inf, last_matrix).min(axis=1, keepdims=True)
        min_csi = np.nan_to_num(min_csi, nan=0.0, posinf=0.0, neginf=0.0)
        max_csi = last_matrix.max(axis=1, keepdims=True)
        # normalize per row        
        norm_matrix = (last_matrix - min_csi) / (max_csi - min_csi)
        norm_matrix = np.nan_to_num(norm_matrix, nan=0.0, posinf=0.0, neginf=0.0)
        
        to_display_matrix = norm_matrix[:,:-n_units] if align_csi else norm_matrix
        matrix_to_image(current_ax, to_display_matrix, color_map, show_grid_x=(window_unit>=0.5))   
        
    

    def update_image_aggr(current_ax, times,csi_aggrs):
        min_x = times[-1]-x_observe_period - guard_seconds
        max_x = times[-1] + guard_seconds
        current_ax.clear()
        current_ax.plot(times, csi_aggrs, label="CSI Aggregate", marker='o',ms=5)
        current_ax.autoscale(enable=True, axis='x', tight=False)
        
        gt_xs = get_gt(min_x, max_x) if show_gt else []
        for i, gt_val in enumerate(gt_xs):
            label = "Ground-Truth" if i == 0 else None
            current_ax.axvline(3 + gt_val, color='r', linestyle='--',lw=1,label=label)
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

        return current_ax
    
    def update_macro_image(win_time, np_matrix, win_duration, times, csi_aggrs):
        #fig, axes = plt.subplots(2,1,figsize=(macro_image_size[0]/100, macro_image_size[1]/100), dpi=100)
        update_image_aggr(current_axes[0], times, csi_aggrs)
        update_image(current_axes[1], win_time, np_matrix, win_duration)

        current_axes[0].set_title("CSI Aggregate Value", fontsize=font_size+5,pad=10)
        current_axes[0].set_xlabel("Time (s)",fontsize=font_size)
        current_axes[1].xaxis.set_ticks_position("top")
        # Move the title to the bottom of the plot
        current_axes[1].set_xlabel("CSI Amplitude Spectrum", fontsize=font_size+5, labelpad=30)
        return plt_to_image(current_fig)
    
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
                csi_aggr = float(json_data.get("csi_aggr", 0))
                all_csi_aggr.append(csi_aggr)
                all_times.append(win_time + (win_duration*shift_csi_aggr))
                
                if gui_callback is not None:
                    gui_callback(np_matrix.shape[0], np_matrix.shape[1])
                                
                macro_image = update_macro_image(win_time, np_matrix, win_duration, all_times, all_csi_aggr)
                
            except json.JSONDecodeError as e:
                print("Error decoding JSON:", e)
                continue
            
        
        # Show the captured image
        if macro_image is not None:
            cv2.imshow("Real-time monitor",macro_image)
            
        # wait for the key and come out of the loop
        cv2.waitKey(10)
        
    cv2.destroyAllWindows()
    print("END OF PX THREAD")
    