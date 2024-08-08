import imaplib
import email
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import logging
import tinytuya
import schedule
from collections import defaultdict


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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

def setup_tuya_devices():
    devices = {}
    for court, info in DEVICES.items():
        try:
            device = tinytuya.BulbDevice(
                dev_id=info['id'],
                address=info['ip'],
                local_key=info['key'],
                version=3.4
            )
            device.set_version(3.4)
            devices[court] = device
            logging.info(f"Device set up for {court}")
        except Exception as e:
            logging.error(f"Error setting up device for {court}: {e}")
    return devices

def control_light(devices, courts_to_control, state):
    try:
        for court in courts_to_control:
            if state:
                devices[court].turn_on()
                logging.info(f"{court} light turned on at {datetime.now().strftime('%H:%M:%S')}")
            else:
                devices[court].turn_off()
                logging.info(f"{court} light turned off at {datetime.now().strftime('%H:%M:%S')}")
        
        # Always control Full Court light
        if state or 'Full Court' in courts_to_control:
            devices['Full Court'].turn_on()
            logging.info(f"Full Court light turned on at {datetime.now().strftime('%H:%M:%S')}")
        elif not state and 'Full Court' not in courts_to_control:
            # Check if any other court is still in use
            other_courts_status = [devices[c].status()['dps']['1'] for c in ['Half Court A', 'Half Court B'] if c not in courts_to_control]
            if not any(other_courts_status):
                devices['Full Court'].turn_off()
                logging.info(f"Full Court light turned off at {datetime.now().strftime('%H:%M:%S')}")
            else:
                logging.info(f"Full Court light remains on as other courts are still in use")
    except Exception as e:
        logging.error(f"Error controlling lights: {e}")

def connect_to_email(username, password, imap_server):
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(username, password)
    return mail

def get_latest_email(mail):
    mail.select('INBOX')
    _, search_data = mail.search(None, 'SUBJECT "CLC Basketball Hub - Latest daily booking schedule"')
    latest_email_id = search_data[0].split()[-1]
    _, data = mail.fetch(latest_email_id, '(RFC822)')
    raw_email = data[0][1]
    return email.message_from_bytes(raw_email)

def convert_to_24hr(time_str):
    time_obj = datetime.strptime(time_str, "%I:%M %p")
    return time_obj.strftime("%H:%M")

def extract_reservation_info(email_message):
    if email_message.is_multipart():
        for part in email_message.walk():
            if part.get_content_type() == "text/html":
                html_content = part.get_payload(decode=True).decode()
                break
    else:
        html_content = email_message.get_payload(decode=True).decode()

    soup = BeautifulSoup(html_content, 'html.parser')
    reservations = defaultdict(list)
    
    main_table = soup.find('table', {'width': '600', 'style': lambda value: value and 'background-color:#ffffff' in value})
    
    if main_table:
        for row in main_table.find_all('tr')[1:]:
            columns = row.find_all('td')
            if len(columns) >= 5:
                time_slot = columns[1].text.strip()
                court = columns[2].text.strip().rstrip('.')  # Remove trailing period
                payment_status = columns[4].text.strip()
                if time_slot and ':' in time_slot:
                    time_24hr = convert_to_24hr(time_slot)
                    if payment_status.lower() != 'recurring':
                        reservations[time_24hr].append(court)
    
    return reservations

def control_lights(devices, reservations):
    current_time = datetime.now()
    for reservation_time, courts in reservations.items():
        reservation_datetime = datetime.strptime(reservation_time, "%H:%M").replace(year=current_time.year, month=current_time.month, day=current_time.day)
        
        if reservation_datetime > current_time:
            wait_time = (reservation_datetime - current_time).total_seconds()
            logging.info(f"Waiting for {wait_time} seconds until next reservation at {reservation_time}")
            time.sleep(wait_time)
            
            courts_to_control = set(courts)
            if 'Full Court' in courts_to_control:
                courts_to_control = {'Half Court A', 'Half Court B', 'Full Court'}
            
            control_light(devices, courts_to_control, True)
            logging.info(f"Reservation started at {reservation_time} for {', '.join(courts_to_control)}")
            
            # Keep the lights on for 1 hour
            time.sleep(3600)
            
            # Check if there's another reservation immediately after
            next_reservation_time = (reservation_datetime + timedelta(hours=1)).strftime("%H:%M")
            if next_reservation_time not in reservations:
                control_light(devices, courts_to_control, False)
                logging.info(f"No immediate follow-up reservation. Lights turned off at {next_reservation_time}")
            else:
                logging.info(f"Another reservation follows at {next_reservation_time}. Keeping lights on.")
        
        current_time = datetime.now()  # Update current time for next iteration
    
    logging.info("All reservations for today have been processed")

def daily_routine():
    logging.info("Starting daily routine")
    devices = setup_tuya_devices()
    if not devices:
        logging.error("Failed to set up devices. Exiting.")
        return

    # Email credentials
    username = ''
    password = ''
    imap_server = ''

    try:
        mail = connect_to_email(username, password, imap_server)
        email_message = get_latest_email(mail)
        reservations = extract_reservation_info(email_message)
        mail.logout()

        logging.info("Reservations for today:")
        for time, courts in reservations.items():
            logging.info(f"Time: {time}, Courts: {', '.join(courts)}")

        control_lights(devices, reservations)
    except Exception as e:
        logging.error(f"An error occurred during the daily routine: {e}")

def main():
    # Run the daily routine immediately when the script starts
    daily_routine()
    
    # Schedule the daily routine to run at 6:10 AM
    schedule.every().day.at("05:10").do(daily_routine)

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()