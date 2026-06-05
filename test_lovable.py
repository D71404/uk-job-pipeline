#!/usr/bin/env python3
"""
Test Lovable integration by scraping and saving to review queue
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from job_scraper import JobScraper
from supabase_lovable_client import LovableJobStore


def main():
    url = input("Enter company URL to scrape: ").strip()
    company = input("Enter company name (optional): ").strip()

    if not url:
        print("❌ URL required")
        return

    print(f"\n🔍 Scraping {url}...")

    # Scrape
    scraper = JobScraper()
    pages = scraper.crawl_website(url, limit=50)

    if not pages:
        print("❌ No pages found")
        return

    career_urls = scraper.filter_career_urls(pages)
    if not career_urls:
        print("❌ No career pages found")
        return

    jobs_data = scraper.extract_jobs(career_urls)
    jobs = jobs_data.get('jobs', [])

    print(f"\n📝 Found {len(jobs)} jobs")

    if not jobs:
        return

    # Preview
    print("\nPreview:")
    for i, job in enumerate(jobs[:3], 1):
        print(f"  {i}. {job.get('title')} - {job.get('location', 'N/A')}")

    # Save to review queue
    save = input(f"\nSave {len(jobs)} jobs to review queue? (y/n): ").lower()
    if save == 'y':
        store = LovableJobStore()
        review_ids = store.insert_to_review(jobs, company_name=company, source_url=url)
        print(f"\n✅ Saved {len(review_ids)} jobs to review queue")

        # Show stats
        stats = store.get_stats()
        print(f"\n📊 Review Queue Stats:")
        print(f"   Pending: {stats['pending']}")
        print(f"   Approved: {stats['approved']}")
        print(f"   Rejected: {stats['rejected']}")


if __name__ == '__main__':
    main()
