# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Create a non-root user
RUN useradd -m -r -s /bin/bash appuser

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install yt-dlp and gallery-dl
RUN pip install --no-cache-dir yt-dlp gallery-dl

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/downloads /app/logs && \
    chown -R appuser:appuser /app/downloads /app/logs && \
    chmod 755 /app/downloads /app/logs

# Set environment variables
ENV DOWNLOAD_DIR=/app/downloads \
    FLASK_APP=app.py \
    PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Run the application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300", "app:app"] 