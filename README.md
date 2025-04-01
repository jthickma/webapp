# Universal Media Downloader

A web application for downloading media from various platforms including YouTube, Instagram, and TikTok.

## Features

- Download videos from YouTube, Instagram, and TikTok
- Rate limiting to prevent abuse
- Automatic file cleanup
- Progress tracking
- Secure file handling
- Docker support

## Prerequisites

- Docker and Docker Compose
- At least 2GB of RAM
- At least 10GB of disk space

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd universal-media-downloader
```

2. Create necessary directories:
```bash
mkdir -p downloads logs
```

3. Build and start the application:
```bash
docker-compose up -d
```

The application will be available at http://localhost:8000

## Usage

1. Open your web browser and navigate to http://localhost:8000
2. Paste the URL of the media you want to download
3. Click the download button
4. Wait for the download to complete
5. Click the download link for the file

## Rate Limits

- 10 downloads per minute per IP
- 30 file downloads per minute per IP
- Maximum file size: 500MB
- Maximum concurrent downloads: 5

## Security

- All files are automatically cleaned up after 7 days
- Files are served with proper permissions
- Rate limiting prevents abuse
- Input validation and sanitization
- Non-root user in container

## Logging

Logs are stored in the `logs` directory and are rotated when they reach 10MB.

## Troubleshooting

1. If downloads fail, check the logs:
```bash
docker-compose logs web
```

2. If the application is not accessible:
```bash
docker-compose ps
```

3. To restart the application:
```bash
docker-compose restart
```

## Development

To run the application in development mode:

```bash
python app.py
```

## License

MIT License 