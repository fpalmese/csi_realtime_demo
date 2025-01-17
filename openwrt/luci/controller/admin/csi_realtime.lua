
module("luci.controller.admin.csi_realtime",package.seeall)
rootDirectory = "/home/forensics"

-- BROKER PARAMS
broker_address = "100.87.100.57"
start_topic = "start_csi_realtime"
stop_topic = "stop_csi_realtime"
save_topic = "save_csi_realtime"
duration_topic = "set_csi_duration"
get_current_status_topic = "get_current_status"
running_status_topic = "running_status"
-- ------------------------

--filesDirectory = "/mnt/sda1/testDirectory"
filesDirectory = tostring(luci.sys.exec("cat "..rootDirectory.."/init/baseDirectory")):gsub("\n", "")

function index()
	entry({"admin", "forensics", "forensics","csi_realtime"}, template("forensics/csi_realtime"), ("CSI Real-Time")).leaf = true	
	entry({"admin", "forensics", "forensics","csi_start_realtime"},call("handle_start_csi_realtime"),nil)
	entry({"admin", "forensics", "forensics","save_csi_realtime_config"},call("handle_save_realtime_config"),nil)
	entry({"admin", "forensics", "forensics","csi_stop_realtime"},call("handle_stop_csi_realtime"),nil)
	entry({"admin", "forensics", "forensics","csi_update_realtime_duration"},call("handle_update_duration"),nil)
	entry({"admin", "forensics", "forensics","get_current_params"},call("handle_get_current_params"),nil)
end

function sleep(n)
  os.execute("sleep " .. tonumber(n))
end

local function trim(inputstr)
	return (inputstr:gsub("^%s*(.-)%s*$", "%1"))
 end

local function build_config_json(http_form)
	local win_duration = http_form.formvalue("win-duration")
	local cap_mode = http_form.formvalue("capture-mode")
	local proc_type = http_form.formvalue("proc-type")
	local devices = http_form.formvalue("device-select")

	local json_res = '{"duration":'..win_duration..', "cap_mode":"'..cap_mode..'", "proc_type":'..proc_type..',"devices":'..devices
	
	if(cap_mode:upper()=="LIVE")then
		local band = http_form.formvalue("band")
		local bandwidth = http_form.formvalue("bandwidth")
		local channel = http_form.formvalue("channel")
	
		json_res = json_res..', "channel": '..channel..', "band":'..band..', "bandwidth":'..bandwidth

	elseif(cap_mode:upper() == "PCAP") then
		local input_pcap = http_form.formvalue("input-pcap")
		json_res = json_res..', "input_pcap": "'..input_pcap..'"'
	end
	
	json_res = json_res..'}'
	return json_res
end

function handle_start_csi_realtime()
	-- publish on topic start to start the capture with the chosen configuration
	local json_res = build_config_json(luci.http)
	res = luci.sys.exec("mosquitto_pub -h "..broker_address.." -t "..start_topic.." -m '"..json_res.."'")
	
	luci.http.prepare_content("application/json")	--prepare the Http response
	luci.http.write_json("Capture Started: "..json_res)

end

function handle_save_realtime_config()
	-- publish on topic save
	local json_res = build_config_json(luci.http)
	luci.sys.call("mosquitto_pub -h "..broker_address.." -t "..save_topic.." -m '"..json_res.."'")
	
	luci.http.prepare_content("application/json")	--prepare the Http response
	luci.http.write_json("Saved Config: "..json_res)

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

function handle_get_current_params()
	luci.sys.call("mosquitto_pub -h "..broker_address.." -t "..get_current_status_topic.." -m hey")
	local status = tostring(luci.sys.exec("mosquitto_sub -h "..broker_address.." -t "..running_status_topic.." -C 1 -W 1"))

	if(status=="")then
		luci.http.status(503,"Service Unavailable")
		luci.http.write_json("")
		return
	end
	luci.http.prepare_content("application/json")	--prepare the Http response
	luci.http.write_json(status)
end
