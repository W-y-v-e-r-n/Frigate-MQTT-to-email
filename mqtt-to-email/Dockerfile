# Dockerfile

FROM python:3.9-slim

# Install necessary packages
RUN apt-get update && apt-get install -y mosquitto-clients && \
    pip install paho-mqtt==1.6.1 requests  # Ensure we use the latest version

# Copy the Python script into the container
COPY mqtt_to_email.py /mqtt_to_email.py

# Run the Python script
CMD ["python", "/mqtt_to_email.py"]
