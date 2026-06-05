#!/usr/bin/env python3
"""
FastAPI Web Server for Job Pipeline
On-demand execution via REST API
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from job_pipeline import JobPipeline

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Key for authentication (optional but recommended)
API_KEY = os.getenv('API_KEY', 'your-secret-key-here')

# Global state
pipeline_status = {
    'is_running': False,
    'last_run': None,
    'last_result': None,
    'error': None
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Job Pipeline API starting up...")
    logger.info(f"   Environment: {os.getenv('RAILWAY_ENVIRONMENT', 'local')}")
    logger.info(f"   API ready at: /api/trigger-pipeline")
    yield
    logger.info("👋 Job Pipeline API shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="UK Job Pipeline API",
    description="On-demand job scraping, filtering, and CV tailoring API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for Lovable frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.lovable.app",
        "https://*.lovable.dev",
        "https://lovable.app",
        "https://lovable.dev",
        "*"  # Allow all origins (adjust for production)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class PipelineRequest(BaseModel):
    """Request model for triggering pipeline."""
    limit: Optional[int] = 50
    scrape_only: bool = False
    tailor_only: bool = False


class PipelineResponse(BaseModel):
    """Response model for pipeline trigger."""
    status: str
    message: str
    started_at: str
    job_id: Optional[str] = None


class StatusResponse(BaseModel):
    """Response model for status check."""
    is_running: bool
    last_run: Optional[str]
    last_result: Optional[Dict[str, Any]]
    error: Optional[str]


# Authentication dependency
def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key from header."""
    if not x_api_key:
        # Allow requests without API key for now (adjust for production)
        return True

    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# Background task function
def run_pipeline_background(scrape_only: bool = False, tailor_only: bool = False, limit: int = 50):
    """Run the pipeline in background."""
    global pipeline_status

    try:
        pipeline_status['is_running'] = True
        pipeline_status['error'] = None

        logger.info("=" * 70)
        logger.info("BACKGROUND PIPELINE EXECUTION STARTED")
        logger.info("=" * 70)

        pipeline = JobPipeline()

        if scrape_only:
            # Only scrape and insert jobs
            scraped = pipeline.scrape_jobs()
            sponsored = pipeline.filter_sponsored_jobs(scraped)
            inserted, skipped = pipeline.insert_jobs_to_db(sponsored)

            result = {
                'mode': 'scrape_only',
                'total_scraped': sum(len(jobs) for jobs in scraped.values()),
                'total_sponsored': sum(len(jobs) for jobs in sponsored.values()),
                'jobs_inserted': inserted,
                'jobs_skipped': skipped,
                'timestamp': datetime.now().isoformat()
            }

        elif tailor_only:
            # Only tailor CVs for existing NEW jobs
            cvs_tailored = pipeline.tailor_cvs_for_new_jobs(limit=limit)

            result = {
                'mode': 'tailor_only',
                'cvs_tailored': cvs_tailored,
                'timestamp': datetime.now().isoformat()
            }

        else:
            # Full pipeline
            result = pipeline.run_full_pipeline()

        pipeline_status['last_result'] = result
        pipeline_status['last_run'] = datetime.now().isoformat()

        logger.info("✅ Background pipeline execution completed successfully")

    except Exception as e:
        logger.error(f"❌ Background pipeline execution failed: {e}", exc_info=True)
        pipeline_status['error'] = str(e)
        pipeline_status['last_result'] = {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

    finally:
        pipeline_status['is_running'] = False


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint - API info."""
    return {
        "name": "UK Job Pipeline API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "trigger": "POST /api/trigger-pipeline",
            "status": "GET /api/status",
            "health": "GET /health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "pipeline_running": pipeline_status['is_running']
    }


@app.get("/api/status", response_model=StatusResponse)
async def get_status(authenticated: bool = Depends(verify_api_key)):
    """
    Get current pipeline status.

    Returns:
        Current execution status and last results
    """
    return StatusResponse(**pipeline_status)


@app.post("/api/trigger-pipeline", response_model=PipelineResponse)
async def trigger_pipeline(
    request: PipelineRequest,
    background_tasks: BackgroundTasks,
    authenticated: bool = Depends(verify_api_key)
):
    """
    Trigger the job pipeline execution.

    This endpoint starts the pipeline in the background and returns immediately.
    The pipeline will scrape jobs, filter for sponsorship, insert to database,
    and tailor CVs using Claude AI.

    Args:
        request: Pipeline configuration
        background_tasks: FastAPI background tasks
        authenticated: Authentication verification

    Returns:
        Immediate response with job ID

    Example:
        ```bash
        curl -X POST https://your-api.railway.app/api/trigger-pipeline \\
             -H "Content-Type: application/json" \\
             -H "X-API-Key: your-secret-key" \\
             -d '{"limit": 50, "scrape_only": false}'
        ```
    """
    # Check if pipeline is already running
    if pipeline_status['is_running']:
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running. Please wait for it to complete."
        )

    # Start pipeline in background
    job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    background_tasks.add_task(
        run_pipeline_background,
        scrape_only=request.scrape_only,
        tailor_only=request.tailor_only,
        limit=request.limit
    )

    logger.info(f"✅ Pipeline triggered: {job_id}")
    logger.info(f"   Mode: {'scrape_only' if request.scrape_only else 'tailor_only' if request.tailor_only else 'full_pipeline'}")
    logger.info(f"   Limit: {request.limit}")

    return PipelineResponse(
        status="started",
        message="Pipeline execution started in background",
        started_at=datetime.now().isoformat(),
        job_id=job_id
    )


@app.post("/api/trigger-scrape")
async def trigger_scrape_only(
    background_tasks: BackgroundTasks,
    authenticated: bool = Depends(verify_api_key)
):
    """
    Quick endpoint to trigger scraping only (no CV tailoring).

    Returns:
        Immediate response
    """
    if pipeline_status['is_running']:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    background_tasks.add_task(run_pipeline_background, scrape_only=True)

    return {
        "status": "started",
        "message": "Scraping pipeline started",
        "mode": "scrape_only",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/trigger-tailor")
async def trigger_tailor_only(
    background_tasks: BackgroundTasks,
    limit: int = 50,
    authenticated: bool = Depends(verify_api_key)
):
    """
    Quick endpoint to trigger CV tailoring only (no scraping).

    Args:
        limit: Maximum jobs to process

    Returns:
        Immediate response
    """
    if pipeline_status['is_running']:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    background_tasks.add_task(run_pipeline_background, tailor_only=True, limit=limit)

    return {
        "status": "started",
        "message": "CV tailoring pipeline started",
        "mode": "tailor_only",
        "limit": limit,
        "timestamp": datetime.now().isoformat()
    }


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Set to False in production
        log_level="info"
    )
