import imaplib
import email
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import logging
import tinytuya
import schedule
from collections import defaultdict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Tuya device setup
DEVICES = {
    'Half Court A': {
        'id': 'bf3a3ff7f0c70f8701jobw',
        'ip': 'Auto',  
        'key': "`b6E@}9^7p<F}9(]"  
    },
    'Half Court B': {
        'id': 'bfff0ed1cf8c979d8b5utr',
        'ip': 'Auto',  
        'key': "9pwqgEJ8jd}23njd"  
    },
    'Full Court': {
        'id': 'bff40a9463aaa2085aaxjf',
        'ip': 'Auto',
        'key': "!#!!/E~scf<GD^*D"
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

def control_light(devices, half_a_on, half_b_on, full_on):
    try:
        # Control Full Court light
        if full_on:
            devices['Full Court'].turn_on()
            logging.info("Full Court light turned on")
        else:
            devices['Full Court'].turn_off()
            logging.info("Full Court light turned off")

        # Control Half Court A light
        if half_a_on:
            devices['Half Court A'].turn_on()
            logging.info("Half Court A light turned on")
            devices['Full Court'].turn_on()
            logging.info("Full Court light turned on")
        else:
            devices['Half Court A'].turn_off()
            logging.info("Half Court A light turned off")

        # Control Half Court B light
        if half_b_on:
            devices['Half Court B'].turn_on()
            logging.info("Half Court B light turned on")
            devices['Full Court'].turn_on()
            logging.info("Full Court light turned on")
        else:
            devices['Half Court B'].turn_off()
            logging.info("Half Court B light turned off")
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
    
    # reservations = {'05:30': ['Half Court B'], '06:30': ['Half Court B', 'Half Court A'], '18:30': ['Half Court A'], '19:30': ['Full Court'], '20:30': ['Half Court B', 'Half Court A'], '21:30': ['Full Court']}
    return reservations

def control_lights(devices, reservations):
    off_start_time = datetime.now().replace(hour=7, minute=30, second=0, microsecond=0)
    off_end_time = datetime.now().replace(hour=17, minute=30, second=0, microsecond=0)

    for reservation_time, courts in reservations.items():
        reservation_datetime = datetime.strptime(reservation_time, "%H:%M").replace(year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)

        if off_start_time <= datetime.now() < off_end_time:
            logging.info("Current time is within the off period (07:30 - 17:30). Turning off all lights.")
            control_light(devices, False, False, False)
            
            # Wait until the off period ends
            wait_time = (off_end_time - datetime.now()).total_seconds()
            time.sleep(wait_time)
            logging.info(f"Off period ended. Resuming reservation processing.")

        if reservation_datetime > datetime.now():
            control_light(devices, False, False, False)
            wait_time = (reservation_datetime - datetime.now()).total_seconds()
            logging.info(f"Waiting for {wait_time} seconds until next reservation at {reservation_time}")
            time.sleep(wait_time)

        # Determine which lights should be on for this reservation
        half_a_on = 'Half Court A' in courts or 'Full Court' in courts
        half_b_on = 'Half Court B' in courts or 'Full Court' in courts
        full_on = 'Full Court' in courts

        # Control the lights based on the current reservation needs
        control_light(devices, half_a_on, half_b_on, full_on)

        logging.info(f"Reservation started at {reservation_time} for {', '.join(courts)}")

        end_time = reservation_datetime + timedelta(minutes=75 if reservation_datetime.strftime("%H:%M") == "21:30" else 60)

        # Wait until the end of the current reservation
        while datetime.now() < end_time:
            time.sleep(60)

    logging.info("All reservations for today have been processed")
    # Turn off all lights after processing all reservations
    control_light(devices, False, False, False)

def daily_routine():
    logging.info("Starting daily routine")
    devices = setup_tuya_devices()
    if not devices:
        logging.error("Failed to set up devices. Exiting.")
        return

    # Email credentials
    username = 'lolchublighting@homecourt.lk'
    password = 'Smartlights123!'
    imap_server = 'mail.homecourt.lk'

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
    
    schedule.every().day.at("05:20").do(daily_routine)

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
