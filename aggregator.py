import os
import math
import logging
import aiohttp
import asyncio
import requests
import re
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

LOG_DIR = config["log_dir"]
MAX_LOG_AGE_DAYS = config["max_log_age_days"]
OUTPUT_FILE_BASE = config["output_file_base"]
WHITE_LIST_FILE = config["white_list_file"]
BLACK_LIST_FILE = config["black_list_file"]
MAX_ALLOWED_KIB = config["max_allowed_kib"]
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Set up logging
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = f"{LOG_DIR}/log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logging.basicConfig(filename=log_filename, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Function to send Telegram notifications
def send_telegram_notification(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
        logging.info("Telegram notification sent.")
    except requests.RequestException as e:
        logging.error(f"Failed to send Telegram notification: {e}")

# Function to clean up old logs
def cleanup_old_logs():
    current_time = time.time()
    for filename in os.listdir(LOG_DIR):
        file_path = os.path.join(LOG_DIR, filename)
        if os.path.isfile(file_path) and (current_time - os.path.getmtime(file_path)) > MAX_LOG_AGE_DAYS * 86400:
            os.remove(file_path)
            logging.info(f"Deleted old log file: {filename}")

# Load whitelist and blacklist
def load_list(file_path):
    if not os.path.exists(file_path):
        Path(file_path).touch()  # Create empty file if it doesn't exist
    with open(file_path, "r") as f:
        return {line.strip() for line in f if line.strip()}

white_list = load_list(WHITE_LIST_FILE)
black_list = load_list(BLACK_LIST_FILE)

# Async function to download file
async def download_file(session, url):
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            text = await response.text()
            lines = text.splitlines()
            logging.info(f"Downloaded {len(lines)} lines from {url}")
            return lines
    except Exception as e:
        logging.error(f"Error downloading {url}: {e}")
        return []

# Validate domain
def is_valid_domain(domain):
    pattern = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.(?:[A-Za-z]{2,6}|xn--[A-Za-z0-9]+)$"
    return bool(re.match(pattern, domain))

# Main function to download and process files
async def main():
    telegram_message = []  # Collect all messages here

    async with aiohttp.ClientSession() as session:
        tasks = [download_file(session, url) for url in config["urls"]]
        results = await asyncio.gather(*tasks)

    # Combine all lines from downloaded files
    all_lines = [line for sublist in results for line in sublist]
    filtered_lines = [
        f"0.0.0.0 {line.strip()}" if not line.startswith("0.0.0.0") else line.strip()
        for line in all_lines if line.strip() and not line.startswith("#")
    ]

    # Remove duplicates
    seen = set()
    unique_lines = [line for line in filtered_lines if line not in seen and not seen.add(line)]

    # Check white list: remove domains from white list
    found_in_white_list = []
    final_lines = []
    for line in unique_lines:
        domain = line.split()[1]  # Extract domain
        if domain in white_list:
            found_in_white_list.append(domain)  # Save domain if it is in white list
        else:
            final_lines.append(line)  # Otherwise, add to final list

    # Add information about white list to logs and Telegram
    if found_in_white_list:
        logging.info(f"Found and removed {len(found_in_white_list)} domains from white list: {', '.join(found_in_white_list)}")
        telegram_message.append(f"❗ Found and removed {len(found_in_white_list)} domains from white list: {', '.join(found_in_white_list)}")
    else:
        telegram_message.append("✅ No domains found in white list.")

    # Filter out blacklisted domains and add missing blacklisted domains
    added_black_list_domains = []
    for black_domain in black_list:
        if black_domain not in {line.split()[1] for line in final_lines} and is_valid_domain(black_domain):
            final_lines.append(f"0.0.0.0 {black_domain}")
            added_black_list_domains.append(black_domain)
            logging.info(f"Added missing blacklisted domain: {black_domain}")

    # Add information about black list to logs and Telegram
    if added_black_list_domains:
        logging.info(f"Found and added {len(added_black_list_domains)} domains from black list: {', '.join(added_black_list_domains)}")
        telegram_message.append(f"❗ Found and added {len(added_black_list_domains)} domains from black list: {', '.join(added_black_list_domains)}")
    else:
        logging.info("Domains from the blacklist are not added.")
        telegram_message.append("✅ Domains from the blacklist are not added.")

    # Calculate required cache size
    required_cache_kib = math.ceil(len(final_lines) * 0.112133 * 1.05)
    if required_cache_kib > MAX_ALLOWED_KIB:
        logging.warning(f"File size exceeds limit: {required_cache_kib} KiB")
        telegram_message.append(f"⚠️ File size exceeds limit: {required_cache_kib} KiB")

    # Check for changes before saving
    output_file = f"{OUTPUT_FILE_BASE}.txt"
    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            existing_content = f.read().splitlines()
        if set(existing_content) == set(final_lines):
            logging.info("No changes detected. Skipping file update.")
            telegram_message.append("❗ No changes detected. File update skipped.")
        else:
            # Save to file
            with open(output_file, "w") as f:
                f.write("\n".join(final_lines))
            logging.info(f"Saved output to {output_file}. Total lines: {len(final_lines)}")
            telegram_message.append(f"✅ File updated: `{output_file}`\n📄 Total lines: {len(final_lines)}\n⚠️ File size: {required_cache_kib} KiB")
    else:
        # Save to file if it doesn't exist
        with open(output_file, "w") as f:
            f.write("\n".join(final_lines))
        logging.info(f"Saved output to {output_file}. Total lines: {len(final_lines)}")
        telegram_message.append(f"✅ File updated: `{output_file}`\n📄 Total lines: {len(final_lines)}\n⚠️ File size: {required_cache_kib} KiB")

    # Send all messages in a single Telegram notification
    send_telegram_notification("\n".join(telegram_message))

# Cleanup and run main
cleanup_old_logs()
asyncio.run(main())
