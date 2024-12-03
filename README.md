# Aggregator of Advertising Domains 🛡️  
### This script automates downloading, filtering, and managing domain lists. It handles whitelisted and blacklisted entries, sends Telegram notifications, and performs log cleanup. The final list is saved in a file with size checks. Сan be used in AdAway, uMatrix, DNS66, GasMask, NetGuard

## Features ✨  
- **Domain Filtering:**  
  Downloads and processes domain lists from multiple sources.  
- **Whitelist/Blacklist Management:**  
  Removes whitelisted domains and adds missing blacklisted ones.  
- **Duplicate Removal:**  
  Automatically detects and removes duplicate entries.  
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
    "urls": [
      "https://example.com/list1.txt",
      "https://example.com/list2.txt"
    ]
  }
  ```
## Usage 🚀
Run the script with:
  ```bash 
  python3 aggregator.py
  ```
## How It Works 🔧

### 1. **Download and Filter**
- The script downloads domain lists from the URLs specified in `config.json`.
- It filters out duplicates, comments, and unwanted domains.

### 2. **Whitelist/Blacklist Handling**
- **Whitelist:** Domains listed in the whitelist are removed from the final list.
- **Blacklist:** Missing domains from the blacklist are added to the final list.

### 3. **Logging and Notifications**
- All actions are logged to timestamped files for easy tracking.
- A detailed report is sent via Telegram to notify users of the script’s actions.

### 4. **Output File**
- The processed list is saved to `filtered_domains.txt` (or a custom name if configured).
- The script checks if the new content is different from the existing one before overwriting the output file.

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
