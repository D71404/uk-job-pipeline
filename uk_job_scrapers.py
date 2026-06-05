"""
UK Job Portal Scrapers
Scrapes job postings from major UK job boards using Firecrawl
"""

import os
import re
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

try:
    from firecrawl import Firecrawl
except ImportError:
    raise ImportError("Install firecrawl: pip install firecrawl-py")

load_dotenv()


class UKJobScrapers:
    """Scraper for multiple UK job portals."""

    # Job extraction schema for Firecrawl
    JOB_SCHEMA = {
        "type": "object",
        "properties": {
            "jobs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Job title"},
                        "company": {"type": "string", "description": "Company name"},
                        "location": {"type": "string", "description": "Job location"},
                        "description": {"type": "string", "description": "Full job description"},
                        "url": {"type": "string", "description": "Direct URL to job posting"},
                        "posted_date": {"type": "string", "description": "When posted (if available)"},
                        "salary": {"type": "string", "description": "Salary information (if available)"}
                    },
                    "required": ["title", "company", "description"]
                }
            }
        },
        "required": ["jobs"]
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Firecrawl client."""
        self.api_key = api_key or os.getenv('FIRECRAWL_API_KEY')
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY required in .env")

        self.firecrawl = Firecrawl(api_key=self.api_key)

    def _extract_jobs_from_urls(self, urls: List[str], field: str) -> List[Dict[str, Any]]:
        """
        Extract jobs from a list of URLs using Firecrawl's extract API.

        Args:
            urls: List of job search result URLs
            field: Job field (AI_ENGINEER, TEACHING, PHD, MARKETING)

        Returns:
            List of extracted job dictionaries
        """
        if not urls:
            return []

        prompt = f"""
        Extract all job listings from these pages. Focus on UK-based positions in the {field} field.

        For each job, extract:
        - Title: Full job title
        - Company: Company/organization name
        - Location: City/region in UK (or "Remote" if applicable)
        - Description: Complete job description including requirements and responsibilities
        - URL: Direct link to the job application page
        - Posted Date: When the job was posted (if shown)
        - Salary: Salary range or rate (if mentioned)

        Important:
        - Only include jobs based in the United Kingdom
        - Look for any mention of visa sponsorship in the description
        - If a job explicitly states "visa sponsorship available" or similar, include that in the description

        Return an empty array if no jobs found.
        """

        all_jobs = []

        # Process in batches of 10 (Firecrawl limit)
        batch_size = 10
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            print(f"   Extracting batch {i//batch_size + 1} ({len(batch)} URLs)...")

            try:
                result = self.firecrawl.extract(
                    urls=batch,
                    prompt=prompt,
                    schema=self.JOB_SCHEMA
                )

                if hasattr(result, 'data'):
                    data = result.data
                elif isinstance(result, dict):
                    data = result.get('data', result)
                else:
                    data = {}

                jobs = data.get('jobs', []) if isinstance(data, dict) else []
                all_jobs.extend(jobs)
                print(f"   Found {len(jobs)} jobs in batch")

                # Rate limiting: Add delay between batches to avoid hitting API limits
                if i + batch_size < len(urls):
                    print(f"   Waiting 4 seconds before next batch...")
                    time.sleep(4)

            except Exception as e:
                print(f"   ❌ Batch extraction failed: {e}")
                time.sleep(3)  # Even on error, wait before retrying
                continue

        return all_jobs

    # ============================================
    # AI Engineer & Marketing Scrapers
    # ============================================

    def scrape_otta(self, field: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape Otta.com for AI Engineer or Marketing roles.

        Args:
            field: 'AI_ENGINEER' or 'MARKETING'
            keywords: Search keywords (e.g., ['AI Engineer', 'Machine Learning'])

        Returns:
            List of job dictionaries
        """
        print(f"\n🔍 Scraping Otta for {field}...")

        base_urls = []
        for keyword in keywords:
            # Otta's job search format
            search_url = f"https://app.otta.com/jobs?location=United+Kingdom&search={keyword.replace(' ', '+')}"
            base_urls.append(search_url)

        # Crawl to discover individual job pages
        all_job_urls = []
        for url in base_urls:
            try:
                print(f"   Crawling: {url}")
                result = self.firecrawl.crawl(
                    url,
                    limit=50,
                    scrape_options={
                        'formats': ['markdown'],
                        'only_main_content': True
                    }
                )

                if result and hasattr(result, 'data'):
                    pages = result.data or []
                    # Filter for job detail pages
                    for page in pages:
                        metadata = page.get('metadata', {}) if isinstance(page, dict) else {}
                        page_url = metadata.get('sourceURL', '') or metadata.get('url', '')
                        if '/jobs/' in page_url and page_url not in all_job_urls:
                            all_job_urls.append(page_url)

                # Rate limiting: Add delay between crawls
                time.sleep(3)

            except Exception as e:
                print(f"   ⚠️  Crawl failed for {url}: {e}")
                time.sleep(3)
                continue

        print(f"   Found {len(all_job_urls)} job URLs")

        # Extract job details
        if all_job_urls:
            return self._extract_jobs_from_urls(all_job_urls[:30], field)  # Limit to 30
        return []

    def scrape_reed(self, field: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape Reed.co.uk for jobs.

        Args:
            field: Job field
            keywords: Search keywords

        Returns:
            List of job dictionaries
        """
        print(f"\n🔍 Scraping Reed for {field}...")

        base_urls = []
        for keyword in keywords:
            # Reed's job search format
            search_url = f"https://www.reed.co.uk/jobs/{keyword.lower().replace(' ', '-')}-jobs"
            base_urls.append(search_url)

        all_job_urls = []
        for url in base_urls:
            try:
                print(f"   Crawling: {url}")
                result = self.firecrawl.crawl(
                    url,
                    limit=50,
                    include_paths=['jobs'],
                    scrape_options={
                        'formats': ['markdown'],
                        'only_main_content': True
                    }
                )

                if result and hasattr(result, 'data'):
                    pages = result.data or []
                    for page in pages:
                        metadata = page.get('metadata', {}) if isinstance(page, dict) else {}
                        page_url = metadata.get('sourceURL', '') or metadata.get('url', '')
                        # Reed job URLs contain /jobs/ and a number
                        if '/jobs/' in page_url and re.search(r'/jobs/\d+/', page_url) and page_url not in all_job_urls:
                            all_job_urls.append(page_url)

                # Rate limiting: Add delay between crawls
                time.sleep(3)

            except Exception as e:
                print(f"   ⚠️  Crawl failed for {url}: {e}")
                time.sleep(3)
                continue

        print(f"   Found {len(all_job_urls)} job URLs")

        if all_job_urls:
            return self._extract_jobs_from_urls(all_job_urls[:30], field)
        return []

    def scrape_linkedin_uk(self, field: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape LinkedIn UK for jobs.

        Args:
            field: Job field
            keywords: Search keywords

        Returns:
            List of job dictionaries
        """
        print(f"\n🔍 Scraping LinkedIn UK for {field}...")

        base_urls = []
        for keyword in keywords:
            # LinkedIn job search with UK location filter
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={keyword.replace(' ', '%20')}&location=United%20Kingdom"
            base_urls.append(search_url)

        all_job_urls = []
        for url in base_urls:
            try:
                print(f"   Crawling: {url}")
                result = self.firecrawl.crawl(
                    url,
                    limit=40,
                    include_paths=['jobs/view'],
                    scrape_options={
                        'formats': ['markdown'],
                        'only_main_content': True
                    }
                )

                if result and hasattr(result, 'data'):
                    pages = result.data or []
                    for page in pages:
                        metadata = page.get('metadata', {}) if isinstance(page, dict) else {}
                        page_url = metadata.get('sourceURL', '') or metadata.get('url', '')
                        if '/jobs/view/' in page_url and page_url not in all_job_urls:
                            all_job_urls.append(page_url)

                # Rate limiting: Add delay between crawls
                time.sleep(3)

            except Exception as e:
                print(f"   ⚠️  Crawl failed for {url}: {e}")
                time.sleep(3)
                continue

        print(f"   Found {len(all_job_urls)} job URLs")

        if all_job_urls:
            return self._extract_jobs_from_urls(all_job_urls[:30], field)
        return []

    # ============================================
    # PhD Scrapers
    # ============================================

    def scrape_findaphd(self) -> List[Dict[str, Any]]:
        """Scrape FindAPhD.com for UK PhD positions."""
        print(f"\n🔍 Scraping FindAPhD for PhD positions...")

        url = "https://www.findaphd.com/phds/united-kingdom/"

        try:
            print(f"   Crawling: {url}")
            result = self.firecrawl.crawl(
                url,
                limit=60,
                include_paths=['phd', 'project'],
                scrape_options={
                    'formats': ['markdown'],
                    'only_main_content': True
                }
            )

            job_urls = []
            if result and hasattr(result, 'data'):
                pages = result.data or []
                for page in pages:
                    metadata = page.get('metadata', {}) if isinstance(page, dict) else {}
                    page_url = metadata.get('sourceURL', '') or metadata.get('url', '')
                    # PhD detail pages contain /phd/ or /project/
                    if ('/phd/' in page_url or '/project/' in page_url) and page_url not in job_urls:
                        job_urls.append(page_url)

            print(f"   Found {len(job_urls)} PhD URLs")

            if job_urls:
                return self._extract_jobs_from_urls(job_urls[:40], 'PHD')
            return []

        except Exception as e:
            print(f"   ❌ Crawl failed: {e}")
            return []

    def scrape_jobs_ac_uk(self) -> List[Dict[str, Any]]:
        """Scrape Jobs.ac.uk for PhD and research positions."""
        print(f"\n🔍 Scraping Jobs.ac.uk for PhD positions...")

        url = "https://www.jobs.ac.uk/phd"

        try:
            print(f"   Crawling: {url}")
            result = self.firecrawl.crawl(
                url,
                limit=50,
                include_paths=['job', 'search'],
                scrape_options={
                    'formats': ['markdown'],
                    'only_main_content': True
                }
            )

            job_urls = []
            if result and hasattr(result, 'data'):
                pages = result.data or []
                for page in pages:
                    metadata = page.get('metadata', {}) if isinstance(page, dict) else {}
                    page_url = metadata.get('sourceURL', '') or metadata.get('url', '')
                    if '/job/' in page_url and page_url not in job_urls:
                        job_urls.append(page_url)

            print(f"   Found {len(job_urls)} job URLs")

            if job_urls:
                return self._extract_jobs_from_urls(job_urls[:30], 'PHD')
            return []

        except Exception as e:
            print(f"   ❌ Crawl failed: {e}")
            return []

    # ============================================
    # Teaching Scrapers
    # ============================================

    def scrape_tes(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Scrape TES (Times Educational Supplement) for teaching jobs."""
        print(f"\n🔍 Scraping TES for teaching positions...")

        base_urls = []
        for keyword in keywords:
            search_url = f"https://www.tes.com/jobs/browse/united-kingdom?keyword={keyword.replace(' ', '+')}"
            base_urls.append(search_url)

        all_job_urls = []
        for url in base_urls:
            try:
                print(f"   Crawling: {url}")
                result = self.firecrawl.crawl(
                    url,
                    limit=50,
                    include_paths=['jobs/vacancy'],
                    scrape_options={
                        'formats': ['markdown'],
                        'only_main_content': True
                    }
                )

                if result and hasattr(result, 'data'):
                    pages = result.data or []
                    for page in pages:
                        metadata = page.get('metadata', {}) if isinstance(page, dict) else {}
                        page_url = metadata.get('sourceURL', '') or metadata.get('url', '')
                        if '/jobs/vacancy/' in page_url and page_url not in all_job_urls:
                            all_job_urls.append(page_url)

            except Exception as e:
                print(f"   ⚠️  Crawl failed for {url}: {e}")
                continue

        print(f"   Found {len(all_job_urls)} job URLs")

        if all_job_urls:
            return self._extract_jobs_from_urls(all_job_urls[:30], 'TEACHING')
        return []

    def scrape_teaching_vacancies(self) -> List[Dict[str, Any]]:
        """Scrape UK Government Teaching Vacancies service."""
        print(f"\n🔍 Scraping DfE Teaching Vacancies...")

        url = "https://teaching-vacancies.service.gov.uk/"

        try:
            print(f"   Crawling: {url}")
            result = self.firecrawl.crawl(
                url,
                limit=60,
                include_paths=['jobs'],
                scrape_options={
                    'formats': ['markdown'],
                    'only_main_content': True
                }
            )

            job_urls = []
            if result and hasattr(result, 'data'):
                pages = result.data or []
                for page in pages:
                    metadata = page.get('metadata', {}) if isinstance(page, dict) else {}
                    page_url = metadata.get('sourceURL', '') or metadata.get('url', '')
                    # Job pages have /jobs/ and a UUID pattern
                    if '/jobs/' in page_url and len(page_url.split('/')[-1]) > 10 and page_url not in job_urls:
                        job_urls.append(page_url)

            print(f"   Found {len(job_urls)} job URLs")

            if job_urls:
                return self._extract_jobs_from_urls(job_urls[:30], 'TEACHING')
            return []

        except Exception as e:
            print(f"   ❌ Crawl failed: {e}")
            return []

    # ============================================
    # Main Scraping Orchestrator
    # ============================================

    def scrape_all_fields(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scrape all job portals for all fields.

        Returns:
            Dictionary mapping field names to lists of jobs
        """
        all_results = {
            'AI_ENGINEER': [],
            'MARKETING': [],
            'PHD': [],
            'TEACHING': []
        }

        print("=" * 60)
        print("🚀 Starting UK Job Portal Scraping")
        print("=" * 60)

        # AI Engineer
        print("\n" + "=" * 60)
        print("AI ENGINEER JOBS")
        print("=" * 60)

        ai_keywords = ['AI Engineer', 'Machine Learning Engineer', 'Data Scientist', 'ML Engineer']

        try:
            all_results['AI_ENGINEER'].extend(self.scrape_otta('AI_ENGINEER', ai_keywords))
        except Exception as e:
            print(f"⚠️  Otta scraping failed: {e}")

        try:
            all_results['AI_ENGINEER'].extend(self.scrape_reed('AI_ENGINEER', ai_keywords))
        except Exception as e:
            print(f"⚠️  Reed scraping failed: {e}")

        try:
            all_results['AI_ENGINEER'].extend(self.scrape_linkedin_uk('AI_ENGINEER', ai_keywords))
        except Exception as e:
            print(f"⚠️  LinkedIn scraping failed: {e}")

        # Marketing
        print("\n" + "=" * 60)
        print("MARKETING JOBS")
        print("=" * 60)

        marketing_keywords = ['Marketing Executive', 'Digital Marketing', 'Marketing Manager', 'Growth Marketing']

        try:
            all_results['MARKETING'].extend(self.scrape_otta('MARKETING', marketing_keywords))
        except Exception as e:
            print(f"⚠️  Otta scraping failed: {e}")

        try:
            all_results['MARKETING'].extend(self.scrape_reed('MARKETING', marketing_keywords))
        except Exception as e:
            print(f"⚠️  Reed scraping failed: {e}")

        try:
            all_results['MARKETING'].extend(self.scrape_linkedin_uk('MARKETING', marketing_keywords))
        except Exception as e:
            print(f"⚠️  LinkedIn scraping failed: {e}")

        # PhD
        print("\n" + "=" * 60)
        print("PHD POSITIONS")
        print("=" * 60)

        try:
            all_results['PHD'].extend(self.scrape_findaphd())
        except Exception as e:
            print(f"⚠️  FindAPhD scraping failed: {e}")

        try:
            all_results['PHD'].extend(self.scrape_jobs_ac_uk())
        except Exception as e:
            print(f"⚠️  Jobs.ac.uk scraping failed: {e}")

        # Teaching
        print("\n" + "=" * 60)
        print("TEACHING JOBS")
        print("=" * 60)

        teaching_keywords = ['Maths Teacher', 'Business Teacher', 'Mathematics', 'Secondary Teacher']

        try:
            all_results['TEACHING'].extend(self.scrape_tes(teaching_keywords))
        except Exception as e:
            print(f"⚠️  TES scraping failed: {e}")

        try:
            all_results['TEACHING'].extend(self.scrape_teaching_vacancies())
        except Exception as e:
            print(f"⚠️  Teaching Vacancies scraping failed: {e}")

        # Summary
        print("\n" + "=" * 60)
        print("SCRAPING SUMMARY")
        print("=" * 60)
        for field, jobs in all_results.items():
            print(f"  {field}: {len(jobs)} jobs found")

        return all_results
