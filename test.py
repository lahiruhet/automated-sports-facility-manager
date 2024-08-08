import tinytuya


DEVICES = {
    'Half Court A': {
        'id': '',
        'ip': 'Auto',
        'key': ""
    },
    'Half Court B': {
        'id': '',
        'ip': 'Auto',
        'key': ""
    },
    'Full Court': {
        'id': '',
        'ip': 'Auto',
        'key': ""
    }
}


def check_device_status(name, device_info):
    print(f"\nChecking status for {name}:")
    

    device = tinytuya.OutletDevice(
        dev_id=device_info['id'],
        address=device_info['ip'],
        local_key=device_info['key'],
        version=3.4
    )
    

    status = device.status()
    if 'dps' in status and '1' in status['dps']:
        if status['dps']['1']:
            print(f'{name} is ON')
        else:
            print(f'{name} is OFF')
    else:
        print(f'Failed to retrieve status for {name}')


for name, info in DEVICES.items():
    check_device_status(name, info)
