# Internships Feed Bot

## Overview

This project is a Discord bot designed to monitor a GitHub repository for new internship postings and send formatted messages to a specified Discord channel. The bot performs the following tasks:

1. Clones or updates the specified GitHub repository.
2. Reads a JSON file containing internship listings.
3. Compares the new listings with previously stored data.
4. Sends formatted messages to a Discord channel for any new visible and active roles.

## Setup

### Prerequisites

- Python 3.6 or higher
- Git
- Discord bot with Message Content Intent enabled
- One or more Discord channel IDs
- (Optional) System logrotate for log management

### Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/builtbybob/internships-bot.git
    cd internships-bot
    ```

2. Install the required Python packages:
    ```sh
    pip install -r requirements.txt
    ```

3. Set up your Discord bot:
    - Create a new bot on the [Discord Developer Portal](https://discord.com/developers/applications).
    - Enable the "Message Content Intent" in the Bot section.
    - Copy the bot token and set it in your `.env` file.
    - Get the channel IDs where you want the bot to send messages and set them in `CHANNEL_IDS`.

### Configuration

The bot uses environment variables for configuration. Copy the `.env.example` file to `.env` and configure:

```ini
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here      # Required: Your Discord bot token
CHANNEL_IDS=123456789,987654321               # Required: Comma-separated list of channel IDs

# Repository Configuration
REPO_URL=https://github.com/SimplifyJobs/Summer2026-Internships.git  # Optional: Default shown
LOCAL_REPO_PATH=Summer2026-Internships        # Optional: Local path for the repo

# Bot Configuration
MAX_RETRIES=3                                 # Optional: Max retries for failed channels
CHECK_INTERVAL_MINUTES=1                      # Optional: Minutes between repo checks
LOG_LEVEL=INFO                                # Optional: Logging level (INFO/DEBUG/etc)
```

## Log Management

The bot includes two methods for log rotation to prevent disk space issues:

### Built-in Log Rotation (run_bot.sh)

The included `run_bot.sh` script provides basic log rotation:

```bash
# Make the script executable
chmod +x run_bot.sh

# Run the bot with built-in log rotation
./run_bot.sh
```

This method:
- Rotates logs when they reach 10MB
- Maintains 5 backup files (nohup.out.1 through nohup.out.5)
- Automatically restarts the bot if it exits

### System Log Rotation (logrotate)

For more robust log management, use the provided logrotate configuration:

1. Copy the config to the logrotate.d directory:
    ```sh
    sudo cp internships-bot.logrotate /etc/logrotate.d/internships-bot
    ```

2. Test the configuration:
    ```sh
    sudo logrotate -d /etc/logrotate.d/internships-bot
    ```

The logrotate configuration:
- Rotates logs weekly or when they reach 10MB
- Keeps 5 compressed backups
- Uses appropriate permissions
- Handles missing log files gracefully

## Usage

1. Start the bot using either method:
    ```sh
    # Using run_bot.sh (recommended)
    ./run_bot.sh
    
    # Or directly (for development)
    python mainbot.py
    ```

2. The bot will:
    - Validate the environment configuration
    - Clone or update the GitHub repository
    - Process the internship listings
    - Send formatted messages to all configured channels
    - Continue monitoring for updates at the configured interval

## Features

### Message Ordering and Processing

- **Chronological Processing**: Messages are processed in chronological order using a priority queue (heapq), ensuring posts appear in the correct sequence.
- **Date Filtering**: Only processes roles posted within the last 5 days to avoid spam from bulk updates.
- **Multi-Channel Support**: Can send messages to multiple Discord channels simultaneously.
- **Rate Limiting**: Includes built-in delays to prevent Discord API rate limiting.

### Error Handling and Recovery

- **Channel Recovery**: Automatically retries failed channel messages up to configured MAX_RETRIES.
- **Channel Health Tracking**: Maintains a list of failed channels to avoid repeated failures.
- **Permission Handling**: Properly handles Discord permission errors and channel access issues.
- **Graceful Shutdown**: Handles SIGINT and SIGTERM signals for clean shutdown.

### Message Tracking

- **Duplicate Prevention**: Uses normalized role keys to prevent duplicate messages.
- **Message History**: Tracks previously sent messages to prevent re-sending on restarts.
- **Change Detection**: Efficiently detects repository updates using git commit hashes.

### Core Functions

#### Repository Management
- `clone_or_update_repo()`: Manages the local copy of the internships repository.
- `read_json()`: Parses the internship listings file.

#### Message Processing
- `format_message(role)`: Creates formatted Discord messages from role data.
- `normalize_role_key(role)`: Generates stable keys for role comparison.
- `compare_roles(old_role, new_role)`: Detects changes in role attributes.

#### Discord Integration
- `send_message(message, channel_id, role_key)`: Sends a message to a single channel.
- `send_messages_to_channels(message, role_key)`: Distributes messages to all configured channels.
- `check_for_new_roles()`: Main update detection and message dispatch logic.

### Scheduling

The bot checks for updates at configurable intervals (default: 1 minute) using the `schedule` library. The check interval can be adjusted using the `CHECK_INTERVAL_MINUTES` environment variable.
