import requests
import math
import logging
import os
import time
from datetime import datetime, timedelta

# Constants for log file management
LOG_DIR = "logs"
MAX_LOG_AGE_DAYS = 7  # Maximum log file age in days

# Create log directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)

# Set up the logger
log_filename = f"{LOG_DIR}/log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logging.basicConfig(filename=log_filename, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Function to clean up old logs
def cleanup_old_logs():
    current_time = time.time()
    for filename in os.listdir(LOG_DIR):
        file_path = os.path.join(LOG_DIR, filename)
        if os.path.isfile(file_path):
            file_age = current_time - os.path.getmtime(file_path)
            if file_age > MAX_LOG_AGE_DAYS * 86400:  # 86400 seconds in a day
                os.remove(file_path)
                logging.info(f"Deleted old log file: {filename}")

# Call cleanup function at the beginning
cleanup_old_logs()

# List of URLs to download files
urls = [
    "https://raw.githubusercontent.com/braveinnovators/ukrainian-security-filter/main/lists/domains.txt",  # https://github.com/braveinnovators/ukrainian-security-filter
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/gambling/hosts", #https://github.com/StevenBlack/hosts
    "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/hosts/multi.txt"
]

# Base name of the output file
output_file_base = "aggregated_list"

# Constants
KIB_PER_STRING = 39998 /356701  # Approx. 0.112133 KiB per string
BUFFER_FACTOR = 1.05  # 5% buffer to ensure enough space
MAX_ALLOWED_KIB = 50000  # Maximum allowed size in KiB

# Function to download file content from a URL
def download_file(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        lines = response.text.splitlines()
        logging.info(f"File downloaded successfully from {url}. Total lines: {len(lines)}")
        return lines
    except requests.RequestException as e:
        logging.error(f"Error downloading {url}: {e}")
        return []

# Download all files and count lines
all_lines = []
total_lines_before_filter = 0

for url in urls:
    logging.info(f"Downloading: {url}")
    file_lines = download_file(url)
    if file_lines:
        all_lines.extend(file_lines)
        total_lines_before_filter += len(file_lines)

# Filter lines: remove empty lines and those starting with '#', add "0.0.0.0" prefix where necessary
filtered_lines = []
for line in all_lines:
    stripped_line = line.strip()
    if not stripped_line or stripped_line.startswith("#"):
        continue  # Skip empty lines and comments
    if stripped_line.startswith("0.0.0.0"):
        filtered_lines.append(stripped_line)  # Add the line as is if it's already in the correct format
    else:
        filtered_lines.append(f"0.0.0.0 {stripped_line}")  # Add the "0.0.0.0" prefix for other lines

# Remove duplicates
seen = set()
unique_lines = []
duplicates = []

for line in filtered_lines:
    if line in seen:
        duplicates.append(line)  # Add duplicate to duplicates list
    else:
        seen.add(line)
        unique_lines.append(line)

# Count total lines and duplicates
duplicates_count = len(duplicates)
total_lines_after_filter = len(unique_lines)

if duplicates_count > 0:
    logging.info(f"Duplicates found and removed: {duplicates_count}")
else:
    logging.info("No duplicates found.")

# Calculate required cache size in KiB with buffer
required_cache_kib = math.ceil(total_lines_after_filter * KIB_PER_STRING * BUFFER_FACTOR)

# Check if the required size exceeds the maximum allowed size
if required_cache_kib > MAX_ALLOWED_KIB:
    logging.warning(f"The file size exceeds {MAX_ALLOWED_KIB} KiB! Actual size: {required_cache_kib} KiB")

# Final file name with cache size appended
output_file = f"{output_file_base}.txt"

# Save the final output to a file
try:
    with open(output_file, "w") as f:
        f.write("\n".join(unique_lines))
    logging.info(f"Processed file saved as: {output_file}")
    logging.info(f"Total lines before filtering (sum of all files): {total_lines_before_filter}")
    logging.info(f"Total lines in merged file after filtering and deduplication: {total_lines_after_filter}")
    logging.info(f"Required cache size (with buffer): {required_cache_kib} KiB")
except IOError as e:
    logging.error(f"Error saving the file {output_file}: {e}")
