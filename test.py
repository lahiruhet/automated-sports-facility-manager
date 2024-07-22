import tinytuya

# Connect to Device
d = tinytuya.OutletDevice(
    dev_id='',
    address='Auto',
    local_key="", 
    version=3.4)

# Get Status
data = d.status() 
print('set_status() result %r' % data)

# Turn On
d.turn_on()

# Turn Off
d.turn_off()
