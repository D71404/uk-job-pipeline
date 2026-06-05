"""
UK Job Portal Scrapers
Scrapes job postings from major UK job boards using Firecrawl
"""

import os
import re
import time
import requests
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

    def __init__(self, api_key: Optional[str] = None, crust_api_key: Optional[str] = None):
        """Initialize Firecrawl and Crust API clients."""
        self.api_key = api_key or os.getenv('FIRECRAWL_API_KEY')
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY required in .env")

        self.firecrawl = Firecrawl(api_key=self.api_key)

        # Crust API for LinkedIn (more reliable than Firecrawl for LinkedIn)
        self.crust_api_key = crust_api_key or os.getenv('CRUST_API_KEY')
        self.crust_base_url = "https://api.getcrust.com/v1"

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
        Extract all job listings from these pages. These are UK job boards (CV Library, TotalJobs, CWJobs, Reed, Otta, Indeed, LinkedIn, etc).

        For each job posting found, extract:
        - title: The job title/role name (e.g., "Senior AI Engineer", "Marketing Manager")
        - company: Company or organization name
        - location: City/region in UK, or "Remote", or "Hybrid"
        - description: Complete job description text including:
          * Job responsibilities
          * Required qualifications and skills
          * Benefits and perks
          * ANY mention of visa sponsorship (tier 2, skilled worker visa, sponsorship available, etc.)
        - url: Direct URL to the job posting or application page
        - posted_date: When posted (if shown)
        - salary: Salary range or rate if mentioned

        CRITICAL INSTRUCTIONS:
        1. Only extract jobs based in the United Kingdom
        2. ALWAYS include the full description text - do not truncate
        3. If the job mentions visa sponsorship, tier 2 visa, skilled worker visa, or "right to work sponsorship", make sure this is clearly stated in the description field
        4. Extract the actual job posting URL (not the search results page)

        Return an empty array if no job postings are found on these pages.
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
        Scrape LinkedIn UK for jobs using Crust API (more reliable than Firecrawl).

        Uses Crust API which handles LinkedIn's anti-bot protections professionally.

        Args:
            field: Job field
            keywords: Search keywords

        Returns:
            List of job dictionaries
        """
        print(f"\n🔍 Scraping LinkedIn UK for {field} (via Crust API)...")

        # If Crust API key not available, fall back to Firecrawl (less reliable)
        if not self.crust_api_key:
            print(f"   ⚠️  CRUST_API_KEY not set, skipping LinkedIn")
            print(f"   ℹ️  Set CRUST_API_KEY in .env to enable LinkedIn scraping")
            return []

        all_jobs = []

        for keyword in keywords:
            try:
                print(f"   Searching LinkedIn for: {keyword}")

                # Crust API endpoint for LinkedIn job search
                headers = {
                    "Authorization": f"Bearer {self.crust_api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "keywords": keyword,
                    "location": "United Kingdom",
                    "limit": 25  # Jobs per keyword
                }

                # Call Crust API
                response = requests.post(
                    f"{self.crust_base_url}/linkedin/jobs/search",
                    headers=headers,
                    json=payload,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get('jobs', [])

                    # Transform Crust response to our format
                    for job in jobs:
                        transformed = {
                            'title': job.get('title', ''),
                            'company': job.get('company', ''),
                            'location': job.get('location', ''),
                            'description': job.get('description', ''),
                            'url': job.get('url', ''),
                            'posted_date': job.get('posted_date', ''),
                            'salary': job.get('salary', '')
                        }
                        all_jobs.append(transformed)

                    print(f"   ✓ Found {len(jobs)} jobs via Crust API")

                elif response.status_code == 401:
                    print(f"   ❌ Invalid CRUST_API_KEY")
                    break

                elif response.status_code == 429:
                    print(f"   ⏱️  Crust API rate limit reached, pausing...")
                    time.sleep(60)

                else:
                    print(f"   ⚠️  Crust API returned status {response.status_code}")

                # Rate limiting between keywords
                time.sleep(2)

            except requests.exceptions.Timeout:
                print(f"   ⏱️  Crust API timeout for keyword: {keyword}")
                continue

            except Exception as e:
                print(f"   ⚠️  LinkedIn scraping error: {e}")
                continue

        print(f"   Total LinkedIn jobs found: {len(all_jobs)}")
        return all_jobs

    def scrape_cv_library(self, field: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape CV Library for jobs.

        Args:
            field: Job field
            keywords: Search keywords

        Returns:
            List of job dictionaries
        """
        print(f"\n🔍 Scraping CV Library for {field}...")

        base_urls = []
        for keyword in keywords:
            search_url = f"https://www.cv-library.co.uk/search-jobs?q={keyword.replace(' ', '+')}&geo=United+Kingdom"
            base_urls.append(search_url)

        all_job_urls = []
        for url in base_urls:
            try:
                print(f"   Crawling: {url}")
                result = self.firecrawl.crawl(
                    url,
                    limit=40,
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
                        if ('/job/' in page_url or '/vacancy/' in page_url) and page_url not in all_job_urls:
                            all_job_urls.append(page_url)

                time.sleep(3)

            except Exception as e:
                print(f"   ⚠️  CV Library crawl failed: {e}")
                time.sleep(3)
                continue

        print(f"   Found {len(all_job_urls)} job URLs")

        if all_job_urls:
            return self._extract_jobs_from_urls(all_job_urls[:30], field)
        return []

    def scrape_totaljobs(self, field: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape TotalJobs for jobs.

        Args:
            field: Job field
            keywords: Search keywords

        Returns:
            List of job dictionaries
        """
        print(f"\n🔍 Scraping TotalJobs for {field}...")

        base_urls = []
        for keyword in keywords:
            search_url = f"https://www.totaljobs.com/jobs/{keyword.lower().replace(' ', '-')}?s=header"
            base_urls.append(search_url)

        all_job_urls = []
        for url in base_urls:
            try:
                print(f"   Crawling: {url}")
                result = self.firecrawl.crawl(
                    url,
                    limit=40,
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
                        if '/job/' in page_url and page_url not in all_job_urls:
                            all_job_urls.append(page_url)

                time.sleep(3)

            except Exception as e:
                print(f"   ⚠️  TotalJobs crawl failed: {e}")
                time.sleep(3)
                continue

        print(f"   Found {len(all_job_urls)} job URLs")

        if all_job_urls:
            return self._extract_jobs_from_urls(all_job_urls[:30], field)
        return []

    def scrape_cwjobs(self, field: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape CWJobs (great for Tech/AI roles) for jobs.

        Args:
            field: Job field
            keywords: Search keywords

        Returns:
            List of job dictionaries
        """
        print(f"\n🔍 Scraping CWJobs for {field}...")

        base_urls = []
        for keyword in keywords:
            search_url = f"https://www.cwjobs.co.uk/jobs/{keyword.lower().replace(' ', '-')}/in-united-kingdom"
            base_urls.append(search_url)

        all_job_urls = []
        for url in base_urls:
            try:
                print(f"   Crawling: {url}")
                result = self.firecrawl.crawl(
                    url,
                    limit=40,
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
                        if '/job/' in page_url and page_url not in all_job_urls:
                            all_job_urls.append(page_url)

                time.sleep(3)

            except Exception as e:
                print(f"   ⚠️  CWJobs crawl failed: {e}")
                time.sleep(3)
                continue

        print(f"   Found {len(all_job_urls)} job URLs")

        if all_job_urls:
            return self._extract_jobs_from_urls(all_job_urls[:30], field)
        return []

    def scrape_indeed_uk(self, field: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape Indeed UK for jobs.

        NOTE: Indeed has strong anti-bot protections. High risk of blocking.

        Args:
            field: Job field
            keywords: Search keywords

        Returns:
            List of job dictionaries (empty if blocked)
        """
        print(f"\n🔍 Scraping Indeed UK for {field}...")
        print(f"   ⚠️  Warning: Indeed has aggressive bot detection")

        base_urls = []
        for keyword in keywords:
            search_url = f"https://uk.indeed.com/jobs?q={keyword.replace(' ', '+')}&l=United+Kingdom"
            base_urls.append(search_url)

        all_job_urls = []
        for url in base_urls:
            try:
                print(f"   Crawling: {url}")
                result = self.firecrawl.crawl(
                    url,
                    limit=15,  # Very reduced limit to avoid detection
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
                        if ('/viewjob' in page_url or '/rc/clk' in page_url) and page_url not in all_job_urls:
                            all_job_urls.append(page_url)

                time.sleep(5)  # Longer delay for Indeed

            except Exception as e:
                # Graceful handling of Indeed blocking
                error_msg = str(e).lower()
                if '403' in error_msg or 'forbidden' in error_msg or 'blocked' in error_msg:
                    print(f"   🚫 Indeed blocked scraping today, moving to next portal")
                elif 'timeout' in error_msg:
                    print(f"   ⏱️  Indeed timeout, moving to next portal")
                elif 'captcha' in error_msg or 'recaptcha' in error_msg:
                    print(f"   🤖 Indeed showing CAPTCHA, moving to next portal")
                else:
                    print(f"   ⚠️  Indeed crawl failed: {e}")

                time.sleep(3)
                continue

        if len(all_job_urls) == 0:
            print(f"   ℹ️  No jobs found on Indeed (likely blocked)")
            return []

        print(f"   Found {len(all_job_urls)} job URLs")

        if all_job_urls:
            return self._extract_jobs_from_urls(all_job_urls[:10], field)  # Very limited batch
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
            all_results['AI_ENGINEER'].extend(self.scrape_cv_library('AI_ENGINEER', ai_keywords))
        except Exception as e:
            print(f"⚠️  CV Library scraping failed: {e}")

        try:
            all_results['AI_ENGINEER'].extend(self.scrape_totaljobs('AI_ENGINEER', ai_keywords))
        except Exception as e:
            print(f"⚠️  TotalJobs scraping failed: {e}")

        try:
            all_results['AI_ENGINEER'].extend(self.scrape_cwjobs('AI_ENGINEER', ai_keywords))
        except Exception as e:
            print(f"⚠️  CWJobs scraping failed: {e}")

        try:
            all_results['AI_ENGINEER'].extend(self.scrape_linkedin_uk('AI_ENGINEER', ai_keywords))
        except Exception as e:
            print(f"⚠️  LinkedIn scraping failed: {e}")

        try:
            all_results['AI_ENGINEER'].extend(self.scrape_indeed_uk('AI_ENGINEER', ai_keywords))
        except Exception as e:
            print(f"⚠️  Indeed scraping failed: {e}")

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
            all_results['MARKETING'].extend(self.scrape_cv_library('MARKETING', marketing_keywords))
        except Exception as e:
            print(f"⚠️  CV Library scraping failed: {e}")

        try:
            all_results['MARKETING'].extend(self.scrape_totaljobs('MARKETING', marketing_keywords))
        except Exception as e:
            print(f"⚠️  TotalJobs scraping failed: {e}")

        try:
            all_results['MARKETING'].extend(self.scrape_linkedin_uk('MARKETING', marketing_keywords))
        except Exception as e:
            print(f"⚠️  LinkedIn scraping failed: {e}")

        try:
            all_results['MARKETING'].extend(self.scrape_indeed_uk('MARKETING', marketing_keywords))
        except Exception as e:
            print(f"⚠️  Indeed scraping failed: {e}")

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
        total_all = 0
        for field, jobs in all_results.items():
            count = len(jobs)
            total_all += count
            print(f"  {field}: {count} jobs found")

        print(f"\n  TOTAL: {total_all} jobs across all fields")
        print("\n  Job Portals Scraped:")
        print("    ✓ Otta (Startups/Tech)")
        print("    ✓ Reed UK (General)")
        print("    ✓ CV Library (General)")
        print("    ✓ TotalJobs (General)")
        print("    ✓ CWJobs (Tech/IT)")
        print("    ✓ LinkedIn UK (May be blocked)")
        print("    ✓ Indeed UK (May be blocked)")
        print("    ✓ FindAPhD (PhD only)")
        print("    ✓ Jobs.ac.uk (Academia)")
        print("    ✓ TES (Teaching)")
        print("    ✓ Gov Teaching Vacancies (Teaching)")
        print("=" * 60)

        return all_results
