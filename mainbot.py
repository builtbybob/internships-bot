# Standard library imports
import asyncio
from datetime import datetime
import heapq
import json
import logging
from logging import Logger
import os
import signal
import sys

# Third-party imports
import discord
from discord.ext import commands
from dotenv import load_dotenv
import git
import schedule

# Load environment variables
load_dotenv()

# Logging setup
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format='[%(asctime)s] [%(levelname)-7s] %(name)s: %(message)s',
)
logger: Logger = logging.getLogger('internships-bot')

# Configuration validation
def validate_config():
    """Validate required configuration values on startup"""
    required_vars = ['DISCORD_TOKEN', 'CHANNEL_IDS']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file or set these environment variables.")
        sys.exit(1)
    
    # Validate channel IDs format
    try:
        channel_ids = os.getenv('CHANNEL_IDS').split(',')
        for channel_id in channel_ids:
            int(channel_id.strip())
    except (ValueError, AttributeError):
        logger.error("CHANNEL_IDS must be comma-separated integers")
        sys.exit(1)
    
    logger.info("Configuration validation passed.")

# Validate configuration on startup
validate_config()

# Constants from environment variables
REPO_URL = os.getenv('REPO_URL', 'https://github.com/SimplifyJobs/Summer2026-Internships.git')
LOCAL_REPO_PATH = os.getenv('LOCAL_REPO_PATH', 'Summer2026-Internships')
JSON_FILE_PATH = os.path.join(LOCAL_REPO_PATH, '.github', 'scripts', 'listings.json')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_IDS = [id.strip() for id in os.getenv('CHANNEL_IDS').split(',')]
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
CHECK_INTERVAL_MINUTES = int(os.getenv('CHECK_INTERVAL_MINUTES', '1'))

# Initialize Discord bot and global variables
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Debug: show which intents are enabled (helps verify message_content is True)
logger.info(f"Configured bot intents: {intents}")
failed_channels = set()  # Keep track of channels that have failed
channel_failure_counts = {}  # Track failure counts for each channel

def clone_or_update_repo():
    """
    Clones a repository if it doesn't exist locally or updates it if it already exists.
    Returns True if the repo was cloned fresh or if the file was updated during pull.
    Returns False if pull resulted in no changes to the target file.
    """
    logger.debug("Cloning or updating repository...")
    if os.path.exists(LOCAL_REPO_PATH):
        try:
            repo = git.Repo(LOCAL_REPO_PATH)
            # Store the current commit hash of the file
            old_hash = repo.git.rev_parse('HEAD:' + os.path.relpath(JSON_FILE_PATH, LOCAL_REPO_PATH))
            
            # Pull the latest changes
            repo.remotes.origin.pull()
            
            try:
                # Get new commit hash of the file
                new_hash = repo.git.rev_parse('HEAD:' + os.path.relpath(JSON_FILE_PATH, LOCAL_REPO_PATH))
                # Compare hashes to see if file changed
                was_updated = old_hash != new_hash
                if was_updated:
                    logger.info("Repository pulled and listings file was updated.")
                else:
                    logger.debug("Repository pulled but listings file unchanged.")
                return was_updated
            except git.exc.GitCommandError:
                # If we can't get the new hash, assume file changed to be safe
                logger.warning("Could not determine if file changed, assuming updated")
                return True
                
        except git.exc.InvalidGitRepositoryError:
            os.rmdir(LOCAL_REPO_PATH)  # Remove invalid directory
            git.Repo.clone_from(REPO_URL, LOCAL_REPO_PATH)
            logger.info("Repository cloned fresh.")
            return True
    else:
        git.Repo.clone_from(REPO_URL, LOCAL_REPO_PATH)
        logger.info("Repository cloned fresh.")
        return True

def read_json():
    """
    The function `read_json()` reads a JSON file and returns the loaded data.
    :return: The function `read_json` is returning the data loaded from the JSON file.
    """
    logger.debug(f"Reading JSON file from {JSON_FILE_PATH}...")
    with open(JSON_FILE_PATH, 'r') as file:
        data = json.load(file)
    logger.debug(f"JSON file read successfully, {len(data)} items loaded.")
    return data


def normalize_role_key(role):
    """
    Create a stable normalized key for a role using company, title and URL (if available).
    This reduces mismatches caused by whitespace, capitalization or minor title changes.
    """
    def norm(s):
        return (s or "").strip().lower()

    if isinstance(role, str):
        return role.strip().lower()

    url = role.get('url') if isinstance(role, dict) else None
    if url:
        return f"{norm(role.get('company_name'))}__{norm(role.get('title'))}__{url}"
    return f"{norm(role.get('company_name'))}__{norm(role.get('title'))}"


def format_epoch(val):
    """
    Format Unix timestamp (seconds) as a human-readable date string.
    Returns a formatted date string in the format 'September, 15 @ 07:13 PM'.
    """
    return datetime.fromtimestamp(val).strftime('%B, %d @ %I:%M %p')


# Function to format the message
def format_message(role):
    """
    The `format_message` function generates a formatted message for a new internship posting, including
    details such as company name, role title, location, season, sponsorship, and posting date.
    
    :param role: The role dictionary containing internship information
    :return: A formatted message string for Discord
    """
    # Build safe values
    title = role.get('title', '').strip()
    company = role.get('company_name', '').strip()
    url = role.get('url', '').strip() if role.get('url') else ''
    locations = role.get('locations') or []
    location_str = ' | '.join(locations) if locations else 'Not specified'
    terms = role.get('terms') or []
    term_str = ' | '.join(terms) if terms else 'Not specified'
    sponsorship = role.get('sponsorship')

    # Format the posting date
    posted_on = format_epoch(role.get('date_posted'))

    # Header link uses angle-bracketed URL per example
    header_link = f"(<{url}>)" if url else ""

    parts = []
    parts.append(f">>> ## {company}")
    parts.append(f"## [{title}]{header_link}")

    # Add locations
    parts.append("### Locations: ")
    parts.append(location_str)

    # Add terms
    if len(terms) > 0 and term_str != 'Summer 2026':
        parts.append(f"### Terms: `{term_str}`")

    # Conditionally include Sponsorship
    if sponsorship and str(sponsorship).strip().lower() != 'other':
        parts.append(f"### Sponsorship: `{sponsorship}`")

    parts.append(f"Posted on: {posted_on}")

    return "\n".join(parts)

def compare_roles(old_role, new_role):
    """
    The function `compare_roles` compares two dictionaries representing roles and returns a list of
    changes between them.
    
    :param old_role: The original role dictionary
    :param new_role: The updated role dictionary
    :return: List of changes between the roles
    """
    changes = []
    for key in new_role:
        if old_role.get(key) != new_role.get(key):
            changes.append(f"{key} changed from {old_role.get(key)} to {new_role.get(key)}")
    return changes

async def send_message(message, channel_id, role_key=None):
    """
    The function sends a message to a Discord channel with error handling and retry mechanism.
    
    :param message: The message content to send
    :param channel_id: The Discord channel ID
    :param role_key: Optional role key for tracking messages (company_name + title)
    :return: None
    """
    if channel_id in failed_channels:
        logger.debug(f"Skipping previously failed channel ID {channel_id}")
        return

    try:
        logger.debug(f"Sending message to channel ID {channel_id}...")
        channel = bot.get_channel(int(channel_id))
        
        if channel is None:
            logger.debug(f"Channel {channel_id} not in cache, attempting to fetch...")
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except discord.NotFound:
                logger.warning(f"Channel {channel_id} not found")
                channel_failure_counts[channel_id] = channel_failure_counts.get(channel_id, 0) + 1
                if channel_failure_counts[channel_id] >= MAX_RETRIES:
                    failed_channels.add(channel_id)
                return
            except discord.Forbidden:
                logger.error(f"No permission for channel {channel_id}")
                failed_channels.add(channel_id)  # Immediate blacklist on permission issues
                return
            except Exception as e:
                logger.error(f"Error fetching channel {channel_id}: {e}")
                channel_failure_counts[channel_id] = channel_failure_counts.get(channel_id, 0) + 1
                if channel_failure_counts[channel_id] >= MAX_RETRIES:
                    failed_channels.add(channel_id)
                return

        sent_message = await channel.send(message)
        logger.debug(f"Successfully sent message to channel {channel_id}")
        
        # Reset failure count on success
        if channel_id in channel_failure_counts:
            del channel_failure_counts[channel_id]
        
        await asyncio.sleep(1)  # Rate limiting delay
        
    except Exception as e:
        logger.error(f"Error sending message to channel {channel_id}: {e}")
        channel_failure_counts[channel_id] = channel_failure_counts.get(channel_id, 0) + 1
        if channel_failure_counts[channel_id] >= MAX_RETRIES:
            logger.warning(f"Channel {channel_id} has failed {MAX_RETRIES} times, adding to failed channels")
            failed_channels.add(channel_id)

async def send_messages_to_channels(message, role_key=None):
    """
    Sends a message to multiple Discord channels concurrently with error handling.
    
    :param message: The message content to send
    :param role_key: Optional role key for tracking messages
    :return: None
    """
    tasks = []
    for channel_id in CHANNEL_IDS:
        if channel_id not in failed_channels:
            tasks.append(send_message(message, channel_id, role_key))
    
    # Wait for all messages to be sent
    await asyncio.gather(*tasks, return_exceptions=True)

async def check_for_new_roles():
    """
    The function checks for new roles, sending appropriate messages to Discord channels.
    Only processes the full comparison if the repository was updated.
    """
    logger.debug("Checking for new roles...")
    has_updates = clone_or_update_repo()
    
    if not has_updates:
        logger.debug("No updates to listings file, skipping check.")
        return
        
    new_data = read_json()
    
    # Compare with previous data if exists
    if os.path.exists('previous_data.json'):
        with open('previous_data.json', 'r') as file:
            old_data = json.load(file)
        logger.debug("Previous data loaded.")
    else:
        old_data = []
        logger.debug("No previous data found.")

    # Initialize a priority queue for new roles
    new_roles_heap = []
    
    # Create a dictionary for quick lookup of old roles using normalized keys
    old_roles_dict = { normalize_role_key(role): role for role in old_data }

    for new_role in new_data:
        old_role = old_roles_dict.get(normalize_role_key(new_role))

        # Get boolean values directly since they are stored as proper booleans
        new_active = new_role.get('active', False)
        new_is_visible = new_role.get('is_visible', True)  # Default to True since all existing entries use True
        
        # Check for new, visible, and active roles only
        if not old_role and new_is_visible and new_active:
            # Check if the role was updated within the last 5 days
            days_since_posted = (datetime.now().timestamp() - new_role['date_posted']) / (24 * 60 * 60)
            if days_since_posted <= 5:
                # Add to priority queue in chronological order (oldest first)
                # Using (timestamp, counter) as the key to ensure unique ordering
                counter = len(new_roles_heap)  # Use length as a unique secondary key
                heapq.heappush(new_roles_heap, (new_role['date_posted'], counter, new_role))
                logger.debug(f"New role found: {new_role['title']} at {new_role['company_name']}")
            else:
                logger.debug(f"Skipping old role: {new_role['title']} at {new_role['company_name']} (posted {days_since_posted:.1f} days ago)")

    logger.debug(f"Found {len(new_roles_heap)} new roles, processing in chronological order")

    # Process roles in order (oldest first)
    while new_roles_heap:
        _, _, role = heapq.heappop(new_roles_heap)  # Unpack timestamp, counter, and role
        role_key = normalize_role_key(role)
        message = format_message(role)
        await send_messages_to_channels(message, role_key)

    # Update previous data
    with open('previous_data.json', 'w') as file:
        json.dump(new_data, file)
    logger.debug("Updated previous data with new data.")

@bot.event
async def on_ready():
    """
    Event handler for when the bot is ready and connected to Discord.
    """
    logger.info(f'Logged in as {bot.user}')
    logger.info(f'Bot is ready and monitoring {len(CHANNEL_IDS)} channels')

    # Initial check for new roles on startup
    await check_for_new_roles()

    # Start the scheduled job loop
    while True:
        schedule.run_pending()  # This will respect the CHECK_INTERVAL_MINUTES setting
        await asyncio.sleep(1)  # Small delay to prevent busy-waiting

# Graceful shutdown handler
def signal_handler(sig, frame):
    """Handle graceful shutdown"""
    logger.info("\nShutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Wrapper for the async function to work with schedule
def run_check_for_new_roles():
    """Wrapper to run the async check_for_new_roles in the bot's event loop"""
    if bot.loop.is_running():
        bot.loop.create_task(check_for_new_roles())
    else:
        logger.warning("Bot event loop is not running, skipping scheduled check")

# Schedule the job with configurable interval
schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(run_check_for_new_roles)

def main():
    """Main function to run the bot"""
    # Run the bot
    logger.info("Starting bot with environment configuration...")
    logger.info(f"Monitoring {len(CHANNEL_IDS)} channels every {CHECK_INTERVAL_MINUTES} minutes")
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()