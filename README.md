# Automated UK Job Application Pipeline

A fully automated daily agent that scrapes UK job portals for visa-sponsored positions and uses Claude AI to tailor CVs for each opportunity.

## 🎯 What It Does

This pipeline runs daily to:

1. **Scrape** job openings from major UK portals across 4 niches:
   - AI Engineer & Marketing (Otta, Reed, LinkedIn)
   - PhD positions (FindAPhD, Jobs.ac.uk)
   - Teaching jobs (TES, DfE Teaching Vacancies)

2. **Filter** for visa sponsorship by checking database and parsing descriptions

3. **Insert** jobs into Supabase (auto-skips duplicates via unique URL constraint)

4. **Tailor** CVs using Claude AI to match each job's requirements

5. **Update** status to `CV_TWEAKED` for Lovable dashboard Kanban board

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements_pipeline.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Initialize database
# Run job_pipeline_schema.sql in Supabase SQL Editor

# 4. Upload master CVs
python3 upload_master_cv.py --field AI_ENGINEER --template my_cv.md
# Edit and upload for each field

# 5. Test the pipeline
python3 job_pipeline.py --scrape  # Test scraping only
python3 job_pipeline.py           # Run full pipeline

# 6. Setup daily automation
./setup_cron.sh
```

## 📁 Project Structure

### Core Pipeline
- **job_pipeline.py** - Main orchestrator
- **job_pipeline_client.py** - Supabase database client
- **uk_job_scrapers.py** - Multi-portal scraping engine
- **cv_optimizer.py** - Claude AI CV tailoring

### Database
- **job_pipeline_schema.sql** - Complete Supabase schema
- Tables: `sponsored_companies`, `jobs`, `master_cvs`, `tweaked_cvs`

### Automation
- **schedule_pipeline.sh** - Daily execution wrapper
- **setup_cron.sh** - Cron job installer
- **upload_master_cv.py** - CV management utility

### Documentation
- **README_PIPELINE.md** - Comprehensive setup guide
- **README_JOB_SCRAPER.md** - Scraping documentation
- **README_LOVABLE_INTEGRATION.md** - Lovable dashboard integration

## 🔑 Required API Keys

Get free API keys from:
- **Supabase**: https://supabase.com (PostgreSQL database)
- **Firecrawl**: https://firecrawl.dev/app (Job scraping)
- **Anthropic**: https://console.anthropic.com/ (Claude AI for CV optimization)

Add to `.env`:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-key-here
FIRECRAWL_API_KEY=fc-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## 📊 Database Schema

```sql
-- Job fields (niches)
job_field: 'AI_ENGINEER' | 'TEACHING' | 'PHD' | 'MARKETING'

-- Application status flow
application_status: 'NEW' → 'CV_TWEAKED' → 'APPLIED' → 'REJECTED'
```

### Tables

1. **sponsored_companies** - Companies that sponsor UK visas
2. **jobs** - All discovered job openings (unique by URL)
3. **master_cvs** - One template CV per niche
4. **tweaked_cvs** - AI-optimized CVs for each job

## 🎨 Features

✅ Multi-portal scraping (8+ job boards)
✅ Smart sponsorship detection
✅ Claude AI CV optimization
✅ Automatic duplicate prevention
✅ Status tracking & Kanban integration
✅ Daily scheduling with cron
✅ Comprehensive logging
✅ Quality checking
✅ Partial runs (scrape-only, tailor-only)

## 🔧 Usage

```bash
# Run full pipeline
python3 job_pipeline.py

# Only scrape jobs
python3 job_pipeline.py --scrape

# Only tailor CVs for existing NEW jobs
python3 job_pipeline.py --tailor --limit 10

# Show statistics
python3 job_pipeline.py --stats

# Manage master CVs
python3 upload_master_cv.py --list
python3 upload_master_cv.py AI_ENGINEER cv.md
```

## 📈 Expected Results

After running daily for 1 week:

- 100-500 jobs scraped
- 10-50 sponsored positions found
- CVs tailored automatically for each job
- Lovable dashboard Kanban board filling up
- Zero manual intervention required

## 🛡️ Security

- `.env` file excluded from git (never commit credentials)
- `.gitignore` configured for sensitive files
- Row Level Security supported in Supabase schema
- API key validation before running

## 📝 Logging

Daily logs saved to `logs/pipeline_YYYYMMDD_HHMMSS.log`

```bash
# View recent logs
tail -f logs/pipeline_*.log

# Check pipeline stats
python3 job_pipeline.py --stats
```

## 🔄 Workflow

```
┌──────────────┐
│   SCRAPE     │ Otta, Reed, LinkedIn, FindAPhD, TES
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   FILTER     │ Check sponsorship (DB + keywords)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   INSERT     │ Save to jobs table (status = NEW)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   TAILOR     │ Claude AI optimizes CV
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   UPDATE     │ Status → CV_TWEAKED
└──────────────┘
```

## 🤝 Integration with Lovable

Jobs automatically sync to your Lovable dashboard:
- **NEW** - Just scraped, awaiting CV
- **CV_TWEAKED** - Ready to apply
- **APPLIED** - Application submitted
- **REJECTED** - Didn't get the job

## 📚 Documentation

- **README_PIPELINE.md** - Complete setup guide
- **README_JOB_SCRAPER.md** - Scraping details
- **README_LOVABLE_INTEGRATION.md** - Dashboard integration

## 🛠️ Tech Stack

- **Python 3.9+**
- **Supabase** (PostgreSQL)
- **Firecrawl API** (Web scraping)
- **Anthropic Claude** (AI CV optimization)
- **Cron** (Daily scheduling)

## 🐛 Troubleshooting

### No master CVs found
```bash
python3 upload_master_cv.py --field AI_ENGINEER --template cv.md
# Edit template, then:
python3 upload_master_cv.py AI_ENGINEER cv.md
```

### Duplicate job URL skipped
This is normal - pipeline prevents duplicates automatically.

### Cron not running
```bash
crontab -l  # Check if installed
./setup_cron.sh  # Reinstall
./schedule_pipeline.sh  # Test manually
```

### No jobs found
- Check Firecrawl API key
- Verify job portals are accessible
- Review logs: `tail -f logs/pipeline_*.log`

## 📄 License

Personal use project. Respect job portal terms of service.

## 🙏 Credits

Built with Claude Code by Anthropic.

---

**Ready to automate your job search?** 🚀

1. Follow the Quick Start above
2. Run `./quick_start.sh` for interactive setup
3. Let the pipeline work for you daily!

For detailed documentation, see **README_PIPELINE.md**.
