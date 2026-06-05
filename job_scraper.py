#!/usr/bin/env python3
"""
Firecrawl Job Scraper Automation

Flow:
1. Crawl a website to discover all pages
2. Filter for careers/jobs URLs
3. Extract structured job details using LLM
4. Save to Excel

Setup:
    pip install firecrawl-py pandas openpyxl

Usage:
    python job_scraper.py https://example.com
"""

import os
import re
import json
import argparse
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime

from dotenv import load_dotenv
from firecrawl import Firecrawl
import pandas as pd

# Load environment variables from .env file
load_dotenv()


# Career-related URL patterns to match
CAREER_PATTERNS = [
    r'/careers?(/|$)',
    r'/jobs?(/|$)',
    r'/positions?(/|$)',
    r'/openings?(/|$)',
    r'/opportunities?(/|$)',
    r'/hiring(/|$)',
    r'/work-with-us(/|$)',
    r'/join-us(/|$)',
    r'/team(/|$)',
    r'/about.*jobs',
    r'/employment(/|$)',
    r'/vacancies?(/|$)',
    r'/recruitment(/|$)',
]

# Job schema for structured extraction
JOB_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Job title/position name"},
                    "department": {"type": "string", "description": "Department or team (e.g., Engineering, Sales, Marketing)"},
                    "location": {"type": "string", "description": "Job location (city, country, or remote)"},
                    "type": {"type": "string", "description": "Employment type (Full-time, Part-time, Contract, Internship)"},
                    "description": {"type": "string", "description": "Full job description"},
                    "requirements": {"type": "array", "items": {"type": "string"}, "description": "Required qualifications/skills"},
                    "responsibilities": {"type": "array", "items": {"type": "string"}, "description": "Job responsibilities/duties"},
                    "salary_range": {"type": "string", "description": "Salary range if mentioned"},
                    "apply_url": {"type": "string", "description": "URL to apply for the job"},
                    "posted_date": {"type": "string", "description": "When the job was posted"}
                },
                "required": ["title"]
            }
        }
    },
    "required": ["jobs"]
}


class JobScraper:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Firecrawl client."""
        self.api_key = api_key or os.getenv('FIRECRAWL_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Firecrawl API key required. Set FIRECRAWL_API_KEY env var or pass api_key."
            )
        self.firecrawl = Firecrawl(api_key=self.api_key)

    def is_career_url(self, url: str) -> bool:
        """Check if URL matches career/job page patterns."""
        url_lower = url.lower()
        for pattern in CAREER_PATTERNS:
            if re.search(pattern, url_lower, re.IGNORECASE):
                return True
        return False

    def crawl_website(self, url: str, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        """
        Crawl website and return all discovered pages.

        Args:
            url: Starting URL
            limit: Max pages to crawl
            **kwargs: Additional crawl options

        Returns:
            List of page data with metadata
        """
        print(f"🔍 Crawling {url} (limit: {limit} pages)...")

        # Configure crawl options
        crawl_options = {
            'limit': limit,
            'scrape_options': {
                'formats': ['markdown'],
                'only_main_content': True
            }
        }
        crawl_options.update(kwargs)

        # Execute crawl (waits for completion)
        result = self.firecrawl.crawl(url, **crawl_options)

        if not result or not hasattr(result, 'data'):
            print("❌ Crawl failed or returned no data")
            return []

        pages = result.data or []
        print(f"✅ Crawled {len(pages)} pages")
        return pages

    def filter_career_urls(self, pages) -> List[str]:
        """Extract career/job page URLs from crawl results."""
        career_urls = []

        for page in pages:
            # Handle both dict and Pydantic Document objects
            if hasattr(page, 'metadata'):
                metadata = page.metadata or {}
                source_url = getattr(metadata, 'sourceURL', None) or getattr(metadata, 'source_url', None) or getattr(metadata, 'url', None)
                # Handle dict metadata as well
                if isinstance(metadata, dict):
                    source_url = metadata.get('sourceURL') or metadata.get('source_url') or metadata.get('url', '')
            else:
                metadata = page.get('metadata', {}) if isinstance(page, dict) else {}
                source_url = metadata.get('sourceURL') or metadata.get('source_url') or metadata.get('url', '')

            if source_url and self.is_career_url(source_url):
                career_urls.append(source_url)

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in career_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        print(f"🎯 Found {len(unique_urls)} career-related URLs:")
        for url in unique_urls[:10]:  # Show first 10
            print(f"   - {url}")
        if len(unique_urls) > 10:
            print(f"   ... and {len(unique_urls) - 10} more")

        return unique_urls

    def extract_jobs(self, urls: List[str], prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract structured job data from career pages.
        Batches URLs in groups of 10 (Firecrawl beta limit).

        Args:
            urls: List of career page URLs
            prompt: Custom extraction prompt

        Returns:
            Extracted job data
        """
        if not urls:
            print("⚠️ No URLs to extract from")
            return {"jobs": []}

        default_prompt = """
        Extract all job listings from this page. For each job, capture:
        - Job title
        - Department/team
        - Location
        - Employment type (Full-time, Part-time, Contract, Internship)
        - Full job description
        - Required qualifications/skills
        - Job responsibilities
        - Salary range (if mentioned)
        - Application link/URL
        - Posted date (if available)

        Return as a structured list of jobs. If no jobs are found, return an empty list.
        """

        extraction_prompt = prompt or default_prompt

        print(f"\n🤖 Extracting job data from {len(urls)} pages...")
        print("⏳ This may take a few minutes...")

        all_jobs = []

        # Batch URLs in groups of 10 (Firecrawl beta limit)
        batch_size = 10
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            print(f"   Processing batch {i//batch_size + 1}/{(len(urls)-1)//batch_size + 1} ({len(batch)} URLs)...")

            try:
                result = self.firecrawl.extract(
                    urls=batch,
                    prompt=extraction_prompt,
                    schema=JOB_SCHEMA
                )

                batch_data = {}
                if hasattr(result, 'data'):
                    batch_data = result.data
                elif isinstance(result, dict):
                    batch_data = result.get('data', result)

                batch_jobs = batch_data.get('jobs', []) if isinstance(batch_data, dict) else []
                all_jobs.extend(batch_jobs)
                print(f"   ✅ Found {len(batch_jobs)} jobs in this batch")

            except Exception as e:
                print(f"   ❌ Batch failed: {e}")
                continue

        return {"jobs": all_jobs}

    def jobs_to_dataframe(self, jobs_data: Dict[str, Any]) -> pd.DataFrame:
        """Convert job data to pandas DataFrame."""
        jobs = jobs_data.get('jobs', [])

        if not jobs:
            print("⚠️ No jobs found in extraction results")
            return pd.DataFrame()

        # Flatten nested structures for Excel
        flattened = []
        for job in jobs:
            flat_job = {
                'Title': job.get('title', ''),
                'Department': job.get('department', ''),
                'Location': job.get('location', ''),
                'Type': job.get('type', ''),
                'Description': job.get('description', ''),
                'Requirements': '\n'.join(job.get('requirements', [])),
                'Responsibilities': '\n'.join(job.get('responsibilities', [])),
                'Salary Range': job.get('salary_range', ''),
                'Apply URL': job.get('apply_url', ''),
                'Posted Date': job.get('posted_date', ''),
            }
            flattened.append(flat_job)

        return pd.DataFrame(flattened)

    def save_to_excel(self, df: pd.DataFrame, output_path: Optional[str] = None) -> str:
        """Save DataFrame to Excel file."""
        if df.empty:
            print("⚠️ No data to save")
            return ""

        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"jobs_{timestamp}.xlsx"

        # Ensure .xlsx extension
        if not output_path.endswith('.xlsx'):
            output_path += '.xlsx'

        df.to_excel(output_path, index=False, engine='openpyxl')
        print(f"\n💾 Saved {len(df)} jobs to: {output_path}")
        return output_path

    def scrape_jobs(self, url: str, limit: int = 100, output: Optional[str] = None,
                    save_to_supabase: bool = False, company_name: str = "") -> str:
        """
        Complete job scraping workflow.

        Args:
            url: Website URL to scrape
            limit: Max pages to crawl
            output: Output Excel file path
            save_to_supabase: Also save to Supabase
            company_name: Company name for database

        Returns:
            Path to saved Excel file (or "" if only saving to Supabase)
        """
        print("=" * 60)
        print("🔥 Firecrawl Job Scraper")
        print("=" * 60)

        # Step 1: Crawl website
        pages = self.crawl_website(url, limit=limit)

        if not pages:
            print("❌ No pages found")
            return ""

        # Step 2: Filter career URLs
        career_urls = self.filter_career_urls(pages)

        if not career_urls:
            print("\n⚠️ No career URLs found. Trying extract on main domain...")
            # Fallback: try to extract from the main URL with wildcard
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}/*"
            career_urls = [base_url]

        # Step 3: Extract job data
        jobs_data = self.extract_jobs(career_urls)

        # Add company name to each job
        jobs = jobs_data.get('jobs', [])
        for job in jobs:
            job['company'] = company_name or job.get('company', '')
            job['source_url'] = url

        # Step 4: Save to Supabase if requested
        if save_to_supabase and jobs:
            try:
                from supabase_client import SupabaseJobStore
                store = SupabaseJobStore()
                inserted = store.insert_jobs(jobs)
                print(f"✅ Saved {inserted} jobs to Supabase")
            except Exception as e:
                print(f"⚠️ Supabase save failed: {e}")

        # Step 5: Convert to DataFrame and save to Excel
        df = self.jobs_to_dataframe({'jobs': jobs})

        if not df.empty:
            return self.save_to_excel(df, output)
        else:
            print("\n⚠️ No jobs found with current settings. Try:")
            print("   - Increasing --limit for deeper crawl")
            print("   - Checking if jobs are on a separate subdomain (e.g., careers.company.com)")
            return ""


def main():
    parser = argparse.ArgumentParser(
        description='Scrape job listings from company websites using Firecrawl'
    )
    parser.add_argument(
        'url',
        help='Company website URL (e.g., https://example.com)'
    )
    parser.add_argument(
        '-l', '--limit',
        type=int,
        default=100,
        help='Maximum pages to crawl (default: 100)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output Excel file path (default: jobs_TIMESTAMP.xlsx)'
    )
    parser.add_argument(
        '--api-key',
        help='Firecrawl API key (or set FIRECRAWL_API_KEY env var)'
    )
    parser.add_argument(
        '--supabase',
        action='store_true',
        help='Also save jobs to Supabase (set SUPABASE_URL and SUPABASE_KEY in .env)'
    )
    parser.add_argument(
        '--company',
        help='Company name (for database)'
    )

    args = parser.parse_args()

    # Initialize scraper
    try:
        scraper = JobScraper(api_key=args.api_key)
    except ValueError as e:
        print(f"❌ {e}")
        print("\nGet your API key at: https://firecrawl.dev/app")
        return

    # Run scraper
    output_file = scraper.scrape_jobs(
        url=args.url,
        limit=args.limit,
        output=args.output,
        save_to_supabase=args.supabase,
        company_name=args.company
    )

    if output_file:
        print(f"\n✅ Done! Check: {output_file}")
    else:
        print("\n❌ No jobs found. Try increasing --limit or checking the URL.")


if __name__ == '__main__':
    main()
