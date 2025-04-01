from flask import Flask, render_template, request, jsonify, send_from_directory
import subprocess
import os
import re
import logging
import uuid  # For generating unique filenames
import stat  # For setting file permissions

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/app/downloads")
# Ensure DOWNLOAD_DIR is absolute and safe
DOWNLOAD_DIR = os.path.abspath(DOWNLOAD_DIR)

# Create download directory with proper permissions
def ensure_download_dir():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR, mode=0o755, exist_ok=True)
    # Ensure the directory is writable
    os.chmod(DOWNLOAD_DIR, 0o755)

# Initialize download directory
ensure_download_dir()

# Validate DOWNLOAD_DIR (important security measure)
if not DOWNLOAD_DIR.startswith("/app/downloads"):  # Adjust prefix as needed
    logging.error("Invalid DOWNLOAD_DIR configuration. Using default.")
    DOWNLOAD_DIR = "/app/downloads"
    ensure_download_dir()

# Basic URL validation
def is_valid_url(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http(s) or ftp
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url")

    if not url or not is_valid_url(url):
        logging.warning(f"Invalid URL: {url}")
        return jsonify({"error": "Invalid URL"}), 400

    try:
        # Ensure download directory exists and is writable
        ensure_download_dir()
        
        # Generate a unique subdirectory for this download
        unique_dir = os.path.join(DOWNLOAD_DIR, str(uuid.uuid4()))
        os.makedirs(unique_dir, mode=0o755, exist_ok=True)

        # Determine the download tool
        if "youtube.com" in url or "youtu.be" in url:
            tool = "yt-dlp"
            command = [tool, "-P", unique_dir, url]
        elif "instagram.com" in url:
            tool = "gallery-dl"
            command = [tool, "-D", unique_dir, "-o", "%(title)s.%(ext)s", url]
        elif "tiktok.com" in url:
            tool = "gallery-dl"
            command = [tool, "-D", unique_dir, "-o", "%(title)s.%(ext)s", url]
        else:
            logging.warning(f"No suitable downloader found for: {url}")
            return jsonify({"error": "No suitable downloader found for this URL"}), 400

        logging.info(f"Downloading with {tool}: {url}")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            logging.error(f"Download failed: {stderr}")
            return jsonify({"error": f"Download failed: {stderr}"}), 500

        # Get list of downloaded files
        downloaded_files = [f for f in os.listdir(unique_dir) if os.path.isfile(os.path.join(unique_dir, f))]
        if downloaded_files:
            # Return the unique directory ID along with the files
            unique_dir_id = os.path.basename(unique_dir)
            logging.info(f"Download successful. Files: {downloaded_files}")
            return jsonify({
                "message": "Download successful", 
                "files": downloaded_files,
                "dir_id": unique_dir_id
            })
        else:
            logging.warning("Download successful, but no files were created")
            return jsonify({"error": "Download successful, but no files were created"}), 500

    except FileNotFoundError as e:
        logging.error(f"Error: {e}. Ensure {tool} is installed.")
        return jsonify({"error": f"Error: {e}. Ensure the download tool is installed."}), 500
    except subprocess.CalledProcessError as e:
        logging.error(f"Download failed with CalledProcessError: {e.stderr}")
        return jsonify({"error": f"Download failed: {e.stderr}"}), 500
    except Exception as e:
        logging.exception(f"An unexpected error occurred: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/downloads/<dir_id>/<filename>')
def serve_download(dir_id, filename):
    try:
        # Construct the full path to the file
        file_dir = os.path.join(DOWNLOAD_DIR, dir_id)
        filepath = os.path.join(file_dir, filename)
        
        # Security: Check if the file exists and is within the download directory
        if not os.path.exists(filepath) or not filepath.startswith(DOWNLOAD_DIR):
            logging.error(f"File not found or access denied: {filepath}")
            return jsonify({"error": "File not found or access denied"}), 404

        return send_from_directory(file_dir, filename, as_attachment=True)
    except FileNotFoundError:
        logging.error(f"File not found: {filename}")
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        logging.error(f"Error serving file: {e}")
        return jsonify({"error": "Error serving file"}), 500

if __name__ == "__main__":
    # When running locally without Docker/gunicorn, you might want debug=True
    # For production deployment via Docker/gunicorn, debug should be False (or removed)
    app.run(host="0.0.0.0", port=8000)