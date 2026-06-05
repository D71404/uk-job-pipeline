# Railway Deployment Guide

Deploy your automated job pipeline on Railway for 24/7 operation.

## 🚂 What Railway Will Do

Railway will:
- ✅ Detect Python project via `requirements.txt`
- ✅ Build Docker container using `Dockerfile`
- ✅ Run pipeline as background worker via `Procfile`
- ✅ Auto-restart on failures
- ✅ Provide free tier for testing ($5/month credit)

## 📋 Prerequisites

1. **Railway Account**: Sign up at https://railway.app
2. **Environment Variables**: Have your API keys ready
3. **Master CVs**: Uploaded to Supabase database

## 🚀 Step-by-Step Deployment

### Step 1: Create New Project on Railway

1. Go to https://railway.app/dashboard
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose `D71404/uk-job-pipeline`
5. Railway will auto-detect the configuration

### Step 2: Add Environment Variables

In Railway dashboard, go to **Variables** tab and add:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key-here
FIRECRAWL_API_KEY=fc-your-api-key-here
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

**Important:** Use your Supabase **service role key** (not anon key) for Railway.

### Step 3: Configure Deployment

Railway should automatically detect:
- **Builder**: Dockerfile
- **Start Command**: `python3 job_pipeline.py`
- **Restart Policy**: On failure

If not auto-detected, set manually in **Settings**.

### Step 4: Deploy

1. Click **"Deploy"** button
2. Watch build logs for any errors
3. Pipeline will start running automatically

### Step 5: Schedule Daily Runs

Since Railway workers run continuously, we need to modify the pipeline for scheduled execution.

**Option A: Use Railway Cron Jobs** (Recommended)

Railway has built-in cron job support:

1. Go to **Settings** → **Cron**
2. Add schedule: `0 9 * * *` (9 AM daily)
3. Command: `python3 job_pipeline.py`

**Option B: Internal Scheduler** (Alternative)

Create a scheduler wrapper:

```python
# scheduler.py
import schedule
import time
from job_pipeline import JobPipeline

def run_pipeline():
    pipeline = JobPipeline()
    pipeline.run_full_pipeline()

# Run daily at 9 AM UTC
schedule.every().day.at("09:00").do(run_pipeline)

print("Scheduler started. Waiting for scheduled runs...")
while True:
    schedule.run_pending()
    time.sleep(60)
```

Then update `Procfile`:
```
worker: python3 scheduler.py
```

## 📊 Monitoring

### View Logs

In Railway dashboard:
1. Click your project
2. Go to **Deployments** tab
3. Click latest deployment
4. View real-time logs

### Check Pipeline Status

Query your Supabase database:

```sql
SELECT status, COUNT(*)
FROM jobs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY status;
```

## 💰 Cost Estimation

Railway Pricing (as of 2024):
- **Free Tier**: $5 credit/month
- **Hobby Plan**: $5/month for small projects
- **Estimated Usage**: ~$2-3/month for daily pipeline

**External API Costs:**
- Firecrawl: ~$1-2/day for extensive scraping
- Anthropic: ~$2-5/day for CV tailoring
- **Total**: ~$90-210/month for full operation

## ⚙️ Configuration Files

### Procfile
```
worker: python3 job_pipeline.py
```
Tells Railway to run as background worker (not web server).

### Dockerfile
Multi-stage build with:
- Python 3.11 slim base
- System dependencies (gcc, git)
- Python packages from requirements.txt
- Application code

### railway.json
Railway-specific config:
- Build strategy (Dockerfile)
- Start command
- Restart policy (on failure, max 10 retries)

### .dockerignore
Excludes from Docker build:
- `.env` files
- Logs and cache
- Local data files

## 🔧 Troubleshooting

### Build Fails: "requirements.txt not found"

Check that `requirements.txt` is at repository root:
```bash
git ls-tree -r main --name-only | grep requirements.txt
```

### Runtime Error: "Missing environment variable"

Verify all variables are set in Railway dashboard:
- Go to **Variables** tab
- Check each key is present
- Click **Redeploy** after adding variables

### Pipeline Runs Once and Stops

Expected behavior! The pipeline runs once per deployment. For continuous scheduling:
1. Use Railway Cron Jobs, OR
2. Implement internal scheduler (see Option B above), OR
3. Manually trigger redeployments daily

### "No master CVs found" Error

Master CVs must be in Supabase database:
```bash
python3 upload_master_cv.py --list  # Check locally
python3 upload_master_cv.py AI_ENGINEER cv.md  # Upload
```

### Out of Memory (OOM) Error

Railway default memory might be too low for extensive scraping:
1. Go to **Settings** → **Resources**
2. Increase memory limit (requires paid plan)
3. Or reduce `--limit` parameter in pipeline

## 🎯 Production Recommendations

### 1. Use Separate Environment

Create `.env.production` for Railway:
```bash
# Production settings
MAX_JOBS_PER_RUN=20  # Reduce for Railway
LOG_LEVEL=INFO
ENABLE_EMAIL_NOTIFICATIONS=true
```

### 2. Add Health Checks

Modify `job_pipeline.py` to send heartbeat:
```python
def send_heartbeat():
    # Send to Railway health check endpoint
    # Or use external service like healthchecks.io
    pass
```

### 3. Implement Alerting

Add failure notifications:
- Email on pipeline errors
- Slack webhook for daily summaries
- Sentry for error tracking

### 4. Database Backups

Setup automatic Supabase backups:
1. Go to Supabase **Settings** → **Database**
2. Enable **Point-in-Time Recovery**
3. Configure backup retention

## 🔄 Updating the Pipeline

After making local changes:

```bash
cd "/Users/dan/Desktop/AI Automations"
git add .
git commit -m "Update pipeline logic"
git push origin main
```

Railway will automatically:
1. Detect the push
2. Rebuild Docker image
3. Deploy new version
4. Restart worker process

## 🎉 Success Indicators

Your deployment is working if you see:

✅ Build succeeds without errors
✅ Worker process starts
✅ Logs show "STARTING AUTOMATED JOB PIPELINE"
✅ New jobs appear in Supabase `jobs` table
✅ Status updates from `NEW` to `CV_TWEAKED`
✅ Lovable dashboard shows new jobs

## 📚 Additional Resources

- **Railway Docs**: https://docs.railway.app
- **Railway Cron**: https://docs.railway.app/guides/cron-jobs
- **Docker Best Practices**: https://docs.docker.com/develop/dev-best-practices
- **Supabase Connection**: https://supabase.com/docs/guides/database/connecting-to-postgres

## 🆘 Getting Help

If deployment fails:
1. Check Railway build logs
2. Verify environment variables
3. Test locally first: `./quick_start.sh`
4. Check GitHub repo: https://github.com/D71404/uk-job-pipeline

---

**Ready to deploy?** Head to https://railway.app and follow the steps above! 🚂
