import imaplib
import email
from email.header import decode_header
import os
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import logging
import time

# Set up logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG').upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

# Email settings
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_RECIPIENT = os.getenv('EMAIL_RECIPIENT')

# Frigate settings
FRIGATE_HOST = os.getenv('FRIGATE_HOST')
FRIGATE_PORT = os.getenv('FRIGATE_PORT')

# IMAP settings
IMAP_SERVER = 'imap.gmail.com'

def check_incoming_emails():
    while True:
        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            mail.select('inbox')

            logging.debug("Started checking for new emails...")

            while True:
                logging.debug("Performing search for unread emails with subject 'Send Clip'")
                status, messages = mail.search(None, '(UNSEEN SUBJECT "Send Clip")')
                logging.debug(f"Search status: {status}")
                logging.debug(f"Search response: {messages}")

                email_ids = messages[0].split()
                logging.debug(f"Found {len(email_ids)} new email(s)")

                for e_id in email_ids:
                    res, msg_data = mail.fetch(e_id, '(RFC822)')
                    for response in msg_data:
                        if isinstance(response, tuple):
                            msg = email.message_from_bytes(response[1])
                            subject = decode_header(msg['Subject'])[0][0]
                            if isinstance(subject, bytes):
                                subject = subject.decode()
                            logging.debug(f"Email subject: {subject}")
                            
                            if subject == 'Send Clip':
                                body = extract_body(msg)
                                logging.debug(f"Email body: {body}")
                                
                                event_id = extract_event_id(body)
                                logging.debug(f"Extracted event ID: {event_id}")
                                
                                if event_id:
                                    send_clip_email(event_id)
                                    delete_email(mail, e_id)
                                else:
                                    logging.debug("Event ID not found in email body")

                # Reconnect after processing a batch of emails to avoid connection issues
                mail.close()
                mail.logout()
                time.sleep(15)  # Check for new emails every 15 seconds
                mail = imaplib.IMAP4_SSL(IMAP_SERVER)
                mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                mail.select('inbox')
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            time.sleep(15)  # Wait before attempting to reconnect

def extract_body(msg):
    logging.debug("Extracting body from email")
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if "attachment" not in content_disposition:
                if content_type == "text/plain":
                    return part.get_payload(decode=True).decode()
                elif content_type == "text/html":
                    return part.get_payload(decode=True).decode()
    else:
        return msg.get_payload(decode=True).decode()
    return ""

def extract_event_id(body):
    logging.debug("Extracting event ID from email body")
    lines = body.splitlines()
    for line in lines:
        if 'event ID' in line:
            # Extract the event ID using regex to ensure no extra text is included
            import re
            match = re.search(r'event ID ([\w.-]+)', line)
            if match:
                event_id = match.group(1)
                logging.debug(f"Found event ID in email body: {event_id}")
                return event_id
    return None

def send_clip_email(event_id):
    clip_url = f"http://{FRIGATE_HOST}:{FRIGATE_PORT}/api/events/{event_id}/clip.mp4"
    subject = f"Frigate Clip: Event {event_id}"
    body = f"Here is the clip for the event ID {event_id}."

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    # Attach clip
    try:
        logging.debug(f"Downloading clip from {clip_url}")
        response = requests.get(clip_url)
        response.raise_for_status()
        clip = response.content
        logging.debug("Clip downloaded successfully")
        clip_attachment = MIMEApplication(clip, Name="clip.mp4")
        clip_attachment.add_header('Content-Disposition', 'attachment; filename="clip.mp4"')
        msg.attach(clip_attachment)
    except Exception as e:
        logging.error(f"Failed to download clip. Error: {e}")

    try:
        logging.debug("Attempting to send email with clip...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, EMAIL_RECIPIENT, text)
        server.quit()
        logging.debug("Email sent successfully!")

        # Delete the sent email from the sent items
        delete_sent_email(subject)
    except Exception as e:
        logging.error(f"Failed to send email. Error: {e}")

def delete_sent_email(subject):
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select('"[Gmail]/Sent Mail"')  # Gmail's "Sent Mail" folder
        status, messages = mail.search(None, f'(SUBJECT "{subject}")')
        logging.debug(f"Search status: {status}")
        logging.debug(f"Search response: {messages}")

        email_ids = messages[0].split()
        for e_id in email_ids:
            mail.store(e_id, '+FLAGS', '\\Deleted')
        mail.expunge()
        mail.close()
        mail.logout()
        logging.debug(f"Deleted sent email with subject: {subject}")
    except Exception as e:
        logging.error(f"Failed to delete sent email. Error: {e}")

def delete_email(mail, e_id):
    try:
        mail.store(e_id, '+FLAGS', '\\Deleted')
        mail.expunge()
        logging.debug(f"Email with ID {e_id} deleted successfully")
    except Exception as e:
        logging.error(f"Failed to delete email with ID {e_id}. Error: {e}")

if __name__ == "__main__":
    check_incoming_emails()
