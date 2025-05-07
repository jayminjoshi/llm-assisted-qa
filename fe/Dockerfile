FROM python:3.10

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
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port 8501 for Streamlit - For documentation purposes
EXPOSE 8501

# Set up entrypoint
ENTRYPOINT ["streamlit", "run"]

# Set default command
CMD ["main.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.fileWatcherType=None", "--server.maxUploadSize=100"] 