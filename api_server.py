"""
API Server for Lovable Job Scraper Integration

Run: python api_server.py
Or:  uvicorn api_server:app --reload --port 8000

Endpoints:
    POST /scrape          - Start scraping a URL
    GET  /reviews         - List pending reviews
    POST /approve         - Approve a job to bd_job_intel
    POST /reject          - Reject a job
    GET  /stats           - Get queue stats
"""

import os
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load env
from dotenv import load_dotenv
load_dotenv()

# Import scraper and supabase client
from job_scraper import JobScraper
from supabase_lovable_client import LovableJobStore

app = FastAPI(title="Lovable Job Scraper API")

# Enable CORS for Lovable
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your Lovable domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class ScrapeRequest(BaseModel):
    url: str
    company_name: Optional[str] = ""
    limit: int = 50

class ScrapeResponse(BaseModel):
    success: bool
    message: str
    jobs_found: int
    review_ids: List[str]

class ReviewResponse(BaseModel):
    id: str
    job_title: str
    company_name: Optional[str]
    location: Optional[str]
    remote_type: Optional[str]
    job_category: Optional[str]
    seniority_level: Optional[str]
    created_at: str

class ApproveRequest(BaseModel):
    review_id: str
    reviewer_user_id: str

class ApproveResponse(BaseModel):
    success: bool
    job_id: Optional[str]
    message: str

class RejectRequest(BaseModel):
    review_id: str
    reviewer_user_id: str
    notes: Optional[str] = ""

class RejectResponse(BaseModel):
    success: bool
    message: str


async def scrape_and_save(request: ScrapeRequest):
    """Background task to scrape and save to review queue."""
    try:
        # Scrape jobs
        scraper = JobScraper()
        pages = scraper.crawl_website(request.url, limit=request.limit)

        if not pages:
            return 0, []

        career_urls = scraper.filter_career_urls(pages)
        if not career_urls:
            return 0, []

        jobs_data = scraper.extract_jobs(career_urls)
        jobs = jobs_data.get('jobs', [])

        # Save to review queue
        if jobs:
            store = LovableJobStore()
            review_ids = store.insert_to_review(
                jobs,
                company_name=request.company_name,
                source_url=request.url
            )
            return len(jobs), review_ids

        return 0, []

    except Exception as e:
        print(f"Scraping failed: {e}")
        return 0, []


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_jobs(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Scrape jobs from a URL and save to review queue.

    Example:
        POST /scrape
        {
            "url": "https://www.turing.com",
            "company_name": "Turing",
            "limit": 50
        }
    """
    try:
        # Run scraping synchronously (can change to background for long jobs)
        jobs_count, review_ids = await scrape_and_save(request)

        if jobs_count == 0:
            return ScrapeResponse(
                success=False,
                message="No jobs found. Try increasing limit or checking URL.",
                jobs_found=0,
                review_ids=[]
            )

        return ScrapeResponse(
            success=True,
            message=f"Found {jobs_count} jobs. Saved to review queue.",
            jobs_found=jobs_count,
            review_ids=review_ids
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reviews", response_model=List[ReviewResponse])
async def get_reviews(limit: int = 50):
    """
    Get pending jobs waiting for review.

    Example:
        GET /reviews?limit=20
    """
    try:
        store = LovableJobStore()
        reviews = store.get_pending_reviews(limit=limit)

        return [
            ReviewResponse(
                id=r['id'],
                job_title=r.get('job_title', ''),
                company_name=r.get('company_name'),
                location=r.get('location'),
                remote_type=r.get('remote_type'),
                job_category=r.get('job_category'),
                seniority_level=r.get('seniority_level'),
                created_at=r.get('created_at', '')
            )
            for r in reviews
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/review/{review_id}")
async def get_review_detail(review_id: str):
    """Get full details of a specific review job."""
    try:
        from supabase import create_client

        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')
        client = create_client(url, key)

        result = client.table('bd_job_reviews').select('*').eq('id', review_id).single().execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Review not found")

        return result.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/approve", response_model=ApproveResponse)
async def approve_job(request: ApproveRequest):
    """
    Approve a job and move it to bd_job_intel.

    Example:
        POST /approve
        {
            "review_id": "uuid-here",
            "reviewer_user_id": "user-uuid-here"
        }
    """
    try:
        store = LovableJobStore()
        job_id = store.approve_job(request.review_id, request.reviewer_user_id)

        if job_id:
            return ApproveResponse(
                success=True,
                job_id=job_id,
                message="Job approved and published"
            )
        else:
            return ApproveResponse(
                success=False,
                job_id=None,
                message="Failed to approve job"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reject", response_model=RejectResponse)
async def reject_job(request: RejectRequest):
    """
    Reject a job review.

    Example:
        POST /reject
        {
            "review_id": "uuid-here",
            "reviewer_user_id": "user-uuid-here",
            "notes": "Duplicate listing"
        }
    """
    try:
        store = LovableJobStore()
        success = store.reject_job(
            request.review_id,
            request.reviewer_user_id,
            request.notes
        )

        return RejectResponse(
            success=success,
            message="Job rejected" if success else "Failed to reject job"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get review queue statistics."""
    try:
        store = LovableJobStore()
        stats = store.get_stats()
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Lovable Job Scraper API")
    print("📍 http://localhost:8000")
    print("\nEndpoints:")
    print("  POST /scrape  - Scrape jobs from URL")
    print("  GET  /reviews - List pending reviews")
    print("  POST /approve - Approve job to bd_job_intel")
    print("  POST /reject  - Reject job")
    print("  GET  /stats   - Queue statistics")
    uvicorn.run(app, host="0.0.0.0", port=8000)
