#!/bin/bash

# ============================================
# Cron Setup Script
# ============================================
# This script sets up the daily cron job for the pipeline

echo "Setting up daily job pipeline cron job..."

# Get the absolute path to this directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCHEDULE_SCRIPT="$SCRIPT_DIR/schedule_pipeline.sh"

# Make scripts executable
chmod +x "$SCHEDULE_SCRIPT"
chmod +x "$SCRIPT_DIR/job_pipeline.py"

echo "Scripts made executable"

# Create cron entry (runs daily at 9 AM)
CRON_SCHEDULE="0 9 * * *"  # Change this to your preferred time
CRON_JOB="$CRON_SCHEDULE $SCHEDULE_SCRIPT"

# Check if cron job already exists
crontab -l 2>/dev/null | grep -F "$SCHEDULE_SCRIPT" > /dev/null

if [ $? -eq 0 ]; then
    echo "Cron job already exists. Updating..."
    # Remove old entry and add new one
    crontab -l 2>/dev/null | grep -vF "$SCHEDULE_SCRIPT" | crontab -
fi

# Add new cron entry
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo ""
echo "✅ Cron job installed successfully!"
echo ""
echo "Schedule: Daily at 9:00 AM"
echo "Command: $SCHEDULE_SCRIPT"
echo ""
echo "To view your crontab:"
echo "  crontab -l"
echo ""
echo "To edit your crontab:"
echo "  crontab -e"
echo ""
echo "To remove the cron job:"
echo "  crontab -l | grep -vF '$SCHEDULE_SCRIPT' | crontab -"
echo ""
echo "Logs will be saved in: $SCRIPT_DIR/logs/"
echo ""
echo "To test the pipeline now, run:"
echo "  $SCHEDULE_SCRIPT"
echo ""
