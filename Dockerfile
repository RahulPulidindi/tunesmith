FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements-docker.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for Flask sessions
RUN mkdir -p ./flask_session

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application
CMD ["python", "main.py"] 