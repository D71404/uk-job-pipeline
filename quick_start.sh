#!/bin/bash

# ============================================
# Job Pipeline Quick Start Script
# ============================================

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Automated Job Application Pipeline - Quick Start       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}✗ Missing .env file${NC}"
    echo ""
    echo "Please create .env from the template:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Edit with your API keys"
    echo ""
    echo "You'll need:"
    echo "  - SUPABASE_URL and SUPABASE_KEY"
    echo "  - FIRECRAWL_API_KEY"
    echo "  - ANTHROPIC_API_KEY"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Found .env configuration${NC}"

# Check if Python dependencies are installed
echo ""
echo "Checking dependencies..."

if ! python3 -c "import supabase" 2>/dev/null; then
    echo -e "${YELLOW}⚠ Missing dependencies${NC}"
    echo ""
    echo "Installing required packages..."
    pip3 install -r requirements_pipeline.txt

    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Installation failed${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Dependencies installed${NC}"

# Check if database schema is initialized
echo ""
echo "Checking database setup..."
echo "Please ensure you have run job_pipeline_schema.sql in your Supabase SQL Editor"
echo "URL: https://app.supabase.com/project/YOUR_PROJECT/sql"
echo ""

read -p "Have you run the database schema? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Please run the schema first:"
    echo "  1. Open: https://app.supabase.com/project/YOUR_PROJECT/sql"
    echo "  2. Copy contents of: job_pipeline_schema.sql"
    echo "  3. Paste and execute in SQL Editor"
    echo ""
    exit 1
fi

# Check master CVs
echo ""
echo "Checking master CVs..."
python3 upload_master_cv.py --list

echo ""
read -p "Do you have master CVs for all fields? (y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${YELLOW}You need to upload master CVs before running the pipeline${NC}"
    echo ""
    echo "Create a template:"
    echo "  python3 upload_master_cv.py --field AI_ENGINEER --template ai_cv.md"
    echo ""
    echo "Upload your CV:"
    echo "  python3 upload_master_cv.py AI_ENGINEER ai_cv.md"
    echo ""
    exit 1
fi

# Offer to test the pipeline
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}✓ Setup complete!${NC}"
echo ""
echo "What would you like to do?"
echo ""
echo "  1) Test scraping only (no CV tailoring)"
echo "  2) Test full pipeline (scrape + tailor CVs)"
echo "  3) Show statistics"
echo "  4) Setup daily cron job"
echo "  5) Exit"
echo ""
read -p "Choose option [1-5]: " -n 1 -r
echo ""

case $REPLY in
    1)
        echo ""
        echo -e "${BLUE}Running scraper test...${NC}"
        python3 job_pipeline.py --scrape
        ;;
    2)
        echo ""
        echo -e "${BLUE}Running full pipeline...${NC}"
        echo "This will scrape jobs and tailor CVs. It may take 10-30 minutes."
        echo ""
        read -p "Continue? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 job_pipeline.py
        fi
        ;;
    3)
        echo ""
        python3 job_pipeline.py --stats
        ;;
    4)
        echo ""
        echo -e "${BLUE}Setting up daily cron job...${NC}"
        chmod +x setup_cron.sh
        ./setup_cron.sh
        ;;
    5)
        echo ""
        echo "Setup complete. To run the pipeline manually:"
        echo "  python3 job_pipeline.py"
        echo ""
        echo "To setup daily automation:"
        echo "  ./setup_cron.sh"
        echo ""
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo ""
echo "  • Check logs: tail -f logs/pipeline_*.log"
echo "  • View jobs: https://app.supabase.com/project/YOUR_PROJECT/editor"
echo "  • Dashboard: Your Lovable app URL"
echo ""
echo "For help, see: README_PIPELINE.md"
echo ""
