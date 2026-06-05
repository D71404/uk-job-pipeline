# 🔥 Firecrawl Job Scraper

Automated job listing extraction from company websites using Firecrawl's Crawl + Extract APIs.

## How It Works

```
1. CRAWL    → Discover all pages on the website
2. FILTER   → Identify career/jobs URLs using pattern matching
3. EXTRACT  → Use LLM to extract structured job data
4. SAVE     → Export to Excel (.xlsx)
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Firecrawl API Key

Sign up at [firecrawl.dev/app](https://firecrawl.dev/app) and copy your API key.

### 3. Set API Key

```bash
# Option 1: Environment variable (recommended)
export FIRECRAWL_API_KEY="fc-your-api-key"

# Option 2: Pass as argument
python job_scraper.py https://example.com --api-key fc-your-api-key
```

## Usage

### Basic Usage (Single Company)

```bash
# Quick scrape (50 pages max)
python job_scraper.py https://stripe.com

# Deep scrape (200 pages, finds more jobs)
python job_scraper.py https://stripe.com --limit 200

# Custom output file
python job_scraper.py https://airbnb.com --output airbnb_jobs.xlsx
```

### Advanced Usage (Batch Processing)

```bash
# Scrape single company with deep crawl
python job_scraper_advanced.py --url https://notion.so --name "Notion" --deep

# Batch scrape multiple companies
python job_scraper_advanced.py --companies companies_example.txt --output tech_jobs.xlsx
```

### Create Company List File

Create a text file with companies to scrape:

```text
# companies.txt
Stripe, https://stripe.com
Airbnb, https://airbnb.com
Notion, https://notion.so
Figma, https://figma.com
```

Then run:

```bash
python job_scraper_advanced.py --companies companies.txt --deep
```

## Output Format

Excel file with columns:

| Column | Description |
|--------|-------------|
| Title | Job title |
| Company | Company name |
| Department | Team/department |
| Location | City, country, or Remote |
| Job Type | Full-time, Contract, etc. |
| Salary Range | Compensation (if listed) |
| Description | Full job description |
| Requirements | Required qualifications |
| Responsibilities | Job duties |
| Apply URL | Link to apply |
| Posted Date | When job was posted |
| Source URL | Where job was found |
| Extracted At | Timestamp |

## Credit Usage

Firecrawl credits consumed:

| Action | Credits |
|--------|---------|
| Crawl (per page) | 1 |
| Extract (per request) | Based on tokens (1 credit = 15 tokens) |

**Example:** Crawling 50 pages + extracting from 5 career pages ≈ 50-100 credits

## Career URL Patterns

The scraper automatically detects these URL patterns:

- `/careers`, `/careers/engineering`
- `/jobs`, `/jobs/frontend-developer`
- `/openings`, `/positions`
- `/hiring`, `/join-us`, `/work-with-us`
- `/team`, `/employment`, `/vacancies`

## Troubleshooting

### No jobs found

1. **Increase limit**: `python job_scraper.py URL --limit 200`
2. **Try deep mode** (advanced): `--deep` flag
3. **Check URL**: Ensure the company has a careers page

### API Errors

```bash
# Verify API key
echo $FIRECRAWL_API_KEY

# Check credits at https://firecrawl.dev/app
```

### Rate Limits

The scraper has built-in delays. If you hit limits:
- Wait a few minutes
- Reduce `--limit`
- Use batch mode with fewer companies

## File Structure

```
.
├── job_scraper.py              # Simple version
├── job_scraper_advanced.py     # Batch processing + smart filtering
├── requirements.txt            # Dependencies
├── companies_example.txt       # Example batch file
├── jobs_YYYYMMDD_HHMMSS.xlsx   # Output files
└── checkpoints/                # Auto-saved progress (batch mode)
```

## Customization

### Change Job Schema

Edit the `JOB_SCHEMA` in `job_scraper.py` to extract different fields:

```python
JOB_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "your_custom_field": {"type": "string"},
                    # ... add more fields
                }
            }
        }
    }
}
```

### Filter by Department

Add to `job_scraper_advanced.py`:

```python
def filter_by_department(jobs: List[JobListing], dept: str) -> List[JobListing]:
    return [j for j in jobs if dept.lower() in j.department.lower()]
```

## License

MIT - Use freely for job searching, research, or building job boards.
