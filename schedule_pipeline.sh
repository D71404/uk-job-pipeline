#!/bin/bash

# ============================================
# Daily Job Pipeline Scheduler
# ============================================
# This script runs the job pipeline and logs the results
# Designed to be executed by cron daily

# Change to script directory
cd "$(dirname "$0")"

# Load environment
source .env 2>/dev/null || true

# Set up Python environment (adjust path as needed)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Log file with timestamp
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/pipeline_$(date +%Y%m%d_%H%M%S).log"

# Run the pipeline
echo "========================================" | tee -a "$LOG_FILE"
echo "Starting Job Pipeline" | tee -a "$LOG_FILE"
echo "Timestamp: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Execute pipeline with full output logging
python3 job_pipeline.py 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "Pipeline finished with exit code: $EXIT_CODE" | tee -a "$LOG_FILE"
echo "Timestamp: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Optional: Send notification on failure
if [ $EXIT_CODE -ne 0 ]; then
    echo "⚠️  Pipeline failed! Check logs at: $LOG_FILE"
    # Add notification commands here (email, Slack, etc.)
fi

# Clean up old logs (keep last 30 days)
find "$LOG_DIR" -name "pipeline_*.log" -mtime +30 -delete

exit $EXIT_CODE
