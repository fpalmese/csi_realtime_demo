
module("luci.controller.admin.csi_realtime",package.seeall)
rootDirectory = "/home/forensics"

-- BROKER PARAMS
broker_address = "192.168.2.224"
start_topic = "start_csi_realtime"
stop_topic = "stop_csi_realtime"
duration_topic = "set_csi_duration"
-- ------------------------

--filesDirectory = "/mnt/sda1/testDirectory"
filesDirectory = tostring(luci.sys.exec("cat "..rootDirectory.."/init/baseDirectory")):gsub("\n", "")

function index()
	entry({"admin", "forensics", "forensics","csi_realtime"}, template("forensics/csi_realtime"), ("CSI Real-Time")).leaf = true	
	entry({"admin", "forensics", "forensics","csi_start_realtime"},call("handle_start_csi_realtime"),nil)
	entry({"admin", "forensics", "forensics","csi_stop_realtime"},call("handle_stop_csi_realtime"),nil)
	entry({"admin", "forensics", "forensics","csi_update_realtime_duration"},call("handle_update_duration"),nil)
end

function sleep(n)
  os.execute("sleep " .. tonumber(n))
end


function handle_start_csi_realtime()
	-- publish on topic start to start the capture with the chosen configuration

	local win_duration = luci.http.formvalue("win-duration")
	local cap_mode = luci.http.formvalue("capture-mode")
	local proc_type = luci.http.formvalue("processing-type")
	local devices = luci.http.formvalue("device-select")
	
	local json_res = '{"duration":'..win_duration..', "cap_mode":"'..cap_mode..'", "proc_type":'..proc_type..',"devices":'..devices..'}'
	
	luci.sys.call("mosquitto_pub -h "..broker_address.." -t "..start_topic.." -m '"..json_res.."'")
	
	luci.http.prepare_content("application/json")	--prepare the Http response
	luci.http.write_json("Capture Started")

end

function handle_stop_csi_realtime()
	-- publish on topic start to start the capture with the chosen configuration
	luci.sys.call("mosquitto_pub -h "..broker_address.." -t "..stop_topic.." -m realtime")
	
	luci.http.prepare_content("application/json")	--prepare the Http response
	luci.http.write_json("Capture started")

end


function handle_update_duration()
	-- publish on topic start to start the capture with the chosen configuration

	local win_duration = luci.http.formvalue("win-duration")	
	luci.sys.call("mosquitto_pub -h "..broker_address.." -t "..duration_topic.." -m "..win_duration)
	
	luci.http.prepare_content("application/json")	--prepare the Http response
	luci.http.write_json("Duration Updated")

end

