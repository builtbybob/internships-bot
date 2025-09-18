#!/bin/bash

# Configuration
MAX_LOG_SIZE_MB=10
LOG_FILE="nohup.out"
BACKUP_COUNT=5

# Function to rotate logs
rotate_logs() {
    if [ -f "$LOG_FILE" ]; then
        size=$(du -m "$LOG_FILE" | cut -f1)
        if [ $size -gt $MAX_LOG_SIZE_MB ]; then
            # Rotate existing backup logs
            for i in $(seq $((BACKUP_COUNT-1)) -1 1); do
                if [ -f "${LOG_FILE}.$i" ]; then
                    mv "${LOG_FILE}.$i" "${LOG_FILE}.$((i+1))"
                fi
            done
            # Move current log to .1
            mv "$LOG_FILE" "${LOG_FILE}.1"
            # Create new empty log file
            touch "$LOG_FILE"
        fi
    fi
}

# Start the bot with log rotation
while true; do
    rotate_logs
    nohup python mainbot.py >> "$LOG_FILE" 2>&1
    sleep 1
done