import logging
from flask import Flask, request, render_template, redirect, url_for, flash
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
import os
import json
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key'
scheduler = BackgroundScheduler()
scheduler.start()

# MQTT client configuration from environment variables
mqtt_broker = os.getenv('MQTT_BROKER', 'mqtt-broker')  # Default to 'mqtt-broker' if not set
mqtt_port = int(os.getenv('MQTT_PORT', 1883))
mqtt_topic = "scheduler/config"
notification_topic = "scheduler/notifications"

client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.debug("Connected to MQTT broker successfully")
    else:
        logging.error(f"Failed to connect to MQTT broker, return code {rc}")

def on_disconnect(client, userdata, rc):
    logging.warning(f"Disconnected from MQTT broker with result code {rc}")
    try:
        client.reconnect()
    except Exception as e:
        logging.error(f"Exception while reconnecting: {e}")

# Set up MQTT client callbacks
client.on_connect = on_connect
client.on_disconnect = on_disconnect

try:
    client.connect(mqtt_broker, mqtt_port, 60)
except Exception as e:
    logging.error(f"Failed to connect to MQTT broker: {e}")
    exit(1)

# Clear retained messages on the topic
client.publish(notification_topic, payload=None, retain=True)
logging.debug("Cleared retained messages on the notification topic")

# Start the MQTT client loop in a separate thread
client.loop_start()

# Global state variables
email_sending_enabled = True
snooze_end_time = None  # Stores the end time of the snooze period
schedule = {
    'monday': {'start_time': '00:00', 'end_time': '23:59'},
    'tuesday': {'start_time': '00:00', 'end_time': '23:59'},
    'wednesday': {'start_time': '00:00', 'end_time': '23:59'},
    'thursday': {'start_time': '00:00', 'end_time': '23:59'},
    'friday': {'start_time': '00:00', 'end_time': '23:59'},
    'saturday': {'start_time': '00:00', 'end_time': '23:59'},
    'sunday': {'start_time': '00:00', 'end_time': '23:59'}
}

day_mapping = {
    'mon': 'monday',
    'tue': 'tuesday',
    'wed': 'wednesday',
    'thu': 'thursday',
    'fri': 'friday',
    'sat': 'saturday',
    'sun': 'sunday'
}

def send_email():
    # Your email sending logic here
    pass

def publish_update(event_type, details):
    message = {
        'event_type': event_type,
        'details': details
    }
    try:
        result = client.publish(notification_topic, json.dumps(message), retain=True)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logging.error(f"Failed to publish message: {result}")
        else:
            logging.debug(f"Published {event_type} message with details: {details}")
    except Exception as e:
        logging.error(f"Exception while publishing message: {e}")

@app.route('/set_schedule_gui', methods=['POST'])
def set_schedule_gui():
    global schedule
    days = request.form.getlist('days')
    try:
        if not days:
            raise ValueError("At least one day must be selected.")

        new_schedule = schedule.copy()  # Copy the existing schedule

        for day in days:
            start_time = request.form.get(f'{day}_start_time')
            end_time = request.form.get(f'{day}_end_time')

            if not start_time or not end_time:
                raise ValueError("Start time and end time must be provided for each selected day.")

            start_hour, start_minute = start_time.split(':')
            end_hour, end_minute = end_time.split(':')

            # Add job to the scheduler
            scheduler.add_job(send_email, CronTrigger(day_of_week=day, hour=start_hour, minute=start_minute))

            # Save the schedule for the day with the full day name
            full_day_name = day_mapping[day]
            new_schedule[full_day_name] = {'start_time': start_time, 'end_time': end_time}

        # Update the global schedule and publish the update
        schedule = new_schedule
        publish_update("schedule_set", {
            'schedule': schedule
        })
        flash('Schedule set successfully!', 'success')
    except Exception as e:
        app.logger.error(f"Exception on /set_schedule_gui: {str(e)}")
        flash(f"Failed to set schedule: {str(e)}", 'danger')

    return redirect(url_for('index'))

@app.route('/toggle_email_sending_gui', methods=['POST'])
def toggle_email_sending_gui():
    global email_sending_enabled
    email_sending_enabled = not email_sending_enabled
    publish_update("email_sending_toggled", {
        'enabled': email_sending_enabled
    })
    flash(f"Email sending {'enabled' if email_sending_enabled else 'disabled'}.", 'success')
    return redirect(url_for('index'))

@app.route('/snooze_gui', methods=['POST'])
def snooze_gui():
    global snooze_end_time
    snooze_duration = int(request.form.get('cooldown_minutes', 60))
    snooze_end_time = datetime.utcnow() + timedelta(minutes=snooze_duration)
    logging.debug(f"Publishing snooze_set event with cooldown_minutes: {snooze_duration}")
    publish_update("snooze_set", {
        'cooldown_minutes': snooze_duration
    })
    flash(f"Email sending snoozed for {snooze_duration} minutes.", 'success')
    return redirect(url_for('index'))

@app.route('/clear_snooze', methods=['POST'])
def clear_snooze():
    global snooze_end_time
    snooze_end_time = None
    publish_update("snooze_set", {
        'cooldown_minutes': 0
    })
    flash('Snooze cleared, email sending enabled immediately.', 'success')
    return redirect(url_for('index'))

@app.route('/')
def index():
    global snooze_end_time, schedule
    # Calculate remaining snooze time in seconds
    remaining_snooze_time = None
    if snooze_end_time:
        remaining_snooze_time = int((snooze_end_time - datetime.utcnow()).total_seconds())  # Convert to seconds
        if remaining_snooze_time <= 0:
            remaining_snooze_time = None
            snooze_end_time = None

    # Define the current schedule
    current_schedule = {
        'days': schedule,
        'email_sending_enabled': email_sending_enabled,
        'remaining_snooze_time': remaining_snooze_time
    }
    return render_template('index.html', schedule=current_schedule)

if __name__ == '__main__':
    # Add logging configuration
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    app.run(host='0.0.0.0', port=5000)
