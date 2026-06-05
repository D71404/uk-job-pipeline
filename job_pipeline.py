#!/usr/bin/env python3
"""
Automated Job Application Pipeline
==================================

Daily workflow:
1. Scrape UK job portals for 4 niches (AI Engineer, Marketing, PhDs, Teaching)
2. Check if company offers visa sponsorship (DB + description parsing)
3. Insert sponsored jobs into Supabase (handles duplicates automatically)
4. For NEW jobs: Fetch master CV, tailor with Claude AI, save to tweaked_cvs
5. Update job status to CV_TWEAKED

Usage:
    python job_pipeline.py              # Run full pipeline
    python job_pipeline.py --scrape     # Only scrape jobs
    python job_pipeline.py --tailor     # Only tailor CVs for existing NEW jobs
    python job_pipeline.py --stats      # Show pipeline statistics
"""

import os
import sys
import argparse
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime
from dotenv import load_dotenv

# Import our custom modules
from job_pipeline_client import JobPipelineClient
from uk_job_scrapers import UKJobScrapers
from cv_optimizer import CVOptimizer, CVQualityChecker

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'pipeline_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class JobPipeline:
    """Main pipeline orchestrator."""

    def __init__(self):
        """Initialize all pipeline components."""
        logger.info("Initializing Job Pipeline...")

        try:
            self.db = JobPipelineClient()
            self.scrapers = UKJobScrapers()
            self.cv_optimizer = CVOptimizer()
            logger.info("✅ All components initialized successfully")
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            raise

    # ============================================
    # Step 1: Scrape Jobs
    # ============================================

    def scrape_jobs(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scrape all UK job portals for all niches.

        Returns:
            Dictionary mapping field names to lists of scraped jobs
        """
        logger.info("\n" + "=" * 70)
        logger.info("STEP 1: SCRAPING UK JOB PORTALS")
        logger.info("=" * 70)

        try:
            results = self.scrapers.scrape_all_fields()
            total_jobs = sum(len(jobs) for jobs in results.values())

            if total_jobs == 0:
                logger.warning(f"\n⚠️  No jobs found during scraping. This could be due to:")
                logger.warning("   - Job portals being temporarily unavailable")
                logger.warning("   - Rate limiting by job sites")
                logger.warning("   - Changes to job portal website structure")
                logger.warning("   Pipeline will exit gracefully.")
            else:
                logger.info(f"\n✅ Scraping complete! Found {total_jobs} total jobs")

            return results
        except Exception as e:
            logger.error(f"❌ Scraping failed: {e}")
            return {'AI_ENGINEER': [], 'MARKETING': [], 'PHD': [], 'TEACHING': []}

    # ============================================
    # Step 2: Filter Sponsored Jobs
    # ============================================

    def filter_sponsored_jobs(
        self,
        scraped_jobs: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Filter jobs to only include those with visa sponsorship.

        Args:
            scraped_jobs: Dictionary of field -> jobs from scraping

        Returns:
            Dictionary of field -> sponsored jobs only
        """
        logger.info("\n" + "=" * 70)
        logger.info("STEP 2: FILTERING FOR SPONSORED JOBS")
        logger.info("=" * 70)

        sponsored_jobs = {
            'AI_ENGINEER': [],
            'MARKETING': [],
            'PHD': [],
            'TEACHING': []
        }

        total_checked = 0
        total_sponsored = 0

        for field, jobs in scraped_jobs.items():
            logger.info(f"\nChecking {field}: {len(jobs)} jobs")

            for job in jobs:
                total_checked += 1
                company = job.get('company', '')
                description = job.get('description', '')

                # Check sponsorship
                is_sponsored, reason = self.db.check_sponsorship(company, description)

                if is_sponsored:
                    logger.info(f"  ✓ {company}: {job.get('title', 'Unknown')} - {reason}")
                    sponsored_jobs[field].append(job)
                    total_sponsored += 1

        logger.info(f"\n✅ Sponsorship filtering complete")
        logger.info(f"   Checked: {total_checked} jobs")

        # Safety check to prevent division by zero
        if total_checked > 0:
            percentage = (total_sponsored / total_checked) * 100
            logger.info(f"   Sponsored: {total_sponsored} jobs ({percentage:.1f}%)")
        else:
            logger.info(f"   Sponsored: {total_sponsored} jobs (0 jobs checked)")

        return sponsored_jobs

    # ============================================
    # Step 3: Insert Jobs into Database
    # ============================================

    def insert_jobs_to_db(
        self,
        sponsored_jobs: Dict[str, List[Dict[str, Any]]]
    ) -> Tuple[int, int]:
        """
        Insert sponsored jobs into Supabase database.
        Handles duplicates gracefully via unique URL constraint.

        Args:
            sponsored_jobs: Dictionary of field -> sponsored jobs

        Returns:
            Tuple of (inserted_count, skipped_count)
        """
        logger.info("\n" + "=" * 70)
        logger.info("STEP 3: INSERTING JOBS INTO DATABASE")
        logger.info("=" * 70)

        total_inserted = 0
        total_skipped = 0

        for field, jobs in sponsored_jobs.items():
            if not jobs:
                continue

            logger.info(f"\nInserting {len(jobs)} {field} jobs...")

            for job in jobs:
                # Prepare job data for database
                job_data = {
                    'company_name': job.get('company', 'Unknown'),
                    'job_title': job.get('title', 'Untitled Position'),
                    'job_url': job.get('url', ''),
                    'description': job.get('description', ''),
                    'field': field
                }

                # Skip if missing critical data
                if not job_data['job_url'] or not job_data['description']:
                    logger.warning(f"   ⚠️  Skipping job with missing data: {job_data['job_title']}")
                    total_skipped += 1
                    continue

                # Attempt insert
                job_id = self.db.insert_job(job_data)

                if job_id:
                    logger.info(f"   ✓ Inserted: {job_data['job_title']} (ID: {job_id})")
                    total_inserted += 1
                else:
                    # Duplicate or error (already logged in client)
                    total_skipped += 1

        logger.info(f"\n✅ Database insertion complete")
        logger.info(f"   Inserted: {total_inserted} new jobs")
        logger.info(f"   Skipped: {total_skipped} duplicates/errors")

        return total_inserted, total_skipped

    # ============================================
    # Step 4: Tailor CVs for NEW Jobs
    # ============================================

    def tailor_cvs_for_new_jobs(self, limit: int = 50) -> int:
        """
        Fetch NEW jobs, tailor CVs, save to tweaked_cvs, update status.

        Args:
            limit: Maximum number of jobs to process

        Returns:
            Number of CVs successfully tailored
        """
        logger.info("\n" + "=" * 70)
        logger.info("STEP 4: TAILORING CVs FOR NEW JOBS")
        logger.info("=" * 70)

        # Fetch jobs with status = NEW
        new_jobs = self.db.get_jobs_by_status('NEW')[:limit]

        if not new_jobs:
            logger.info("No new jobs requiring CV tailoring")
            return 0

        logger.info(f"Found {len(new_jobs)} jobs needing CV tailoring")

        # Fetch master CVs for each field
        master_cvs = {}
        for field in ['AI_ENGINEER', 'TEACHING', 'PHD', 'MARKETING']:
            cv = self.db.get_master_cv(field)
            if cv:
                master_cvs[field] = cv
                logger.info(f"  ✓ Loaded master CV for {field}")
            else:
                logger.warning(f"  ⚠️  No master CV found for {field}")

        if not master_cvs:
            logger.error("❌ No master CVs available. Please upload master CVs to the database first.")
            return 0

        # Tailor CVs
        tailored_count = 0

        for i, job in enumerate(new_jobs, 1):
            job_id = job['id']
            field = job['field']
            job_title = job['job_title']
            company = job['company_name']

            logger.info(f"\n[{i}/{len(new_jobs)}] Processing: {job_title} at {company}")

            # Check if master CV exists for this field
            if field not in master_cvs:
                logger.warning(f"   ⚠️  No master CV for {field}, skipping...")
                continue

            try:
                # Tailor CV
                tailored_cv = self.cv_optimizer.tailor_cv(
                    master_cv_markdown=master_cvs[field],
                    job_title=job_title,
                    company_name=company,
                    job_description=job['description'],
                    field=field
                )

                # Quality check
                quality = CVQualityChecker.check_cv_quality(tailored_cv, job['description'])

                if not quality['passed']:
                    logger.warning(f"   ⚠️  CV quality check failed (score: {quality['score']}/100)")
                    logger.warning(f"   Issues: {', '.join(quality['issues'])}")
                    # Still save it, but log the warning

                # Save to tweaked_cvs table
                cv_id = self.db.insert_tweaked_cv(job_id, tailored_cv)

                if cv_id:
                    logger.info(f"   ✓ Saved tailored CV (ID: {cv_id})")

                    # Update job status to CV_TWEAKED
                    if self.db.update_job_status(job_id, 'CV_TWEAKED'):
                        logger.info(f"   ✓ Status updated to CV_TWEAKED")
                        tailored_count += 1
                    else:
                        logger.error(f"   ❌ Failed to update job status")
                else:
                    logger.error(f"   ❌ Failed to save tailored CV")

            except Exception as e:
                logger.error(f"   ❌ CV tailoring failed: {e}")
                continue

        logger.info(f"\n✅ CV tailoring complete: {tailored_count}/{len(new_jobs)} successful")
        return tailored_count

    # ============================================
    # Full Pipeline Execution
    # ============================================

    def run_full_pipeline(self) -> Dict[str, Any]:
        """
        Execute the complete pipeline end-to-end.

        Returns:
            Summary statistics
        """
        logger.info("\n" + "=" * 70)
        logger.info("🚀 STARTING AUTOMATED JOB PIPELINE")
        logger.info(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)

        start_time = datetime.now()

        # Step 1: Scrape jobs
        scraped_jobs = self.scrape_jobs()
        total_scraped = sum(len(jobs) for jobs in scraped_jobs.values())

        # Early exit if no jobs scraped
        if total_scraped == 0:
            logger.info("\n⚠️  No jobs scraped. Exiting pipeline gracefully.")
            logger.info("=" * 70)
            return {
                'timestamp': datetime.now().isoformat(),
                'duration_seconds': (datetime.now() - start_time).total_seconds(),
                'total_scraped': 0,
                'total_sponsored': 0,
                'jobs_inserted': 0,
                'jobs_skipped': 0,
                'cvs_tailored': 0,
                'status': 'no_jobs_found'
            }

        # Step 2: Filter for sponsorship
        sponsored_jobs = self.filter_sponsored_jobs(scraped_jobs)
        total_sponsored = sum(len(jobs) for jobs in sponsored_jobs.values())

        # Step 3: Insert into database
        inserted, skipped = self.insert_jobs_to_db(sponsored_jobs)

        # Step 4: Tailor CVs
        cvs_tailored = self.tailor_cvs_for_new_jobs()

        # Calculate duration
        duration = datetime.now() - start_time

        # Final summary
        summary = {
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration.total_seconds(),
            'total_scraped': total_scraped,
            'total_sponsored': total_sponsored,
            'jobs_inserted': inserted,
            'jobs_skipped': skipped,
            'cvs_tailored': cvs_tailored,
            'pipeline_stats': self.db.get_pipeline_stats()
        }

        logger.info("\n" + "=" * 70)
        logger.info("🎉 PIPELINE COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Duration: {duration.total_seconds():.1f}s")
        logger.info(f"Scraped: {total_scraped} jobs")
        logger.info(f"Sponsored: {total_sponsored} jobs")
        logger.info(f"Inserted: {inserted} new jobs")
        logger.info(f"Skipped: {skipped} duplicates")
        logger.info(f"CVs Tailored: {cvs_tailored}")
        logger.info("=" * 70)

        return summary

    def show_stats(self):
        """Display current pipeline statistics."""
        logger.info("\n" + "=" * 70)
        logger.info("📊 PIPELINE STATISTICS")
        logger.info("=" * 70)

        stats = self.db.get_pipeline_stats()

        logger.info(f"\nTotal Jobs: {stats.get('total_jobs', 0)}")

        logger.info("\nBy Field:")
        for field, count in stats.get('by_field', {}).items():
            logger.info(f"  {field}: {count}")

        logger.info("\nBy Status:")
        for status, count in stats.get('by_status', {}).items():
            logger.info(f"  {status}: {count}")

        logger.info("\n" + "=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Automated UK Job Application Pipeline'
    )
    parser.add_argument(
        '--scrape',
        action='store_true',
        help='Only scrape jobs (skip CV tailoring)'
    )
    parser.add_argument(
        '--tailor',
        action='store_true',
        help='Only tailor CVs for existing NEW jobs (skip scraping)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show pipeline statistics'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of jobs to process (default: 50)'
    )

    args = parser.parse_args()

    try:
        pipeline = JobPipeline()

        if args.stats:
            # Show stats only
            pipeline.show_stats()

        elif args.scrape:
            # Scrape and insert only
            scraped = pipeline.scrape_jobs()
            sponsored = pipeline.filter_sponsored_jobs(scraped)
            inserted, skipped = pipeline.insert_jobs_to_db(sponsored)
            logger.info(f"\n✅ Scraping complete: {inserted} inserted, {skipped} skipped")

        elif args.tailor:
            # Tailor CVs only
            tailored = pipeline.tailor_cvs_for_new_jobs(limit=args.limit)
            logger.info(f"\n✅ CV tailoring complete: {tailored} CVs processed")

        else:
            # Run full pipeline
            summary = pipeline.run_full_pipeline()
            logger.info("\n✅ Full pipeline execution complete")

    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Pipeline failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
