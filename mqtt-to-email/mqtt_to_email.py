import paho.mqtt.client as mqtt
import json
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import logging
import os
import time

# Set up logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG').upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

# MQTT settings
MQTT_BROKER = os.getenv('MQTT_BROKER')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_TOPIC = os.getenv('MQTT_TOPIC') #Frigate NVR events
NOTIFICATION_TOPIC = "scheduler/notifications" #scheduler_web_server notifications

# Email settings
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_RECIPIENT = os.getenv('EMAIL_RECIPIENT')

# Frigate settings
FRIGATE_HOST = os.getenv('FRIGATE_HOST')
FRIGATE_PORT = os.getenv('FRIGATE_PORT')

# Event type filter
EVENT_TYPE = os.getenv('EVENT_TYPE', 'person')

# Camera filter (comma-separated list of cameras or "ALL")
CAMERAS = os.getenv('CAMERAS', 'ALL').split(',')

# Track the last processed event IDs
last_event_ids = []

# Track snooze end time
snooze_end_time = None

# Email sending schedule and status
email_sending_enabled = True

# Default schedule: always send emails (24 hours a day, 7 days a week)
current_schedule = {
    "monday": {"start_time": "00:00", "end_time": "23:59"},
    "tuesday": {"start_time": "00:00", "end_time": "23:59"},
    "wednesday": {"start_time": "00:00", "end_time": "23:59"},
    "thursday": {"start_time": "00:00", "end_time": "23:59"},
    "friday": {"start_time": "00:00", "end_time": "23:59"},
    "saturday": {"start_time": "00:00", "end_time": "23:59"},
    "sunday": {"start_time": "00:00", "end_time": "23:59"},
}

# Log environment variables
logging.debug(f"MQTT_BROKER={MQTT_BROKER}")
logging.debug(f"MQTT_PORT={MQTT_PORT}")
logging.debug(f"MQTT_TOPIC={MQTT_TOPIC}")
logging.debug(f"EMAIL_ADDRESS={EMAIL_ADDRESS}")
logging.debug(f"EMAIL_RECIPIENT={EMAIL_RECIPIENT}")
logging.debug(f"FRIGATE_HOST={FRIGATE_HOST}")
logging.debug(f"FRIGATE_PORT={FRIGATE_PORT}")
logging.debug(f"EVENT_TYPE={EVENT_TYPE}")
logging.debug(f"CAMERAS={CAMERAS}")

def is_email_sending_allowed():
    global snooze_end_time, email_sending_enabled, current_schedule
    if snooze_end_time and time.time() < snooze_end_time:
        remaining_time = snooze_end_time - time.time()
        logging.info(f"Email sending is currently snoozed. Remaining time: {remaining_time:.2f} seconds")
        return False
    if not email_sending_enabled:
        logging.info("Email sending is currently DISABLED.")
        return False
    
    # Check if current time is within the scheduled time range
    current_time = time.strftime("%H:%M")
    current_day = time.strftime("%A").lower()
    day_schedule = current_schedule.get(current_day, {"start_time": "00:00", "end_time": "23:59"})

    # Check if current time is within the active time frame
    if not (day_schedule["start_time"] <= current_time <= day_schedule["end_time"]):
        schedule_str = ', '.join([f"{day.capitalize()} {times['start_time']} - {times['end_time']}" for day, times in current_schedule.items()])
        logging.info(f"Email sending is out of schedule range. Schedule: {schedule_str}")
        return False

    return True

def send_notification_email(event_type, details):
    subject = f"Scheduler Notification: {event_type}"
    body = f"Details: {details}"
    html = f"""
    <html>
        <body>
            <p>{body}</p>
        </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))
    msg.attach(MIMEText(html, 'html'))

    try:
        logging.debug("Attempting to send notification email...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, EMAIL_RECIPIENT, text)
        server.quit()
        logging.debug("Notification email sent successfully!")
    except Exception as e:
        logging.error(f"Failed to send notification email. Error: {e}")

def on_connect(client, userdata, flags, rc):
    logging.debug(f"Connected to MQTT broker with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    # Delayed subscription to avoid retained messages
    time.sleep(2)  # Adjust the sleep duration as needed
    client.subscribe(NOTIFICATION_TOPIC)
    logging.debug(f"Subscribed to topics: {MQTT_TOPIC}, {NOTIFICATION_TOPIC}")

def on_disconnect(client, userdata, rc):
    logging.warning(f"Disconnected from MQTT broker with result code {rc}")
    # Attempt to reconnect
    client.reconnect()

def on_message(client, userdata, msg):
    global last_event_ids, snooze_end_time, email_sending_enabled, current_schedule
    logging.debug(f"Received MQTT message on topic: {msg.topic}")

    # Handle empty payloads
    if not msg.payload:
        logging.debug("Received empty payload, ignoring message.")
        return

    if msg.topic == NOTIFICATION_TOPIC:
        payload = json.loads(msg.payload.decode('utf-8'))
        event_type = payload.get('event_type')
        details = payload.get('details')
        logging.info(f"Received notification: {event_type} - {details}")

        if event_type == "snooze_set":
            # Set the snooze end time
            cooldown_minutes = details.get('cooldown_minutes', 120)
            snooze_end_time = time.time() + cooldown_minutes * 60
            logging.info(f"Snoozed for {cooldown_minutes} minutes")

        elif event_type == "email_sending_toggled":
            email_sending_enabled = details.get('enabled', True)
            logging.info(f"Email sending enabled: {email_sending_enabled}")

        elif event_type == "schedule_set":
            # Update the current schedule
            new_schedule = details.get('schedule', {})
            if new_schedule:
                current_schedule.update(new_schedule)
                logging.info(f"Schedule set: {current_schedule}")

        send_notification_email(event_type, details)
    else:
        payload = json.loads(msg.payload.decode('utf-8'))

        event_id = payload['after']['id']
        camera_name = payload['after']['camera']
        event_label = payload['after']['label']

        logging.debug(f"Received message: {payload}")

        # Check if the camera sent the event is in the CAMERAS list
        if 'ALL' not in CAMERAS and camera_name not in CAMERAS:
            logging.debug(f"Camera '{camera_name}' is not in filter list '{CAMERAS}'. Ignoring event.")
            return

        # Check if the event label matches the filter
        if event_label != EVENT_TYPE:
            logging.debug(f"Event label '{event_label}' does not match filter '{EVENT_TYPE}'. Ignoring event.")
            return

        # Check if the event ID is in the list of last 10 processed IDs
        if event_id not in last_event_ids:
            last_event_ids.append(event_id)
            if len(last_event_ids) > 10:
                last_event_ids.pop(0)  # Keep only the last 10 event IDs

            # Ensure email sending is allowed before downloading the snapshot
            if is_email_sending_allowed() and payload['after']['has_snapshot']:
                snapshot_url = f"http://{FRIGATE_HOST}:{FRIGATE_PORT}/api/events/{event_id}/snapshot.jpg"
                logging.debug(f"Downloading image from {snapshot_url}")
                try:
                    response = requests.get(snapshot_url)
                    response.raise_for_status()
                    image = response.content
                    logging.debug("Image downloaded successfully")
                    send_email(event_id, camera_name, image)
                except Exception as e:
                    logging.error(f"Failed to download image. Error: {e}")
        else:
            logging.debug(f"Duplicate event ID {event_id} ignored.")

def send_email(event_id, camera_name, image):
    if not is_email_sending_allowed():
        logging.info("Email sending is currently disabled or snoozed.")
        return

    subject = f"Frigate Event on Camera: {camera_name}"
    body = f"Here is the snapshot for the event ID {event_id} from camera {camera_name}."
    html = f"""
    <html>
        <body>
            <p>{body}</p>
            <p><a href="mailto:{EMAIL_ADDRESS}?subject=Send%20Clip&body=Please%20send%20the%20clip%20for%20the%20event%20ID%20{event_id}%20detected%20on%20camera%20{camera_name}.">Request Clip</a></p>
        </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))
    msg.attach(MIMEText(html, 'html'))

    # Attach image
    try:
        image_attachment = MIMEImage(image)
        image_attachment.add_header('Content-Disposition', 'attachment; filename="snapshot.jpg"')
        msg.attach(image_attachment)
    except Exception as e:
        logging.error(f"Failed to attach image. Error: {e}")

    try:
        logging.debug("Attempting to send email...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, EMAIL_RECIPIENT, text)
        server.quit()
        logging.debug("Email sent successfully!")
    except Exception as e:
        logging.error(f"Failed to send email. Error: {e}")

if __name__ == "__main__":
    logging.debug(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        logging.error(f"Failed to connect to MQTT broker: {e}")
        exit(1)

    client.loop_forever()
