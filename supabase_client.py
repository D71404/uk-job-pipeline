"""
Supabase integration for job scraper

Setup:
    1. Create table in Supabase (see SQL below)
    2. Add to .env:
       SUPABASE_URL=https://your-project.supabase.co
       SUPABASE_KEY=your-anon-or-service-key
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from supabase import create_client, Client
except ImportError:
    raise ImportError("Install supabase: pip install supabase-py")


# SQL to create jobs table in Supabase:
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS job_listings (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT,
    department TEXT,
    location TEXT,
    job_type TEXT,
    description TEXT,
    requirements TEXT,
    responsibilities TEXT,
    salary_range TEXT,
    apply_url TEXT,
    posted_date TEXT,
    source_url TEXT,
    extracted_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Optional: Add index for faster queries
CREATE INDEX IF NOT EXISTS idx_jobs_company ON job_listings(company);
CREATE INDEX IF NOT EXISTS idx_jobs_location ON job_listings(location);
CREATE INDEX IF NOT EXISTS idx_jobs_extracted ON job_listings(extracted_at);
"""


class SupabaseJobStore:
    """Store and retrieve job listings from Supabase."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = url or os.getenv('SUPABASE_URL')
        self.key = key or os.getenv('SUPABASE_KEY')

        if not self.url or not self.key:
            raise ValueError(
                "Supabase credentials required. Set SUPABASE_URL and SUPABASE_KEY in .env"
            )

        self.client: Client = create_client(self.url, self.key)
        self.table = 'job_listings'

    def insert_job(self, job: Dict[str, Any]) -> bool:
        """Insert a single job listing."""
        try:
            # Clean up data
            clean_job = {
                'title': job.get('title', '')[:500],
                'company': job.get('company', '')[:200],
                'department': job.get('department', '')[:200],
                'location': job.get('location', '')[:200],
                'job_type': job.get('job_type', job.get('type', ''))[:100],
                'description': job.get('description', '')[:10000],
                'requirements': job.get('requirements', '')[:5000],
                'responsibilities': job.get('responsibilities', '')[:5000],
                'salary_range': job.get('salary_range', '')[:200],
                'apply_url': job.get('apply_url', '')[:1000],
                'posted_date': job.get('posted_date', '')[:100],
                'source_url': job.get('source_url', '')[:1000],
                'extracted_at': datetime.now().isoformat(),
            }

            result = self.client.table(self.table).insert(clean_job).execute()
            return True

        except Exception as e:
            print(f"❌ Failed to insert job: {e}")
            return False

    def insert_jobs(self, jobs: List[Dict[str, Any]], batch_size: int = 50) -> int:
        """
        Insert multiple jobs in batches.

        Returns:
            Number of successfully inserted jobs
        """
        if not jobs:
            print("⚠️ No jobs to insert")
            return 0

        inserted = 0
        total = len(jobs)

        print(f"\n💾 Saving {total} jobs to Supabase...")

        for i in range(0, total, batch_size):
            batch = jobs[i:i + batch_size]

            # Clean batch data
            clean_batch = []
            for job in batch:
                clean_job = {
                    'title': str(job.get('title', ''))[:500],
                    'company': str(job.get('company', ''))[:200],
                    'department': str(job.get('department', ''))[:200],
                    'location': str(job.get('location', ''))[:200],
                    'job_type': str(job.get('job_type', job.get('type', '')))[:100],
                    'description': str(job.get('description', ''))[:10000],
                    'requirements': str(job.get('requirements', ''))[:5000],
                    'responsibilities': str(job.get('responsibilities', ''))[:5000],
                    'salary_range': str(job.get('salary_range', ''))[:200],
                    'apply_url': str(job.get('apply_url', ''))[:1000],
                    'posted_date': str(job.get('posted_date', ''))[:100],
                    'source_url': str(job.get('source_url', ''))[:1000],
                    'extracted_at': datetime.now().isoformat(),
                }
                clean_batch.append(clean_job)

            try:
                result = self.client.table(self.table).insert(clean_batch).execute()
                inserted += len(batch)
                print(f"   ✅ Batch {i//batch_size + 1}/{(total-1)//batch_size + 1}: {len(batch)} jobs")

            except Exception as e:
                print(f"   ❌ Batch failed: {e}")
                # Try inserting one by one to skip bad records
                for job in clean_batch:
                    if self.insert_job(job):
                        inserted += 1

        print(f"✅ Total inserted: {inserted}/{total}")
        return inserted

    def get_all_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve all jobs from database."""
        result = self.client.table(self.table).select('*').limit(limit).execute()
        return result.data if result else []

    def get_jobs_by_company(self, company: str) -> List[Dict[str, Any]]:
        """Get jobs for specific company."""
        result = (self.client.table(self.table)
                  .select('*')
                  .ilike('company', f'%{company}%')
                  .execute())
        return result.data if result else []

    def get_jobs_by_location(self, location: str) -> List[Dict[str, Any]]:
        """Get jobs by location."""
        result = (self.client.table(self.table)
                  .select('*')
                  .ilike('location', f'%{location}%')
                  .execute())
        return result.data if result else []

    def delete_old_jobs(self, days: int = 30) -> int:
        """Delete jobs older than specified days."""
        cutoff = (datetime.now() - __import__('datetime').timedelta(days=days)).isoformat()
        result = (self.client.table(self.table)
                  .delete()
                  .lt('extracted_at', cutoff)
                  .execute())
        return len(result.data) if result else 0

    def get_stats(self) -> Dict[str, Any]:
        """Get database stats."""
        total = len(self.client.table(self.table).select('id', count='exact').execute().data or [])

        # Get unique companies count
        companies_result = self.client.rpc('get_unique_companies_count').execute()

        return {
            'total_jobs': total,
            'unique_companies': companies_result.data if companies_result else 0
        }


# SQL for getting unique companies count (run in Supabase SQL editor):
UNIQUE_COMPANIES_SQL = """
CREATE OR REPLACE FUNCTION get_unique_companies_count()
RETURNS INTEGER AS $$
DECLARE
    count INTEGER;
BEGIN
    SELECT COUNT(DISTINCT company) INTO count FROM job_listings;
    RETURN count;
END;
$$ LANGUAGE plpgsql;
"""
