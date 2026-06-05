# Automated Job Application Pipeline

A fully automated daily pipeline that scrapes UK job portals, filters for visa-sponsored positions, and uses Claude AI to tailor CVs for each opportunity.

## 🎯 What It Does

1. **Scrapes** job openings from major UK portals for 4 niches:
   - AI Engineer (Otta, Reed, LinkedIn)
   - Marketing Executive (Otta, Reed, LinkedIn)
   - PhD positions (FindAPhD, Jobs.ac.uk)
   - Teaching positions (TES, DfE Teaching Vacancies)

2. **Checks** if jobs offer visa sponsorship by:
   - Looking up company in your `sponsored_companies` database
   - Parsing job descriptions for sponsorship keywords

3. **Inserts** sponsored jobs into Supabase `jobs` table
   - Automatically skips duplicates (via unique URL constraint)
   - Sets initial status to `NEW`

4. **Tailors** CVs for each new job using Claude AI:
   - Fetches master CV for the job's field from `master_cvs` table
   - Analyzes job requirements
   - Rewrites bullet points to match employer needs
   - Saves tailored CV to `tweaked_cvs` table

5. **Updates** job status to `CV_TWEAKED`
   - Automatically moves job to next Kanban column in Lovable dashboard

## 📁 Project Structure

```
AI Automations/
├── job_pipeline.py              # Main orchestrator script
├── job_pipeline_client.py       # Supabase database client
├── uk_job_scrapers.py          # Job portal scrapers
├── cv_optimizer.py             # Claude AI CV tailoring engine
├── job_pipeline_schema.sql     # Database schema (run in Supabase)
├── schedule_pipeline.sh        # Daily execution wrapper
├── setup_cron.sh               # Cron installation script
├── requirements_pipeline.txt   # Python dependencies
├── .env.example                # Environment template
└── logs/                       # Daily execution logs
```

## 🚀 Setup Instructions

### 1. Install Dependencies

```bash
cd "Desktop/AI Automations"
pip install -r requirements_pipeline.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
nano .env  # or your preferred editor
```

Required credentials:
- **SUPABASE_URL** and **SUPABASE_KEY**: From your Supabase project settings
- **FIRECRAWL_API_KEY**: Get from https://firecrawl.dev/app
- **ANTHROPIC_API_KEY**: Get from https://console.anthropic.com/

### 3. Initialize Database

Run the schema in your Supabase SQL Editor:

```bash
# Copy the schema
cat job_pipeline_schema.sql

# Then paste and execute in Supabase SQL Editor
# https://app.supabase.com/project/YOUR_PROJECT/sql
```

This creates:
- `sponsored_companies` - Companies that sponsor visas
- `jobs` - Discovered job openings
- `master_cvs` - Your master CV templates (one per field)
- `tweaked_cvs` - AI-tailored CVs for each job

### 4. Upload Master CVs

You need to add one master CV per job field. Use the Supabase dashboard or run SQL:

```sql
-- Example: Insert master CV for AI Engineer field
INSERT INTO master_cvs (field, cv_content_markdown) VALUES (
    'AI_ENGINEER',
    '# Your Name

## Professional Summary
[Your summary here...]

## Experience
[Your experience here...]

## Skills
[Your skills here...]

## Education
[Your education here...]'
);

-- Repeat for other fields: 'MARKETING', 'PHD', 'TEACHING'
```

### 5. Test the Pipeline

Run manually first to test:

```bash
# Full pipeline test
python3 job_pipeline.py

# Or test individual steps:
python3 job_pipeline.py --scrape   # Only scrape jobs
python3 job_pipeline.py --tailor   # Only tailor CVs
python3 job_pipeline.py --stats    # Show statistics
```

### 6. Setup Daily Automation

Install cron job to run daily at 9 AM:

```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

Or manually add to crontab:

```bash
crontab -e

# Add this line (change time as needed):
0 9 * * * /path/to/Desktop/AI\ Automations/schedule_pipeline.sh
```

## 📊 Database Schema

### Tables

**sponsored_companies**
- Stores companies known to sponsor UK visas
- Fields: `id`, `company_name` (UNIQUE), `industry`, `created_at`

**jobs**
- All discovered job openings
- Fields: `id`, `company_name`, `job_title`, `job_url` (UNIQUE), `description`, `field` (ENUM), `status` (ENUM), `created_at`
- Status flow: `NEW` → `CV_TWEAKED` → `APPLIED` → `REJECTED`

**master_cvs**
- One master CV template per niche
- Fields: `id`, `field` (UNIQUE), `cv_content_markdown`, `updated_at`

**tweaked_cvs**
- AI-optimized CVs for specific jobs
- Fields: `id`, `job_id` (UNIQUE FK), `tailored_cv_markdown`, `created_at`

### ENUMs

```sql
job_field: 'AI_ENGINEER' | 'TEACHING' | 'PHD' | 'MARKETING'
application_status: 'NEW' | 'CV_TWEAKED' | 'APPLIED' | 'REJECTED'
```

## 🔧 Configuration Options

### Environment Variables

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-key-here
FIRECRAWL_API_KEY=fc-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional
MAX_JOBS_PER_RUN=50        # Limit jobs processed per run
LOG_LEVEL=INFO             # Logging verbosity
```

### Command Line Options

```bash
# Run full pipeline
python3 job_pipeline.py

# Only scrape and insert jobs (skip CV tailoring)
python3 job_pipeline.py --scrape

# Only tailor CVs for existing NEW jobs (skip scraping)
python3 job_pipeline.py --tailor

# Tailor limited number of CVs
python3 job_pipeline.py --tailor --limit 10

# Show pipeline statistics
python3 job_pipeline.py --stats
```

## 🎨 Lovable Dashboard Integration

Jobs automatically flow through your Kanban board:

1. **NEW** - Just inserted, awaiting CV tailoring
2. **CV_TWEAKED** - CV ready, should apply
3. **APPLIED** - Application submitted (manual update)
4. **REJECTED** - Didn't get the job (manual update)

Update status in Lovable dashboard and it syncs to Supabase automatically.

## 📝 Logs

Daily logs are saved in `logs/pipeline_YYYYMMDD_HHMMSS.log`

View recent logs:
```bash
tail -f logs/pipeline_*.log
```

## 🔍 Monitoring

Check pipeline health:

```bash
# View statistics
python3 job_pipeline.py --stats

# Check database directly in Supabase
# https://app.supabase.com/project/YOUR_PROJECT/editor
```

Query useful stats:

```sql
-- Jobs by status
SELECT status, COUNT(*) FROM jobs GROUP BY status;

-- Jobs by field
SELECT field, COUNT(*) FROM jobs GROUP BY field;

-- Recent jobs needing CVs
SELECT * FROM jobs WHERE status = 'NEW' ORDER BY created_at DESC LIMIT 20;

-- Check tailored CVs
SELECT j.job_title, j.company_name, t.created_at
FROM jobs j
JOIN tweaked_cvs t ON j.id = t.job_id
ORDER BY t.created_at DESC;
```

## 🛡️ Sponsored Company Management

Add companies known to sponsor:

```sql
INSERT INTO sponsored_companies (company_name, industry)
VALUES ('DeepMind', 'AI/ML');
```

Or use Python:

```python
from job_pipeline_client import JobPipelineClient

db = JobPipelineClient()
db.add_sponsored_company('OpenAI', 'AI Research')
```

## 🤖 CV Optimization Details

The CV optimizer uses Claude Sonnet 4.5 to:

1. **Analyze** job requirements
   - Extract key skills
   - Identify must-have experiences
   - Detect company values

2. **Tailor** master CV
   - Rewrite bullet points to match requirements
   - Incorporate priority keywords naturally
   - Quantify achievements where possible
   - Reorder sections by relevance

3. **Quality Check**
   - Validate no placeholders
   - Check for required sections
   - Ensure appropriate length (< 2 pages)

Quality scores below 70/100 are logged but still saved.

## 🔧 Troubleshooting

### "No master CVs available"
Upload master CVs to the `master_cvs` table for each job field you're targeting.

### "Duplicate job URL skipped"
This is normal - the pipeline automatically prevents duplicate insertions.

### "Firecrawl API rate limit"
Firecrawl has usage limits. Reduce scraping frequency or upgrade your plan.

### "No jobs found"
- Check that job portals are accessible
- Verify Firecrawl API key is valid
- Check logs for specific errors

### Cron job not running
```bash
# Check if cron is installed
crontab -l

# Check system logs
grep CRON /var/log/syslog  # Linux
log show --predicate 'process == "cron"' --last 1d  # macOS

# Test script manually
./schedule_pipeline.sh
```

## 🎯 Customization

### Add New Job Portals

Edit `uk_job_scrapers.py` and add new scraper methods:

```python
def scrape_new_portal(self, keywords: List[str]) -> List[Dict[str, Any]]:
    # Your scraper implementation
    pass
```

Then call it in `scrape_all_fields()`.

### Add New Job Fields

1. Update ENUM in SQL:
```sql
ALTER TYPE job_field ADD VALUE 'NEW_FIELD';
```

2. Add master CV for the field
3. Update scrapers to include the new field

### Customize CV Template

Modify the prompt in `cv_optimizer.py` → `_generate_tailored_cv()` method.

## 📚 API Documentation

See individual module docstrings:

```python
# Database operations
from job_pipeline_client import JobPipelineClient
help(JobPipelineClient)

# Scraping
from uk_job_scrapers import UKJobScrapers
help(UKJobScrapers)

# CV optimization
from cv_optimizer import CVOptimizer
help(CVOptimizer)
```

## 🚨 Important Notes

1. **Master CVs Required**: Pipeline will fail if no master CVs exist
2. **API Costs**: Monitor Firecrawl and Anthropic usage
3. **Duplicate Handling**: Automatic via unique URL constraint
4. **CV Quality**: Always review AI-generated CVs before applying
5. **Sponsorship Detection**: Not 100% accurate - manual verification recommended

## 🎉 Success Metrics

After running for a few days, you should see:

- **50-200 jobs** scraped per day across all niches
- **5-20 sponsored jobs** filtered per day
- **CVs tailored** for all NEW jobs
- **Zero manual intervention** required for daily operation

Check your Lovable dashboard to see the Kanban board filling up automatically!

## 📞 Support

For issues or questions:
1. Check logs: `tail -f logs/pipeline_*.log`
2. Run with `--stats` to check database state
3. Test individual components (`--scrape` or `--tailor`)

## 📄 License

This is a custom pipeline for personal use. Respect job portal terms of service and scraping policies.
