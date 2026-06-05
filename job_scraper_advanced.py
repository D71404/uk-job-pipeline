#!/usr/bin/env python3
"""
Firecrawl Job Scraper - Advanced Version

Features:
- Batch processing multiple companies
- Smart URL discovery with path filtering
- Structured extraction with fallback parsing
- Progress tracking and resume capability
- Detailed logging

Usage:
    python job_scraper_advanced.py --companies companies.txt
    python job_scraper_advanced.py --url https://example.com --deep
"""

import os
import re
import json
import argparse
import logging
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, urljoin
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

from dotenv import load_dotenv
from firecrawl import Firecrawl
import pandas as pd

# Load environment variables from .env file
load_dotenv()


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class JobListing:
    """Structured job listing data."""
    title: str
    company: str = ""
    department: str = ""
    location: str = ""
    job_type: str = ""
    description: str = ""
    requirements: str = ""
    responsibilities: str = ""
    salary_range: str = ""
    apply_url: str = ""
    posted_date: str = ""
    source_url: str = ""
    extracted_at: str = ""


class AdvancedJobScraper:
    """Advanced job scraper with batch processing and smart filtering."""

    # Career page patterns (in order of priority)
    CAREER_PATTERNS = [
        (r'/careers(/|$)', 10),
        (r'/jobs(/|$)', 10),
        (r'/about/careers', 9),
        (r'/company/careers', 9),
        (r'/openings(/|$)', 8),
        (r'/positions(/|$)', 8),
        (r'/opportunities(/|$)', 7),
        (r'/hiring(/|$)', 7),
        (r'/work-with-us', 6),
        (r'/join-us', 6),
        (r'/join(-|_)?our(-|_)?team', 6),
        (r'/life-at', 5),
        (r'/team(/|$)', 4),
        (r'/employment(/|$)', 4),
        (r'/vacancies?(/|$)', 4),
        (r'/recruitment(/|$)', 3),
    ]

    # Exclude patterns (common false positives)
    EXCLUDE_PATTERNS = [
        r'/blog/',
        r'/news/',
        r'/press/',
        r'/media/',
        r'/event/',
        r'/case-stud(y|ies)',
        r'/success-story',
        r'/customer/',
        r'/partner/',
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('FIRECRAWL_API_KEY')
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY required")
        self.firecrawl = Firecrawl(api_key=self.api_key)
        self.results: List[JobListing] = []

    def score_career_url(self, url: str) -> int:
        """Score URL based on how likely it is to be a careers page."""
        url_lower = url.lower()
        score = 0

        for pattern, weight in self.CAREER_PATTERNS:
            if re.search(pattern, url_lower, re.IGNORECASE):
                score = max(score, weight)

        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, url_lower, re.IGNORECASE):
                score -= 5

        return score

    def is_likely_career_url(self, url: str, min_score: int = 5) -> bool:
        """Check if URL is likely a career page."""
        return self.score_career_url(url) >= min_score

    def crawl_with_focus(self, url: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Crawl with path filtering for faster career page discovery.

        Strategy:
        1. First try with includePaths for common career paths
        2. If no results, do broader crawl
        """
        domain = urlparse(url).netloc
        logger.info(f"Crawling {domain} with career focus...")

        # Try focused crawl first
        career_paths = [
            'career', 'careers', 'job', 'jobs', 'opening', 'openings',
            'position', 'positions', 'hire', 'hiring', 'join', 'team'
        ]

        try:
            result = self.firecrawl.crawl(
                url,
                limit=limit,
                includePaths=career_paths,
                scrape_options={
                    'formats': ['markdown'],
                    'only_main_content': True
                }
            )

            if result and hasattr(result, 'data') and result.data:
                logger.info(f"Focused crawl found {len(result.data)} pages")
                return result.data

        except Exception as e:
            logger.warning(f"Focused crawl failed: {e}")

        # Fallback to broader crawl
        logger.info("Trying broader crawl...")
        try:
            result = self.firecrawl.crawl(
                url,
                limit=limit,
                scrape_options={
                    'formats': ['markdown'],
                    'only_main_content': True
                }
            )
            return result.data if result and hasattr(result, 'data') else []

        except Exception as e:
            logger.error(f"Broad crawl failed: {e}")
            return []

    def discover_career_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank and filter career pages from crawl results."""
        scored_pages = []

        for page in pages:
            metadata = page.get('metadata', {})
            url = metadata.get('sourceURL') or metadata.get('url', '')
            score = self.score_career_url(url)

            if score >= 5:
                scored_pages.append({
                    'url': url,
                    'score': score,
                    'title': metadata.get('title', ''),
                    'page': page
                })

        # Sort by score descending
        scored_pages.sort(key=lambda x: x['score'], reverse=True)

        logger.info(f"Found {len(scored_pages)} career-related pages")
        for p in scored_pages[:5]:
            logger.info(f"  [{p['score']}] {p['url']}")

        return scored_pages

    def extract_with_schema(self, urls: List[str]) -> Dict[str, Any]:
        """Extract jobs using structured schema."""

        schema = {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "department": {"type": "string"},
                            "location": {"type": "string"},
                            "type": {"type": "string"},
                            "description": {"type": "string"},
                            "requirements": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "responsibilities": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "salary_range": {"type": "string"},
                            "apply_url": {"type": "string"},
                            "posted_date": {"type": "string"}
                        },
                        "required": ["title"]
                    }
                }
            },
            "required": ["jobs"]
        }

        prompt = """
        Extract all job listings from these career pages.

        For each job posting, extract:
        - Title: The job title/role name
        - Department: Team or department (Engineering, Sales, Marketing, etc.)
        - Location: City, state, country, or "Remote"
        - Type: Full-time, Part-time, Contract, Internship, etc.
        - Description: Full job description text
        - Requirements: List of required qualifications, skills, experience
        - Responsibilities: List of job duties and responsibilities
        - Salary Range: Compensation range if mentioned
        - Apply URL: Direct link to apply (if different from source)
        - Posted Date: When job was posted

        Return empty array if no job listings found on the page.
        """

        try:
            result = self.firecrawl.extract(
                urls=urls,
                prompt=prompt,
                schema=schema
            )

            if hasattr(result, 'data'):
                return result.data
            elif isinstance(result, dict):
                return result.get('data', result)
            return {"jobs": []}

        except Exception as e:
            logger.error(f"Schema extraction failed: {e}")
            return {"jobs": []}

    def scrape_company(self, url: str, company_name: str = "", deep: bool = False) -> List[JobListing]:
        """
        Scrape jobs from a single company.

        Args:
            url: Company website URL
            company_name: Name of company
            deep: If True, do deeper crawl (more pages)

        Returns:
            List of JobListing objects
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Scraping: {company_name or url}")
        logger.info('='*60)

        limit = 200 if deep else 50
        jobs_found: List[JobListing] = []

        # Step 1: Crawl
        pages = self.crawl_with_focus(url, limit=limit)
        if not pages:
            logger.warning("No pages crawled")
            return jobs_found

        # Step 2: Discover career pages
        career_pages = self.discover_career_pages(pages)
        if not career_pages:
            logger.warning("No career pages found")
            return jobs_found

        # Step 3: Extract jobs
        career_urls = [p['url'] for p in career_pages[:10]]  # Top 10 pages
        logger.info(f"Extracting from {len(career_urls)} pages...")

        data = self.extract_with_schema(career_urls)
        jobs = data.get('jobs', [])

        # Step 4: Create JobListing objects
        for job in jobs:
            listing = JobListing(
                title=job.get('title', ''),
                company=company_name,
                department=job.get('department', ''),
                location=job.get('location', ''),
                job_type=job.get('type', ''),
                description=job.get('description', ''),
                requirements='\n'.join(job.get('requirements', [])),
                responsibilities='\n'.join(job.get('responsibilities', [])),
                salary_range=job.get('salary_range', ''),
                apply_url=job.get('apply_url', ''),
                posted_date=job.get('posted_date', ''),
                source_url=career_urls[0] if career_urls else '',
                extracted_at=datetime.now().isoformat()
            )
            jobs_found.append(listing)

        logger.info(f"Found {len(jobs_found)} jobs")
        return jobs_found

    def scrape_multiple(
        self,
        companies: List[Dict[str, str]],
        output: str = "jobs_combined.xlsx",
        deep: bool = False
    ) -> str:
        """
        Scrape jobs from multiple companies.

        Args:
            companies: List of dicts with 'name' and 'url' keys
            output: Output Excel file path
            deep: Deep crawl mode

        Returns:
            Path to saved file
        """
        all_jobs: List[JobListing] = []

        for i, company in enumerate(companies, 1):
            logger.info(f"\n[{i}/{len(companies)}] Processing {company['name']}...")

            try:
                jobs = self.scrape_company(
                    url=company['url'],
                    company_name=company['name'],
                    deep=deep
                )
                all_jobs.extend(jobs)

                # Auto-save progress every 5 companies
                if i % 5 == 0:
                    self._save_checkpoint(all_jobs, f"checkpoint_{i}.xlsx")

            except Exception as e:
                logger.error(f"Failed to scrape {company['name']}: {e}")
                continue

        # Final save
        if all_jobs:
            return self._save_to_excel(all_jobs, output)
        else:
            logger.warning("No jobs found from any company")
            return ""

    def _save_checkpoint(self, jobs: List[JobListing], filename: str):
        """Save intermediate checkpoint."""
        checkpoint_dir = Path("checkpoints")
        checkpoint_dir.mkdir(exist_ok=True)
        path = checkpoint_dir / filename
        self._save_to_excel(jobs, str(path))
        logger.info(f"Checkpoint saved: {path}")

    def _save_to_excel(self, jobs: List[JobListing], path: str) -> str:
        """Save jobs to Excel."""
        if not jobs:
            return ""

        df = pd.DataFrame([asdict(j) for j in jobs])

        # Reorder columns for readability
        col_order = [
            'title', 'company', 'department', 'location', 'job_type',
            'salary_range', 'description', 'requirements', 'responsibilities',
            'apply_url', 'posted_date', 'source_url', 'extracted_at'
        ]
        df = df[[c for c in col_order if c in df.columns]]

        # Rename columns for display
        df.columns = [c.replace('_', ' ').title() for c in df.columns]

        df.to_excel(path, index=False, engine='openpyxl')
        logger.info(f"Saved {len(jobs)} jobs to {path}")
        return path


def load_companies_from_file(filepath: str) -> List[Dict[str, str]]:
    """Load company list from text file.

    Format per line: Company Name, https://example.com
    """
    companies = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split(',', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = parts[1].strip()
                companies.append({'name': name, 'url': url})

    return companies


def main():
    parser = argparse.ArgumentParser(
        description='Advanced job scraper with batch processing'
    )
    parser.add_argument(
        '--url',
        help='Single company URL to scrape'
    )
    parser.add_argument(
        '--name',
        help='Company name (for single URL mode)'
    )
    parser.add_argument(
        '--companies',
        help='Text file with company list (format: Name, URL)'
    )
    parser.add_argument(
        '-o', '--output',
        default='jobs.xlsx',
        help='Output file (default: jobs.xlsx)'
    )
    parser.add_argument(
        '--deep',
        action='store_true',
        help='Deep crawl mode (more pages, slower)'
    )
    parser.add_argument(
        '--api-key',
        help='Firecrawl API key'
    )

    args = parser.parse_args()

    # Initialize
    try:
        scraper = AdvancedJobScraper(api_key=args.api_key)
    except ValueError as e:
        logger.error(e)
        return

    # Run
    if args.url:
        # Single company mode
        jobs = scraper.scrape_company(
            url=args.url,
            company_name=args.name or "",
            deep=args.deep
        )
        if jobs:
            scraper._save_to_excel(jobs, args.output)
            print(f"\n✅ Saved {len(jobs)} jobs to {args.output}")

    elif args.companies:
        # Batch mode
        companies = load_companies_from_file(args.companies)
        logger.info(f"Loaded {len(companies)} companies from {args.companies}")

        result = scraper.scrape_multiple(companies, args.output, args.deep)
        if result:
            print(f"\n✅ Batch complete! Results: {result}")

    else:
        parser.print_help()
        print("\nExample usage:")
        print(f"  python {__file__} --url https://stripe.com --name Stripe")
        print(f"  python {__file__} --companies companies.txt --deep")


if __name__ == '__main__':
    main()
