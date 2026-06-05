# Lovable Job Scraper Integration

Complete integration between Firecrawl job scraper and your Lovable app.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│   Lovable    │────▶│  API Server  │────▶│  bd_job_reviews │────▶│ bd_job_intel │
│  (UI Pages)  │     │  (Python)    │     │  (Staging)      │     │ (Production) │
└──────────────┘     └──────────────┘     └─────────────────┘     └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Firecrawl   │
                    │  (Scraping)  │
                    └──────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Supabase Schema

Run `supabase_schema.sql` in your Supabase SQL Editor:

```sql
-- Creates:
-- - bd_job_reviews (staging table)
-- - approve_job_to_intel() function
-- - reject_job_review() function
-- - pending_job_reviews view
-- - RLS policies
```

### 3. Configure Environment

Your `.env` is already configured with:

```bash
FIRECRAWL_API_KEY=fc-...
SUPABASE_URL=https://jljnfeyisbteqfqveopr.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIs...
```

### 4. Start API Server

```bash
python api_server.py
# or
uvicorn api_server:app --reload --port 8000
```

Server runs at `http://localhost:8000`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/scrape` | Scrape jobs from URL → review queue |
| GET | `/reviews` | List pending reviews |
| GET | `/review/{id}` | Get review details |
| POST | `/approve` | Approve job → bd_job_intel |
| POST | `/reject` | Reject job |
| GET | `/stats` | Queue statistics |
| GET | `/health` | Health check |

### Example: Scrape Jobs

```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.turing.com",
    "company_name": "Turing",
    "limit": 50
  }'
```

Response:
```json
{
  "success": true,
  "message": "Found 14 jobs. Saved to review queue.",
  "jobs_found": 14,
  "review_ids": ["uuid-1", "uuid-2", ...]
}
```

### Example: List Pending Reviews

```bash
curl http://localhost:8000/reviews
```

Response:
```json
[
  {
    "id": "uuid-here",
    "job_title": "Senior Software Engineer",
    "company_name": "Turing",
    "location": "Remote",
    "remote_type": "Remote",
    "job_category": "Engineering",
    "seniority_level": "Senior",
    "created_at": "2024-..."
  }
]
```

### Example: Approve Job

```bash
curl -X POST http://localhost:8000/approve \
  -H "Content-Type: application/json" \
  -d '{
    "review_id": "uuid-here",
    "reviewer_user_id": "user-uuid-here"
  }'
```

## Lovable Pages Setup

### Page 1: Scrape Jobs

**Components:**
- URL input field
- Company name input
- "Scrape" button
- Results display

**Workflow:**
1. User enters URL and company name
2. POST to `/scrape`
3. Show results: "Found X jobs in review queue"

**Supabase Action (HTTP Request):**
```javascript
// On button click
const response = await fetch('http://localhost:8000/scrape', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    url: urlInput.value,
    company_name: companyInput.value,
    limit: 50
  })
});
const data = await response.json();
```

### Page 2: Review Queue

**Components:**
- List of pending jobs
- Job detail view
- Approve/Reject buttons

**Data Source:**
```sql
SELECT * FROM pending_job_reviews;
```

**Actions:**
- **Approve**: Call `approve_job_to_intel(review_id, auth.uid())`
- **Reject**: Call `reject_job_review(review_id, auth.uid(), notes)`

### Page 3: Stats Dashboard

**Components:**
- Pending count
- Approved count
- Rejected count
- Recent activity

**Data Source:**
```bash
GET /stats
```

## Database Schema

### bd_job_reviews (Staging)

Mirrors `bd_job_intel` + review workflow fields:

| Column | Purpose |
|--------|---------|
| `review_status` | pending / approved / rejected / needs_info |
| `reviewed_by` | User who reviewed |
| `reviewed_at` | Review timestamp |
| `reviewer_notes` | Rejection reason, etc. |
| `raw_scraped_data` | Original scraped JSON |
| `source_url` | URL that was scraped |

### Workflow Functions

**approve_job_to_intel(review_id, reviewer_user_id)**
- Copies job to `bd_job_intel`
- Links company if found by name
- Updates review status to 'approved'
- Returns new job ID

**reject_job_review(review_id, reviewer_user_id, notes)**
- Updates review status to 'rejected'
- Stores reviewer notes

## Data Mapping

Scraped fields → bd_job_intel:

| Scraped | bd_job_intel | Notes |
|---------|--------------|-------|
| title | job_title | |
| (normalized) | job_title_normalized | swe, swe_frontend, etc. |
| company | company_name | Temp until linked |
| location | location | |
| (detected) | remote_type | Remote/Hybrid/On-site |
| (detected) | job_category | Engineering/Data/etc. |
| (detected) | seniority_level | Junior/Mid/Senior/etc. |
| description | full_job_description | |
| (summarized) | job_description_summary | Auto-generated |
| salary_range | salary_min/max | Parsed from text |
| requirements | skills_mentioned | Extracted skills array |
| requirements | required_experiences | Parsed bullets |
| (detected) | years_experience_min/max | From text |

## Testing

```bash
# Test CLI tool
python test_lovable.py

# Test API
curl http://localhost:8000/health

# Full test
python job_scraper.py https://www.turing.com --supabase --company "Turing"
```

## Deployment

### Option 1: Local (Development)
```bash
python api_server.py
```

### Option 2: Cloud (Production)
Deploy to Render, Railway, or Fly.io:

```bash
# Render (render.yaml)
services:
  - type: web
    name: job-scraper-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn api_server:app --host 0.0.0.0 --port $PORT
```

### Option 3: Supabase Edge Functions
Convert to Deno/Edge Function for serverless (advanced).

## Security Notes

1. **API Key**: Use service_role key only server-side
2. **CORS**: Restrict `allow_origins` to your Lovable domain in production
3. **RLS**: Enabled on `bd_job_reviews` - authenticated users only
4. **Rate Limiting**: Add rate limiting for production API

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No jobs found" | Increase `--limit` or check URL |
| "Supabase connection failed" | Check SUPABASE_URL and SUPABASE_KEY |
| "Company not linked" | Add company to `bd_companies` first |
| Duplicate jobs | Check `job_url` uniqueness in your app |

## Files Reference

| File | Purpose |
|------|---------|
| `api_server.py` | FastAPI server for Lovable |
| `supabase_lovable_client.py` | Supabase integration with schema mapping |
| `supabase_schema.sql` | Database setup SQL |
| `job_scraper.py` | Core scraper (Firecrawl) |
| `test_lovable.py` | CLI test tool |

## Next Steps

1. ✅ Run `supabase_schema.sql` in your Supabase project
2. ✅ Test scraping: `python test_lovable.py`
3. ✅ Start API server: `python api_server.py`
4. Build Lovable pages that call the API
5. Deploy API server to cloud for production
