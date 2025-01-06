FROM python:3.9-slim

WORKDIR /app

# Install the required Python packages directly
RUN pip install --no-cache-dir requests

COPY email_listener.py .

CMD ["python", "email_listener.py"]
