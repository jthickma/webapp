from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import subprocess
import os
import re
import logging
import uuid
import stat
from datetime import datetime, timedelta
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Configure logging with rotation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(
            'app.log',
            maxBytes=1024 * 1024,  # 1MB
            backupCount=5
        )
    ]
)

# Constants
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/app/downloads")
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
MAX_CONCURRENT_DOWNLOADS = 5
FILE_CLEANUP_DAYS = 7
DOWNLOAD_TIMEOUT = 300  # 5 minutes

# Ensure DOWNLOAD_DIR is absolute and safe
DOWNLOAD_DIR = os.path.abspath(DOWNLOAD_DIR)

def cleanup_old_downloads():
    """Remove downloads older than FILE_CLEANUP_DAYS"""
    try:
        current_time = datetime.now()
        for item in os.listdir(DOWNLOAD_DIR):
            item_path = os.path.join(DOWNLOAD_DIR, item)
            if os.path.isdir(item_path):
                item_time = datetime.fromtimestamp(os.path.getctime(item_path))
                if current_time - item_time > timedelta(days=FILE_CLEANUP_DAYS):
                    shutil.rmtree(item_path)
                    logging.info(f"Cleaned up old download directory: {item_path}")
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

def ensure_download_dir():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR, mode=0o755, exist_ok=True)
    # Set more restrictive permissions
    os.chmod(DOWNLOAD_DIR, 0o755)
    logging.info(f"Download directory permissions set: {oct(os.stat(DOWNLOAD_DIR).st_mode)[-3:]}")

# Initialize download directory and cleanup
ensure_download_dir()
cleanup_old_downloads()

# Validate DOWNLOAD_DIR
if not DOWNLOAD_DIR.startswith("/app/downloads"):
    logging.error("Invalid DOWNLOAD_DIR configuration. Using default.")
    DOWNLOAD_DIR = "/app/downloads"
    ensure_download_dir()

def get_active_downloads():
    """Count active downloads in the system"""
    return len([d for d in os.listdir(DOWNLOAD_DIR) if os.path.isdir(os.path.join(DOWNLOAD_DIR, d))])

def is_valid_url(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http(s) or ftp
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal and invalid characters"""
    return secure_filename(filename)

@app.route("/", methods=["GET"])
def index():
    return render_template("deepseekindex.html")

@app.route("/download", methods=["POST"])
@limiter.limit("10 per minute")
def download():
    url = request.form.get("url")
    request_id = str(uuid.uuid4())
    logging.info(f"Download request {request_id} received for URL: {url}")

    if not url or not is_valid_url(url):
        logging.warning(f"Invalid URL in request {request_id}: {url}")
        return jsonify({"error": "Invalid URL", "request_id": request_id}), 400

    if get_active_downloads() >= MAX_CONCURRENT_DOWNLOADS:
        logging.warning(f"Too many concurrent downloads. Request {request_id} rejected.")
        return jsonify({
            "error": "System is busy. Please try again later.",
            "request_id": request_id
        }), 429

    try:
        # Ensure download directory exists and is writable
        ensure_download_dir()
        
        # Generate a unique subdirectory for this download
        unique_dir = os.path.join(DOWNLOAD_DIR, request_id)
        os.makedirs(unique_dir, mode=0o755, exist_ok=True)
        logging.info(f"Created unique directory: {unique_dir} with permissions: {oct(os.stat(unique_dir).st_mode)[-3:]}")

        # Determine the download tool
        if "youtube.com" in url or "youtu.be" in url:
            tool = "yt-dlp"
            command = [tool, "-P", unique_dir, "--max-filesize", str(MAX_FILE_SIZE), url]
        elif "instagram.com" in url:
            tool = "gallery-dl"
            command = [tool, "-D", unique_dir, "-o", "%(title)s.%(ext)s", "--max-filesize", str(MAX_FILE_SIZE), url]
        elif "tiktok.com" in url:
            tool = "gallery-dl"
            command = [tool, "-D", unique_dir, "-o", "%(title)s.%(ext)s", "--max-filesize", str(MAX_FILE_SIZE), url]
        else:
            logging.warning(f"No suitable downloader found for URL in request {request_id}: {url}")
            return jsonify({
                "error": "No suitable downloader found for this URL",
                "request_id": request_id
            }), 400

        logging.info(f"Starting download {request_id} with {tool}: {url}")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        try:
            stdout, stderr = process.communicate(timeout=DOWNLOAD_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            logging.error(f"Download {request_id} timed out after {DOWNLOAD_TIMEOUT} seconds")
            return jsonify({
                "error": "Download timed out. Please try again.",
                "request_id": request_id
            }), 504

        if process.returncode != 0:
            logging.error(f"Download {request_id} failed: {stderr}")
            return jsonify({
                "error": f"Download failed: {stderr}",
                "request_id": request_id
            }), 500

        # Get list of downloaded files
        downloaded_files = [f for f in os.listdir(unique_dir) if os.path.isfile(os.path.join(unique_dir, f))]
        if downloaded_files:
            # Set proper permissions for downloaded files
            for file in downloaded_files:
                file_path = os.path.join(unique_dir, file)
                os.chmod(file_path, 0o644)  # More restrictive permissions
                logging.info(f"Set file permissions for {file_path}: {oct(os.stat(file_path).st_mode)[-3:]}")

            logging.info(f"Download {request_id} successful. Files: {downloaded_files}")
            return jsonify({
                "message": "Download successful",
                "files": downloaded_files,
                "dir_id": request_id
            })
        else:
            logging.warning(f"Download {request_id} successful, but no files were created")
            return jsonify({
                "error": "Download successful, but no files were created",
                "request_id": request_id
            }), 500

    except FileNotFoundError as e:
        logging.error(f"Error in request {request_id}: {e}. Ensure {tool} is installed.")
        return jsonify({
            "error": f"Error: {e}. Ensure the download tool is installed.",
            "request_id": request_id
        }), 500
    except subprocess.CalledProcessError as e:
        logging.error(f"Download {request_id} failed with CalledProcessError: {e.stderr}")
        return jsonify({
            "error": f"Download failed: {e.stderr}",
            "request_id": request_id
        }), 500
    except Exception as e:
        logging.exception(f"Unexpected error in request {request_id}: {str(e)}")
        return jsonify({
            "error": f"An unexpected error occurred: {str(e)}",
            "request_id": request_id
        }), 500

@app.route('/downloads/<dir_id>/<filename>')
@limiter.limit("30 per minute")
def serve_download(dir_id, filename):
    request_id = str(uuid.uuid4())
    try:
        # Validate and sanitize inputs
        if not dir_id or not filename:
            logging.warning(f"Invalid request {request_id}: Missing dir_id or filename")
            return jsonify({"error": "Invalid request", "request_id": request_id}), 400

        # Sanitize filename
        safe_filename = sanitize_filename(filename)
        if safe_filename != filename:
            logging.warning(f"Filename sanitization in request {request_id}: {filename} -> {safe_filename}")

        # Construct the full path to the file
        file_dir = os.path.join(DOWNLOAD_DIR, dir_id)
        filepath = os.path.join(file_dir, safe_filename)
        
        logging.info(f"Request {request_id}: Attempting to serve file: {filepath}")
        
        # Security: Check if the file exists and is within the download directory
        if not os.path.exists(filepath):
            logging.error(f"Request {request_id}: File not found: {filepath}")
            return jsonify({
                "error": "File not found",
                "request_id": request_id
            }), 404
            
        if not filepath.startswith(DOWNLOAD_DIR):
            logging.error(f"Request {request_id}: Access denied - File path outside download directory: {filepath}")
            return jsonify({
                "error": "Access denied",
                "request_id": request_id
            }), 403

        # Check if file is a regular file (not a directory or symlink)
        if not os.path.isfile(filepath):
            logging.error(f"Request {request_id}: Invalid file type: {filepath}")
            return jsonify({
                "error": "Invalid file type",
                "request_id": request_id
            }), 400

        # Check file size
        file_size = os.path.getsize(filepath)
        if file_size > MAX_FILE_SIZE:
            logging.error(f"Request {request_id}: File too large: {filepath} ({file_size} bytes)")
            return jsonify({
                "error": "File too large",
                "request_id": request_id
            }), 413

        # Ensure file is readable
        if not os.access(filepath, os.R_OK):
            logging.error(f"Request {request_id}: File not readable: {filepath}")
            try:
                os.chmod(filepath, 0o644)
                logging.info(f"Request {request_id}: Fixed file permissions for {filepath}")
            except Exception as e:
                logging.error(f"Request {request_id}: Failed to fix file permissions: {e}")
                return jsonify({
                    "error": "File access error",
                    "request_id": request_id
                }), 500

        return send_from_directory(file_dir, safe_filename, as_attachment=True)
    except FileNotFoundError:
        logging.error(f"Request {request_id}: File not found: {filename}")
        return jsonify({
            "error": "File not found",
            "request_id": request_id
        }), 404
    except Exception as e:
        logging.exception(f"Request {request_id}: Error serving file: {e}")
        return jsonify({
            "error": "Error serving file",
            "request_id": request_id
        }), 500

if __name__ == "__main__":
    # When running locally without Docker/gunicorn, you might want debug=True
    # For production deployment via Docker/gunicorn, debug should be False (or removed)
    app.run(host="0.0.0.0", port=8000)