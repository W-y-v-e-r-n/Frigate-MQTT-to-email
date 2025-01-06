# Frigate-MQTT-to-email

This project consists of an MQTT to Email service that listens for specific MQTT events
and sends emails with snapshots when those events occur. 
It also includes an Email Listener service that listens for incoming emails requesting
video clips and responds with the requested clips.

## Project Structure

```plaintext
mqtt-email-project/
├── mqtt-to-email/
│   ├── Dockerfile
│   ├── mqtt-to-email.py
├── email-listener/
│   ├── Dockerfile
│   ├── email_listener.py
├── scheduler-web-server/
│   ├── templates/
│   │   └── index.html
│   ├── Dockerfile
│   ├── scheduler_web_server.py
├── mosquitto/
│   ├── config/
│   │   └── mosquitto.conf
│   ├── data/
│   ├── log/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── README.md
├── LICENSE
└── docker-compose.yml
```

## Features

- MQTT to Email Service: Listens for specific MQTT events and sends an email with a snapshot when the event occurs.
- Email Listener Service: Listens for incoming emails requesting video clips and responds with the requested clips.
- Scheduler -web-server provides a GUI for scheduling and managing email notifications.
- Mosquitto MQTT Broker: Serves as the MQTT broker for the project.

## Prerequisites

- Docker
- Docker Compose
- A Gmail account for sending and receiving emails
- Frigate server for event detection

## Environment Variables

Ensure you have the following environment variables set in the docker-compose.yml file for mqtt-to-email and email-listener services:

- **MQTT_BROKER**: The MQTT broker address
- **MQTT_PORT**: The MQTT broker port (default: 1883)
- **MQTT_TOPIC**: The MQTT topic to subscribe to
- **EMAIL_ADDRESS**: Your Gmail address
- **EMAIL_PASSWORD**: Your Gmail password
- **EMAIL_RECIPIENT**: The recipient email address
- **FRIGATE_HOST**: The Frigate server host
- **FRIGATE_PORT**: The Frigate server port (default: 5001)
- **EVENT_TYPE**: Comma-separated list of event types to filter (e.g., person, cat)
- **CAMERAS**: Comma-separated list of cameras to filter (e.g., Front, Back, Door) or "ALL" for all cameras

## Functions

### MQTT to Email Service
The mqtt-to-email service listens for events on the specified MQTT topic. When an event of the specified type (e.g., person) occurs,
it sends an email with a snapshot of the event.

###Email Listener Service
The email-listener service listens for incoming emails with the subject "Send Clip". When such an email is received,
it extracts the event ID from the email body, retrieves the corresponding video clip from the Frigate server, and responds with the clip attached.

## Scheduler Web Server

It is a Flask-based web application that provides a GUI for scheduling and managing email notifications. It uses MQTT for communication with other services, such as `mqtt-to-email`.

### Usage
Once the services are up and running, you can access the web interface at http://localhost:5000.

- Set Schedule: Use the form to choose days and specify start and end times for email notifications.
- Toggle Email Sending: Enable or disable email notifications.
- Snooze Notifications: Temporarily disable email notifications for a specified duration.
