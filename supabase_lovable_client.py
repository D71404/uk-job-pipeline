"""
Supabase client for Lovable bd_job_intel schema
Maps scraped jobs to the exact table structure
"""

import os
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

try:
    from supabase import create_client, Client
except ImportError:
    raise ImportError("Install supabase: pip install supabase")


class LovableJobStore:
    """
    Store jobs in Lovable's bd_job_reviews (staging) and bd_job_intel (production)
    """

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = url or os.getenv('SUPABASE_URL')
        self.key = key or os.getenv('SUPABASE_KEY')

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY required in .env")

        self.client: Client = create_client(self.url, self.key)
        self.review_table = 'bd_job_reviews'
        self.intel_table = 'bd_job_intel'

    def _parse_salary(self, salary_text: str) -> tuple:
        """Extract min/max salary from text."""
        if not salary_text:
            return None, None

        # Find all numbers with K or $ signs
        numbers = []

        # Pattern: $100k-$150k or 100k-150k
        pattern1 = r'\$?(\d+)[kK]?\s*-\s*\$?(\d+)[kK]?'
        match = re.search(pattern1, salary_text)
        if match:
            min_val = int(match.group(1))
            max_val = int(match.group(2))
            # Convert K to actual number
            if 'k' in salary_text.lower():
                min_val *= 1000
                max_val *= 1000
            return min_val, max_val

        # Pattern: single number
        pattern2 = r'\$?(\d+)[kK]?'
        matches = re.findall(pattern2, salary_text)
        if matches:
            nums = [int(m) * 1000 if 'k' in salary_text.lower() else int(m) for m in matches]
            return min(nums), max(nums)

        return None, None

    def _parse_years_experience(self, text: str) -> tuple:
        """Extract years of experience from text."""
        if not text:
            return None, None

        # Pattern: 3-5 years, 3+ years, 5 years
        patterns = [
            r'(\d+)\s*-\s*(\d+)\s*(?:years?|yrs?)',
            r'(\d+)\+?\s*(?:years?|yrs?)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                if len(match.groups()) == 2:
                    return int(match.group(1)), int(match.group(2))
                else:
                    years = int(match.group(1))
                    return years, years + 5  # Assume +5 for max

        return None, None

    def _extract_skills(self, description: str, requirements: str) -> List[str]:
        """Extract skills from job text."""
        text = f"{description} {requirements}".lower()

        common_skills = [
            'python', 'javascript', 'typescript', 'react', 'node.js', 'nodejs',
            'sql', 'postgresql', 'mysql', 'mongodb', 'aws', 'gcp', 'azure',
            'docker', 'kubernetes', 'terraform', 'ci/cd', 'git', 'github',
            'machine learning', 'ai', 'data science', 'tensorflow', 'pytorch',
            'java', 'kotlin', 'swift', 'go', 'golang', 'rust', 'c++', 'c#',
            '.net', 'django', 'flask', 'fastapi', 'spring', 'rails',
            'angular', 'vue', 'svelte', 'next.js', 'nuxt',
            'redis', 'kafka', 'elasticsearch', 'spark', 'hadoop',
            'tableau', 'powerbi', 'looker', 'pandas', 'numpy',
            'agile', 'scrum', 'jira', 'confluence', 'figma', 'sketch'
        ]

        found_skills = []
        for skill in common_skills:
            if skill in text:
                found_skills.append(skill)

        return found_skills

    def _detect_remote_type(self, location: str, description: str) -> str:
        """Detect remote/hybrid/onsite from text."""
        text = f"{location} {description}".lower()

        if 'remote' in text or 'work from home' in text or 'wfh' in text:
            return 'Remote'
        elif 'hybrid' in text:
            return 'Hybrid'
        else:
            return 'On-site'

    def _detect_seniority(self, title: str, description: str) -> str:
        """Detect seniority level from title/description."""
        text = f"{title} {description}".lower()

        if any(x in text for x in ['principal', 'staff', 'distinguished', 'fellow']):
            return 'Principal/Staff'
        elif any(x in text for x in ['senior', 'sr.', 'lead', 'staff']):
            return 'Senior'
        elif any(x in text for x in ['manager', 'director', 'head of']):
            return 'Manager'
        elif any(x in text for x in ['junior', 'jr.', 'entry', 'associate', 'intern']):
            return 'Junior'
        else:
            return 'Mid-level'

    def _normalize_job_title(self, title: str) -> str:
        """Normalize job title for matching."""
        title_lower = title.lower()

        # Map common variations
        mappings = {
            'software engineer': 'swe',
            'frontend': 'swe_frontend',
            'backend': 'swe_backend',
            'full stack': 'swe_fullstack',
            'fullstack': 'swe_fullstack',
            'devops': 'devops_engineer',
            'data scientist': 'data_scientist',
            'data engineer': 'data_engineer',
            'ml engineer': 'ml_engineer',
            'machine learning': 'ml_engineer',
            'product manager': 'product_manager',
            'designer': 'designer',
        }

        for key, value in mappings.items():
            if key in title_lower:
                return value

        return 'other'

    def _detect_category(self, title: str, department: str) -> tuple:
        """Detect job category and subcategory."""
        text = f"{title} {department}".lower()

        categories = {
            'Engineering': ['engineer', 'developer', 'devops', 'sre', 'architect'],
            'Data': ['data scientist', 'data engineer', 'data analyst', 'ml engineer', 'ai engineer'],
            'Product': ['product manager', 'product owner', 'program manager'],
            'Design': ['designer', 'ux', 'ui', 'product design'],
            'Marketing': ['marketing', 'growth', 'seo', 'content'],
            'Sales': ['sales', 'account executive', 'sdr', 'business development'],
            'Operations': ['operations', 'ops', 'analyst'],
            'HR': ['hr', 'recruiter', 'talent', 'people'],
        }

        for category, keywords in categories.items():
            if any(kw in text for kw in keywords):
                return category, self._normalize_job_title(title)

        return 'Other', 'other'

    def map_scraped_job(self, scraped: Dict[str, Any], company_name: str = "", source_url: str = "") -> Dict[str, Any]:
        """
        Map scraped job data to bd_job_intel schema
        """
        title = scraped.get('title', '')
        description = scraped.get('description', '')
        requirements = scraped.get('requirements', '')
        location = scraped.get('location', '')

        # Parse salary
        salary_min, salary_max = self._parse_salary(scraped.get('salary_range', ''))

        # Parse years experience
        years_min, years_max = self._parse_years_experience(description)

        # Extract skills
        skills = self._extract_skills(description, requirements)

        # Detect fields
        remote_type = self._detect_remote_type(location, description)
        seniority = self._detect_seniority(title, description)
        category, subcategory = self._detect_category(title, scraped.get('department', ''))

        # Build job_description_summary
        summary = f"{title} at {company_name or 'Company'}. "
        if location:
            summary += f"Located in {location}. "
        summary += f"{remote_type} position. "
        if skills:
            summary += f"Key skills: {', '.join(skills[:5])}."

        # Build required_experiences array
        experiences = []
        if requirements:
            # Split by bullet points or newlines
            lines = re.split(r'[\n•\-]', requirements)
            experiences = [l.strip() for l in lines if l.strip() and len(l.strip()) > 10][:5]

        return {
            'job_title': title,
            'job_title_normalized': self._normalize_job_title(title),
            'company_name': company_name or scraped.get('company', ''),
            'company_linkedin_url': None,
            'job_url': scraped.get('apply_url', ''),
            'job_description_url': source_url,
            'full_job_description': description,
            'job_description_summary': summary,
            'job_category': category,
            'job_subcategory': subcategory,
            'location': location,
            'remote_type': remote_type,
            'seniority_level': seniority,
            'department': scraped.get('department', ''),
            'clearance_required': None,
            'salary_min': salary_min,
            'salary_max': salary_max,
            'equity_range': None,
            'bonus_target': None,
            'bonus_type': None,
            'skills_mentioned': skills,
            'nice_to_have_skills': [],
            'required_experiences': experiences,
            'years_experience_min': years_min,
            'years_experience_max': years_max,
            'travel_requirement': None,
            'team_size': None,
            'is_leadership_role': any(x in title.lower() for x in ['lead', 'manager', 'director', 'head', 'principal', 'staff']),
            'source_url': source_url,
            'scraped_at': datetime.now().isoformat(),
            'raw_scraped_data': scraped,
            'metadata': {
                'scraped_by': 'firecrawl_job_scraper',
                'original_responsibilities': scraped.get('responsibilities', ''),
                'original_requirements': scraped.get('requirements', ''),
            }
        }

    def insert_to_review(self, jobs: List[Dict[str, Any]], company_name: str = "", source_url: str = "") -> List[str]:
        """
        Insert scraped jobs to bd_job_reviews (staging table)
        Returns list of inserted review IDs
        """
        if not jobs:
            print("⚠️ No jobs to insert")
            return []

        inserted_ids = []
        print(f"\n💾 Saving {len(jobs)} jobs to review queue...")

        for job in jobs:
            try:
                # Map to schema
                mapped = self.map_scraped_job(job, company_name, source_url)

                # Insert to review table
                result = self.client.table(self.review_table).insert(mapped).execute()

                if result.data:
                    inserted_ids.append(result.data[0]['id'])

            except Exception as e:
                print(f"   ❌ Failed to insert job '{job.get('title', 'Unknown')}': {e}")
                continue

        print(f"✅ Inserted {len(inserted_ids)}/{len(jobs)} jobs to review queue")
        return inserted_ids

    def get_pending_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending jobs waiting for review."""
        result = (self.client.table(self.review_table)
                  .select('*')
                  .eq('review_status', 'pending')
                  .order('created_at', desc=True)
                  .limit(limit)
                  .execute())
        return result.data if result else []

    def approve_job(self, review_job_id: str, reviewer_user_id: str) -> Optional[str]:
        """
        Approve job and copy to bd_job_intel
        Returns the new job ID in bd_job_intel
        """
        try:
            result = self.client.rpc(
                'approve_job_to_intel',
                {'review_job_id': review_job_id, 'reviewer_user_id': reviewer_user_id}
            ).execute()

            if result.data:
                print(f"✅ Job approved and moved to bd_job_intel: {result.data}")
                return result.data

        except Exception as e:
            print(f"❌ Failed to approve job: {e}")

        return None

    def reject_job(self, review_job_id: str, reviewer_user_id: str, notes: str = "") -> bool:
        """Reject a job review."""
        try:
            self.client.rpc(
                'reject_job_review',
                {'review_job_id': review_job_id, 'reviewer_user_id': reviewer_user_id, 'notes': notes}
            ).execute()
            print(f"✅ Job rejected: {review_job_id}")
            return True
        except Exception as e:
            print(f"❌ Failed to reject job: {e}")
            return False

    def get_stats(self) -> Dict[str, int]:
        """Get review queue stats."""
        try:
            pending = self.client.table(self.review_table).select('*', count='exact').eq('review_status', 'pending').execute()
            approved = self.client.table(self.review_table).select('*', count='exact').eq('review_status', 'approved').execute()
            rejected = self.client.table(self.review_table).select('*', count='exact').eq('review_status', 'rejected').execute()

            return {
                'pending': pending.count if pending else 0,
                'approved': approved.count if approved else 0,
                'rejected': rejected.count if rejected else 0,
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {'pending': 0, 'approved': 0, 'rejected': 0}
