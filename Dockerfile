FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn

# Copy codebase
COPY . .

# Port 7860 is the default web port for Hugging Face Spaces
EXPOSE 7860

# Start Unified Dashboard, Alpha Discovery Engine & Drip Submitter
CMD ["python", "app.py"]
