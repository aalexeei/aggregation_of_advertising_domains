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
import hashlib

# Install the working directory into the script folder
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Configuration from config.json
config_path = os.path.join(os.getcwd(), "config.json")
with open(config_path, "r") as config_file:
    config = json.load(config_file)

LOG_DIR = config["log_dir"]
MAX_LOG_AGE_DAYS = config["max_log_age_days"]
OUTPUT_FILE_BASE = config["output_file_base"]
WHITE_LIST_FILE = config["white_list_file"]
BLACK_LIST_FILE = config["black_list_file"]
MAX_ALLOWED_KIB = config["max_allowed_kib"]
REQUEST_TIMEOUT_SECONDS = config.get("request_timeout_seconds", 60)
ABORT_ON_SOURCE_FAILURE = config.get("abort_on_source_failure", True)
MAX_SHRINK_PERCENT = config.get("max_shrink_percent", 20)
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
        return {line.strip().split(' ')[1] if line.startswith('0.0.0.0 ') else line.strip()
                for line in f if line.strip() and not line.startswith('#')}


white_list = load_list(WHITE_LIST_FILE)
black_list = load_list(BLACK_LIST_FILE)


# A whitelist entry written as ".example.com" covers the zone: the domain itself and every
# subdomain. Aggressive sources keep inventing new hostnames under one backend (game auth,
# regional shards), and MikroTik adlist matches exact names only, so without this every new
# subdomain silently breaks the same service again.
def split_white_list(entries):
    exact, zones = set(), set()
    for entry in entries:
        if entry.startswith("*."):
            entry = entry[1:]
        if entry.startswith("."):
            zones.add(entry.lstrip("."))
        else:
            exact.add(entry)
    return exact, zones


white_exact, white_zones = split_white_list(white_list)


def is_white_listed(domain):
    if domain in white_exact:
        return True
    parts = domain.split(".")
    return any(".".join(parts[i:]) in white_zones for i in range(len(parts)))


# Async function to download file
async def download_file(session, url):
    """Download one source. Returns (url, lines, error) - error is None on success."""
    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        async with session.get(url, ssl=False, timeout=timeout) as response:
            response.raise_for_status()
            text = await response.text()
            lines = text.splitlines()
            logging.info(f"Downloaded {len(lines)} lines from {url}")
            return url, lines, None
    except Exception as e:
        logging.error(f"Error downloading {url}: {e}")
        return url, [], str(e)


# Validate domain
def is_valid_domain(domain):
    pattern = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,}$"
    return bool(re.match(pattern, domain))


# Adblock modifiers that leave a rule equivalent to a plain DNS block. Anything else
# (element types, domain=/denyallow= context) would over-block if applied to the whole domain.
DNS_SAFE_MODIFIERS = {"all", "doc", "document", "important", "popup", "third-party", "3p"}

COMMENT_PREFIXES = ("#", "!", "[")
COSMETIC_MARKERS = ("##", "#@#", "#?#", "#$#", "#%#")

# Special-use names that must never be published as blocked. Nearly every hosts file
# opens with a loopback preamble (localhost, localhost.localdomain, broadcasthost, ...)
# and those lines parse as perfectly valid domains. RFC 6761 / RFC 8375.
RESERVED_NAMES = {"localhost", "localhost.localdomain", "broadcasthost", "local", "localdomain"}
RESERVED_TLDS = {"corp", "home", "internal", "invalid", "lan", "local",
                 "localdomain", "localhost", "onion", "test"}

HOSTS_PATTERN = re.compile(r"^(?:0\.0\.0\.0|127\.0\.0\.1|::1?)\s+(\S+)")
ADBLOCK_PATTERN = re.compile(r"^\|\|([^/^$|]+)\^?(?:\$(.*))?$")


# Check that every modifier of an Adblock rule is safe to drop when blocking by DNS
def modifiers_are_dns_safe(modifiers):
    return all(
        part.split("=")[0].strip() in DNS_SAFE_MODIFIERS
        for part in modifiers.split(",") if part.strip()
    )


# Extract a blockable domain from a hosts, plain-domain or Adblock Plus line.
# Returns None for comments and for rules that cannot be expressed as a DNS block
# (cosmetic filters, exceptions, path/regex rules, TLD wildcards).
def parse_line(line):
    line = line.strip()
    if not line or line.startswith(COMMENT_PREFIXES):
        return None
    if line.startswith("@@"):  # exception rule - must never end up in a blocklist
        return None
    if any(marker in line for marker in COSMETIC_MARKERS):
        return None

    hosts_match = HOSTS_PATTERN.match(line)
    if hosts_match:
        candidate = hosts_match.group(1)
    else:
        adblock_match = ADBLOCK_PATTERN.match(line)
        if adblock_match:
            candidate, modifiers = adblock_match.groups()
            if modifiers and not modifiers_are_dns_safe(modifiers):
                return None
        else:
            candidate = line

    candidate = candidate.lower()
    if candidate in RESERVED_NAMES or candidate.rsplit(".", 1)[-1] in RESERVED_TLDS:
        return None
    return candidate if is_valid_domain(candidate) else None


# Calculate hash for list of lines
def calculate_hash(lines):
    return hashlib.md5("\n".join(lines).encode()).hexdigest()


# Main function to download and process files
async def main():
    telegram_message = []  # Collect all messages here

    async with aiohttp.ClientSession() as session:
        tasks = [download_file(session, url) for url in config["urls"]]
        results = await asyncio.gather(*tasks)

    # Parse every source and record the ones that failed. A source that downloads fine
    # but yields no domains has changed format on us, which is just as broken as a 404.
    failed_sources = []
    filtered_lines = []

    for url, lines, error in results:
        if error:
            failed_sources.append(f"{url} - {error}")
            continue

        domains = [domain for domain in map(parse_line, lines) if domain]
        logging.info(f"Parsed {len(domains)} domains from {len(lines)} lines of {url}")

        if not domains:
            failed_sources.append(f"{url} - downloaded {len(lines)} lines but no usable domains")
            continue

        filtered_lines.extend(f"0.0.0.0 {domain}" for domain in domains)

    # A missing source silently shrinks the blocklist, so refuse to publish a partial list
    if failed_sources:
        for source in failed_sources:
            logging.error(f"Source unavailable: {source}")
        telegram_message.append(f"❌ {len(failed_sources)} of {len(results)} sources failed:")
        telegram_message.extend(f"• {source}" for source in failed_sources)

        if ABORT_ON_SOURCE_FAILURE:
            logging.error("Aborting: refusing to overwrite the list from incomplete sources.")
            telegram_message.append("🛑 Aborted, list left unchanged.")
            send_telegram_notification("\n".join(telegram_message))
            return
    else:
        telegram_message.append(f"✅ All {len(results)} sources downloaded.")

    # Remove duplicates in one pass
    seen = set()
    unique_lines = [line for line in filtered_lines if line not in seen and not seen.add(line)]

    logging.info(f"Removed {len(filtered_lines) - len(unique_lines)} duplicate lines.")
    telegram_message.append(f"🗑 Removed {len(filtered_lines) - len(unique_lines)} duplicate lines.")

    # Remove domains from white list
    final_lines = [line for line in unique_lines if not is_white_listed(line.split()[1])]
    found_in_white_list = len(unique_lines) - len(final_lines)

    if found_in_white_list:
        logging.info(f"Removed {found_in_white_list} domains from white list.")
        telegram_message.append(f"❗ Removed {found_in_white_list} domains from white list!")
    else:
        telegram_message.append("✅ No domains found in white list.")

    # Add missing blacklisted domains
    final_domains = {line.split()[1] for line in final_lines}
    added_black_list_domains = [
        black_domain for black_domain in black_list
        if black_domain not in final_domains and is_valid_domain(black_domain)
    ]
    final_lines.extend([f"0.0.0.0 {domain}" for domain in added_black_list_domains])

    if added_black_list_domains:
        logging.info(f"Added {len(added_black_list_domains)} domains from black list")
        telegram_message.append(f"❗ Added {len(added_black_list_domains)} domains from black list!")
    else:
        telegram_message.append("✅ No domains from the blacklist were added.")

    # Calculate required cache size. Measured on RouterOS: 1_624_417 adlist entries occupied
    # 116_439 KiB, i.e. 73.4 bytes each, so this estimate runs ~7% high. Keep the margin -
    # the coefficient can differ between RouterOS versions and warning early is the safe side.
    required_cache_kib = math.ceil(len(final_lines) * 75.19 * 1.05 / 1024)

    # Check for changes and save to file
    output_file = f"{OUTPUT_FILE_BASE}.txt"
    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            existing_lines = f.read().splitlines()
        existing_hash = calculate_hash(existing_lines)

        # A source can return HTTP 200 with truncated content, which no error check catches.
        # Treat an unexplained collapse in size as a bad build rather than a real update.
        shrink_limit = len(existing_lines) * (1 - MAX_SHRINK_PERCENT / 100)
        if existing_lines and len(final_lines) < shrink_limit:
            shrink_percent = round((1 - len(final_lines) / len(existing_lines)) * 100, 1)
            logging.error(f"Aborting: list shrank by {shrink_percent}% "
                          f"({len(existing_lines)} -> {len(final_lines)} lines).")
            telegram_message.append(
                f"🛑 Aborted: list shrank by {shrink_percent}% "
                f"({len(existing_lines)} → {len(final_lines)} lines). File left unchanged.")
            send_telegram_notification("\n".join(telegram_message))
            return

        new_hash = calculate_hash(final_lines)
        if existing_hash == new_hash:
            logging.info("No changes detected. Skipping file update.")
            telegram_message.append("❗ No changes detected. File update skipped.")
        else:
            with open(output_file, "w") as f:
                f.write("\n".join(final_lines))
            logging.info(f"Saved output to {output_file}. Total lines: {len(final_lines)}")
            telegram_message.append(
                f"✅ File updated: `{output_file}`\n📄 Total lines: {len(final_lines)}\n⚠️ RAM required: {required_cache_kib} KiB")
    else:
        with open(output_file, "w") as f:
            f.write("\n".join(final_lines))
        logging.info(f"Saved output to {output_file}. Total lines: {len(final_lines)}")
        telegram_message.append(
            f"✅ File updated: `{output_file}`\n📄 Total lines: {len(final_lines)}\n⚠️ RAM required: {required_cache_kib} KiB")

    if required_cache_kib > MAX_ALLOWED_KIB:
        logging.warning(f"File size exceeds limit: {required_cache_kib} KiB")
        telegram_message.append(f"❗❗ RAM exceeds limit: {required_cache_kib} KiB")

    send_telegram_notification("\n".join(telegram_message))

# Cleanup and run main
if __name__ == "__main__":
    cleanup_old_logs()
    asyncio.run(main())
