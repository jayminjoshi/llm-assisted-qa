# Use Python 3.10 slim image
FROM python:3.10-slim

# Check for required ENV variable and set it
ARG ENV
RUN if [ -z "$ENV" ]; then \
    echo "ERROR: ENV build argument is required. Use --build-arg ENV=your_env_value" && \
    exit 1; \
fi

ENV ENV=$ENV

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    ca-certificates \
    openssl \
    libssl-dev \
    chromium \
    chromium-driver \
    libwoff1 \
    libvpx7 \
    libevent-2.1-7 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    flite1-dev \
    libwebp7 \
    libwebpdemux2 \
    libwebpmux3 \
    libharfbuzz-icu0 \
    libenchant-2-2 \
    libhyphen0 \
    libmanette-0.2-0 \
    x264 \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome environment variables
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PYTHONUNBUFFERED=1

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install

# Copy application code
COPY app/ ./app/

# Set environment variables
ENV PYTHONPATH=/app

# Command to run the application
WORKDIR /app/app
CMD ["python", "main.py"]