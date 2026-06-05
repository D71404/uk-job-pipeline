"""
Supabase Client for Job Pipeline
Handles all database operations for the automated job application pipeline
"""

import os
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

try:
    from supabase import create_client, Client
except ImportError:
    raise ImportError("Install supabase: pip install supabase")

load_dotenv()


class JobPipelineClient:
    """Client for managing job pipeline database operations."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """Initialize Supabase client."""
        self.url = url or os.getenv('SUPABASE_URL')
        self.key = key or os.getenv('SUPABASE_KEY')

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY required in .env")

        self.client: Client = create_client(self.url, self.key)

    # ============================================
    # Sponsored Companies Operations
    # ============================================

    def is_company_sponsored(self, company_name: str) -> bool:
        """
        Check if a company offers visa sponsorship.

        Args:
            company_name: Company name to check (case-insensitive)

        Returns:
            True if company is in sponsored_companies table
        """
        try:
            # Case-insensitive search
            result = (self.client.table('sponsored_companies')
                     .select('id')
                     .ilike('company_name', company_name)
                     .execute())

            return len(result.data) > 0
        except Exception as e:
            print(f"Error checking sponsored company: {e}")
            return False

    def add_sponsored_company(self, company_name: str, industry: str = "") -> bool:
        """Add a new sponsored company to the database."""
        try:
            self.client.table('sponsored_companies').insert({
                'company_name': company_name,
                'industry': industry
            }).execute()
            return True
        except Exception as e:
            print(f"Error adding sponsored company: {e}")
            return False

    def get_all_sponsored_companies(self) -> List[str]:
        """Get list of all sponsored company names."""
        try:
            result = self.client.table('sponsored_companies').select('company_name').execute()
            return [row['company_name'] for row in result.data]
        except Exception as e:
            print(f"Error fetching sponsored companies: {e}")
            return []

    # ============================================
    # Jobs Operations
    # ============================================

    def insert_job(self, job_data: Dict[str, Any]) -> Optional[int]:
        """
        Insert a new job into the database.
        Handles duplicate URLs gracefully by catching unique constraint violation.

        Args:
            job_data: Dict with keys: company_name, job_title, job_url, description, field

        Returns:
            Job ID if inserted, None if duplicate or error
        """
        try:
            result = self.client.table('jobs').insert({
                'company_name': job_data['company_name'],
                'job_title': job_data['job_title'],
                'job_url': job_data['job_url'],
                'description': job_data['description'],
                'field': job_data['field'],
                'status': 'NEW'
            }).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]['id']
            return None

        except Exception as e:
            error_msg = str(e).lower()
            # Check if it's a duplicate key error
            if 'duplicate' in error_msg or 'unique' in error_msg:
                print(f"   ⏭️  Duplicate job URL skipped: {job_data.get('job_url', 'unknown')}")
                return None
            else:
                print(f"   ❌ Error inserting job: {e}")
                return None

    def insert_jobs_batch(self, jobs: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Insert multiple jobs, handling duplicates gracefully.

        Args:
            jobs: List of job data dictionaries

        Returns:
            Tuple of (successful_inserts, skipped_duplicates)
        """
        inserted = 0
        skipped = 0

        for job in jobs:
            result = self.insert_job(job)
            if result:
                inserted += 1
            else:
                skipped += 1

        return inserted, skipped

    def get_jobs_by_status(self, status: str = 'NEW') -> List[Dict[str, Any]]:
        """Get all jobs with a specific status."""
        try:
            result = (self.client.table('jobs')
                     .select('*')
                     .eq('status', status)
                     .order('created_at', desc=True)
                     .execute())
            return result.data
        except Exception as e:
            print(f"Error fetching jobs: {e}")
            return []

    def get_job_by_id(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific job by ID."""
        try:
            result = (self.client.table('jobs')
                     .select('*')
                     .eq('id', job_id)
                     .execute())
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error fetching job: {e}")
            return None

    def update_job_status(self, job_id: int, new_status: str) -> bool:
        """Update job status (NEW -> CV_TWEAKED -> APPLIED -> REJECTED)."""
        try:
            self.client.table('jobs').update({
                'status': new_status
            }).eq('id', job_id).execute()
            return True
        except Exception as e:
            print(f"Error updating job status: {e}")
            return False

    # ============================================
    # Master CVs Operations
    # ============================================

    def get_master_cv(self, field: str) -> Optional[str]:
        """
        Get the master CV for a specific job field.

        Args:
            field: One of 'AI_ENGINEER', 'TEACHING', 'PHD', 'MARKETING'

        Returns:
            CV content in markdown format, or None if not found
        """
        try:
            result = (self.client.table('master_cvs')
                     .select('cv_content_markdown')
                     .eq('field', field)
                     .execute())

            if result.data and len(result.data) > 0:
                return result.data[0]['cv_content_markdown']
            return None
        except Exception as e:
            print(f"Error fetching master CV: {e}")
            return None

    def upsert_master_cv(self, field: str, cv_markdown: str) -> bool:
        """Insert or update a master CV for a field."""
        try:
            self.client.table('master_cvs').upsert({
                'field': field,
                'cv_content_markdown': cv_markdown
            }).execute()
            return True
        except Exception as e:
            print(f"Error upserting master CV: {e}")
            return False

    # ============================================
    # Tweaked CVs Operations
    # ============================================

    def insert_tweaked_cv(self, job_id: int, tailored_cv_markdown: str) -> Optional[int]:
        """
        Insert a tailored CV for a specific job.

        Args:
            job_id: Job ID to link the CV to
            tailored_cv_markdown: AI-optimized CV content

        Returns:
            Tweaked CV ID if successful, None otherwise
        """
        try:
            result = self.client.table('tweaked_cvs').insert({
                'job_id': job_id,
                'tailored_cv_markdown': tailored_cv_markdown
            }).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]['id']
            return None
        except Exception as e:
            print(f"Error inserting tweaked CV: {e}")
            return None

    def get_tweaked_cv(self, job_id: int) -> Optional[str]:
        """Get the tailored CV for a specific job."""
        try:
            result = (self.client.table('tweaked_cvs')
                     .select('tailored_cv_markdown')
                     .eq('job_id', job_id)
                     .execute())

            if result.data and len(result.data) > 0:
                return result.data[0]['tailored_cv_markdown']
            return None
        except Exception as e:
            print(f"Error fetching tweaked CV: {e}")
            return None

    # ============================================
    # Sponsorship Detection
    # ============================================

    def check_sponsorship(self, company_name: str, job_description: str) -> Tuple[bool, str]:
        """
        Check if a job offers visa sponsorship.
        Uses both DB lookup and description keyword matching.

        Args:
            company_name: Company name
            job_description: Full job description text

        Returns:
            Tuple of (is_sponsored, reason)
        """
        # First check database
        if self.is_company_sponsored(company_name):
            return True, "Company in sponsored_companies database"

        # Check description for sponsorship keywords
        description_lower = job_description.lower()

        sponsorship_keywords = [
            r'visa sponsor(ship)?',
            r'tier 2 sponsor',
            r'skilled worker visa',
            r'sponsorship available',
            r'we sponsor',
            r'sponsorship provided',
            r'right to work.*provid',
            r'work permit.*sponsor',
            r'immigration support',
            r'relocation.*visa'
        ]

        for keyword_pattern in sponsorship_keywords:
            if re.search(keyword_pattern, description_lower):
                return True, f"Description mentions: {keyword_pattern}"

        return False, "No sponsorship indication found"

    # ============================================
    # Dashboard & Stats
    # ============================================

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get overall pipeline statistics."""
        try:
            # Get job counts by status
            jobs_result = self.client.table('jobs').select('status', count='exact').execute()

            # Get counts by field
            by_field = {}
            for field in ['AI_ENGINEER', 'TEACHING', 'PHD', 'MARKETING']:
                result = (self.client.table('jobs')
                         .select('*', count='exact')
                         .eq('field', field)
                         .execute())
                by_field[field] = result.count if hasattr(result, 'count') else 0

            # Get status breakdown
            status_counts = {}
            for status in ['NEW', 'CV_TWEAKED', 'APPLIED', 'REJECTED']:
                result = (self.client.table('jobs')
                         .select('*', count='exact')
                         .eq('status', status)
                         .execute())
                status_counts[status] = result.count if hasattr(result, 'count') else 0

            return {
                'total_jobs': jobs_result.count if hasattr(jobs_result, 'count') else 0,
                'by_field': by_field,
                'by_status': status_counts,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}

    def get_jobs_needing_cv(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get jobs that need CV tailoring (status = NEW)."""
        return self.get_jobs_by_status('NEW')[:limit]
