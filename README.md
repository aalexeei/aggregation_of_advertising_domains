# Aggregator of Advertising Domains 🛡️  
### This script automates downloading, filtering, and managing domain lists. It handles whitelisted and blacklisted entries, sends Telegram notifications, and performs log cleanup. The final list is saved in a file with size checks. Сan be used in AdAway, uMatrix, DNS66, GasMask, NetGuard

## Features ✨  
- **Domain Filtering:**  
  Downloads and processes domain lists from multiple sources.  
- **Multiple Input Formats:**  
  Accepts hosts files, plain domain lists and Adblock Plus filter lists in the same config.  
- **Whitelist/Blacklist Management:**  
  Removes whitelisted domains and adds missing blacklisted ones.  
- **Duplicate Removal:**  
  Automatically detects and removes duplicate entries.  
- **Fail-Loud Sources:**  
  Aborts instead of publishing a partial list when a source dies or changes format.  
- **Log Cleanup:**  
  Deletes outdated log files based on the configured age.  
- **Telegram Notifications:**  
  Sends updates about script status and actions.  
- **File Size Check:**  
  Warns if the output file exceeds the allowed size.  

## Installation 📦  
- **Clone the Repository:**  
  ```bash  
  git clone https://github.com/aalexeei/aggregation_of_advertising_domains.git 
  cd aggregation_of_advertising_domains  
  
- **Install dependencies:**
  ```bash 
   pip3 install -r requirements.txt
  ```
  
- **Set environment variables in a .env file:**
  ```bash 
  TELEGRAM_BOT_TOKEN=your_telegram_bot_token
  TELEGRAM_CHAT_ID=your_telegram_chat_id
  ```
- **Configure the script using config.json:**

  ```json 
  {
    "log_dir": "./logs",
    "max_log_age_days": 7,
    "output_file_base": "aggregated_list",
    "white_list_file": "./whitelist.txt",
    "black_list_file": "./blacklist.txt",
    "max_allowed_kib": 100000,
    "request_timeout_seconds": 60,
    "abort_on_source_failure": true,
    "max_shrink_percent": 20,
    "urls": [
      "https://example.com/list1.txt",
      "https://example.com/list2.txt"
    ]
  }
  ```
  | Key | Meaning |
  | --- | --- |
  | `request_timeout_seconds` | Per-source download timeout. |
  | `abort_on_source_failure` | Leave the output file untouched if any source fails. Set to `false` to publish from whatever downloaded. |
  | `max_shrink_percent` | Abort if the new list is smaller than the previous one by more than this. |
## Usage 🚀
Run the script with:
  ```bash 
  python3 aggregator.py
  ```
## How It Works 🔧

### 1. **Download and Filter**
- The script downloads domain lists from the URLs specified in `config.json`.
- Each line is parsed regardless of the source format:
  - **hosts** — `0.0.0.0 ads.example.com`, `127.0.0.1 ads.example.com`
  - **plain domains** — `ads.example.com`
  - **Adblock Plus** — `||ads.example.com^`, `||ads.example.com^$third-party`
- Rules that have no DNS equivalent are skipped rather than mangled: cosmetic filters
  (`site.com##.banner`), exceptions (`@@||site.com^`), path and regex rules,
  TLD wildcards (`||adservice.google.^`), and rules whose modifiers restrict them to a
  context DNS cannot see (`$script`, `$domain=site.com`) — blocking those at the DNS level
  would take down the whole domain instead of one request.
- It filters out duplicates, comments, and unwanted domains.

### 2. **Whitelist/Blacklist Handling**
- **Whitelist:** Domains listed in the whitelist are removed from the final list.
  An entry written as `example.com` matches that exact name; an entry written as
  `.example.com` (or `*.example.com`) matches the domain and every subdomain, which is
  what you want when a source blocks a whole backend zone.
- **Blacklist:** Missing domains from the blacklist are added to the final list.

### 3. **Logging and Notifications**
- All actions are logged to timestamped files for easy tracking.
- A detailed report is sent via Telegram to notify users of the script’s actions.

### 4. **Output File**
- The processed list is saved to `aggregated_list.txt` (or a custom name if configured).
- The script checks if the new content is different from the existing one before overwriting the output file.

### 5. **Choosing Sources — Read Before Adding a URL**
The output is a **hosts file, which matches domains exactly**. MikroTik `/ip dns adlist`,
AdAway, NetGuard and DNS66 have no wildcard support: `0.0.0.0 example.com` does **not**
block `ads.example.com`. (On RouterOS, `match-subdomain=yes` exists only for
`/ip dns static`, not for adlist.)

Most large blocklists have moved to **base-domain lists for wildcard resolvers** — hagezi
dropped the hosts format entirely, and oisd never had one. Files named `-onlydomains`,
`wildcard/`, `domainswild` or `dnsmasq` carry one entry per base domain and state
`Syntax: Domains (without subdomains)` in their header. Feeding those into a hosts file
silently loses every subdomain: hagezi's old `hosts/pro.txt` listed `0.as.slashdot.org`,
its replacement lists only `slashdot.org`.

**So: only add sources that enumerate subdomains** (StevenBlack, 1Hosts, AdAway).
Base-domain lists are still worth keeping — they block the apex domain — but they cannot
replace a subdomain-enumerated list, and no source can restore subdomains another
maintainer stopped publishing.

### 6. **Source Health Checks**
A blocklist that silently shrinks is worse than one that fails, so the script refuses to
publish and reports to Telegram when:
- a source returns an error or times out;
- a source returns HTTP 200 but yields **zero** usable domains (it changed format);
- the new list is more than `max_shrink_percent` smaller than the previous one.

## Example Output 📄

### Log File:
`/logs/log_2024-12-03_14-00-00.log`

### Final Output:
`aggregated_list.txt`

### Telegram Notifications 📢
Sample messages sent to Telegram:

🗑 Removed 17141 duplicate lines.
- ❗ Found and removed 1 domains from white list!
- ✅ Domains from the blacklist are not added.
- ✅ File updated: aggregated_list.txt
- 📄 Total lines: 592618
- ⚠️ RAM required: 69775 KiB

## Contributing 🤝
Feel free to submit issues or pull requests. Contributions are welcome!



Enjoy a cleaner, safer internet! 🌐
