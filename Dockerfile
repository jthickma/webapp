# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV DOWNLOAD_DIR /app/downloads

# Install system dependencies required by yt-dlp/gallery-dl (adjust as needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Create the download directory
RUN mkdir -p ${DOWNLOAD_DIR} && chown -R www-data:www-data ${DOWNLOAD_DIR}

# Expose port 8000 for the Flask app
EXPOSE 8000

# Run app.py when the container launches using gunicorn (a production WSGI server)
# Use www-data user for better security
USER www-data
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"] 