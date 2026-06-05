"""
CV Optimizer using Claude AI
Tailors master CVs to specific job requirements
"""

import os
import re
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

try:
    from anthropic import Anthropic
except ImportError:
    raise ImportError("Install anthropic: pip install anthropic")

load_dotenv()


class CVOptimizer:
    """AI-powered CV optimization engine using Claude."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-5-20250929"):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key
            model: Claude model to use (default: Claude Sonnet 4.5)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required in .env")

        self.client = Anthropic(api_key=self.api_key)
        self.model = model

    def tailor_cv(
        self,
        master_cv_markdown: str,
        job_title: str,
        company_name: str,
        job_description: str,
        field: str
    ) -> str:
        """
        Tailor a master CV to match a specific job posting.

        Args:
            master_cv_markdown: Original CV in markdown format
            job_title: Target job title
            company_name: Target company name
            job_description: Full job description and requirements
            field: Job field (AI_ENGINEER, TEACHING, PHD, MARKETING)

        Returns:
            Tailored CV in markdown format
        """
        print(f"\n🤖 Tailoring CV for: {job_title} at {company_name}")

        # Analyze job requirements first
        job_analysis = self._analyze_job_requirements(
            job_title,
            company_name,
            job_description,
            field
        )

        # Generate tailored CV
        tailored_cv = self._generate_tailored_cv(
            master_cv_markdown,
            job_title,
            company_name,
            job_description,
            job_analysis,
            field
        )

        print(f"✅ CV tailored successfully ({len(tailored_cv)} characters)")
        return tailored_cv

    def _analyze_job_requirements(
        self,
        job_title: str,
        company_name: str,
        job_description: str,
        field: str
    ) -> Dict[str, Any]:
        """
        Analyze job posting to extract key requirements.

        Returns:
            Dictionary with key_skills, required_experiences, priorities, company_values
        """
        print("   📊 Analyzing job requirements...")

        prompt = f"""Analyze this job posting and extract the key requirements for CV optimization.

Job Title: {job_title}
Company: {company_name}
Field: {field}

Job Description:
{job_description}

Please analyze and extract:
1. **Key Technical Skills**: The most important technical skills mentioned (max 5)
2. **Required Experiences**: Essential experience requirements (years, domains, achievements)
3. **Soft Skills**: Important soft skills and personal qualities mentioned
4. **Company Values**: Values or culture hints that should be reflected
5. **Priority Keywords**: Critical keywords/phrases that should appear in the CV

Return your analysis in this exact format:

KEY SKILLS:
- [skill 1]
- [skill 2]
...

REQUIRED EXPERIENCES:
- [experience 1]
- [experience 2]
...

SOFT SKILLS:
- [skill 1]
- [skill 2]
...

COMPANY VALUES:
- [value 1]
- [value 2]
...

PRIORITY KEYWORDS:
- [keyword 1]
- [keyword 2]
...
"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            analysis_text = message.content[0].text

            # Parse the analysis
            analysis = {
                'key_skills': self._extract_section(analysis_text, 'KEY SKILLS'),
                'required_experiences': self._extract_section(analysis_text, 'REQUIRED EXPERIENCES'),
                'soft_skills': self._extract_section(analysis_text, 'SOFT SKILLS'),
                'company_values': self._extract_section(analysis_text, 'COMPANY VALUES'),
                'priority_keywords': self._extract_section(analysis_text, 'PRIORITY KEYWORDS'),
                'raw_analysis': analysis_text
            }

            print(f"   ✓ Identified {len(analysis['key_skills'])} key skills")
            print(f"   ✓ Identified {len(analysis['priority_keywords'])} priority keywords")

            return analysis

        except Exception as e:
            print(f"   ⚠️  Analysis failed: {e}")
            return {
                'key_skills': [],
                'required_experiences': [],
                'soft_skills': [],
                'company_values': [],
                'priority_keywords': [],
                'raw_analysis': ''
            }

    def _extract_section(self, text: str, section_name: str) -> list:
        """Extract bulleted list from a section."""
        pattern = rf"{section_name}:\s*((?:[-•]\s*.+\n?)+)"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            section_text = match.group(1)
            items = re.findall(r'[-•]\s*(.+)', section_text)
            return [item.strip() for item in items if item.strip()]

        return []

    def _generate_tailored_cv(
        self,
        master_cv: str,
        job_title: str,
        company_name: str,
        job_description: str,
        job_analysis: Dict[str, Any],
        field: str
    ) -> str:
        """
        Generate a tailored CV using Claude.

        Returns:
            Tailored CV in markdown format
        """
        print("   ✍️  Generating tailored CV...")

        # Build the optimization prompt
        prompt = f"""You are an expert CV writer specializing in helping candidates secure job offers.

Your task is to optimize this master CV to perfectly match the target job requirements.

# TARGET JOB
- **Position**: {job_title}
- **Company**: {company_name}
- **Field**: {field}

# JOB DESCRIPTION
{job_description[:3000]}

# JOB REQUIREMENTS ANALYSIS
{job_analysis['raw_analysis'][:1500]}

# MASTER CV (TO BE TAILORED)
{master_cv}

# OPTIMIZATION INSTRUCTIONS

Your goal is to create a tailored CV that maximizes the candidate's chances of getting an interview for THIS SPECIFIC JOB.

## What to do:

1. **Rewrite bullet points** to emphasize experiences that match the job requirements
2. **Incorporate priority keywords** naturally throughout the CV (from the job analysis)
3. **Highlight relevant skills** mentioned in the job description
4. **Quantify achievements** where possible (numbers, percentages, impact)
5. **Reorder sections** to put the most relevant experiences first
6. **Add a targeted summary** at the top that positions the candidate for THIS specific role
7. **Match the tone** to the company culture (startup vs corporate, formal vs casual)
8. **Ensure UK formatting** for dates, spelling, and conventions

## What NOT to do:

- Do NOT fabricate experiences, skills, or achievements
- Do NOT remove truthful information - only reframe/reorder it
- Do NOT make the CV longer than 2 pages worth of content
- Do NOT use generic phrases like "team player" or "hard worker"
- Do NOT copy-paste exact phrases from the job description verbatim (paraphrase naturally)
- Do NOT add placeholders or [brackets] - write complete, real content

## Output Format:

Return ONLY the tailored CV in clean markdown format. Start with a header, then include all sections (Summary, Experience, Skills, Education, etc.).

Make it compelling, specific, and impossible to ignore for THIS job.

Begin now:
"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.7,  # Slightly creative but still grounded
                messages=[{"role": "user", "content": prompt}]
            )

            tailored_cv = message.content[0].text.strip()

            # Add metadata footer
            footer = f"\n\n---\n*CV tailored for {job_title} at {company_name} on {datetime.now().strftime('%Y-%m-%d')}*"
            tailored_cv += footer

            print(f"   ✓ Generated {len(tailored_cv)} character CV")

            return tailored_cv

        except Exception as e:
            print(f"   ❌ CV generation failed: {e}")
            # Return original with a note
            return f"{master_cv}\n\n---\n*Note: Auto-tailoring failed. Manual review recommended.*"

    def batch_tailor_cvs(
        self,
        jobs: list,
        master_cvs: Dict[str, str]
    ) -> Dict[int, str]:
        """
        Tailor CVs for multiple jobs in batch.

        Args:
            jobs: List of job dictionaries (with id, title, company_name, description, field)
            master_cvs: Dictionary mapping field names to master CV markdown

        Returns:
            Dictionary mapping job_id to tailored CV markdown
        """
        results = {}

        print(f"\n🔄 Batch tailoring {len(jobs)} CVs...")

        for i, job in enumerate(jobs, 1):
            job_id = job['id']
            field = job['field']
            master_cv = master_cvs.get(field)

            if not master_cv:
                print(f"   [{i}/{len(jobs)}] ⚠️  No master CV found for field {field}")
                continue

            print(f"   [{i}/{len(jobs)}] Processing job {job_id}...")

            try:
                tailored_cv = self.tailor_cv(
                    master_cv_markdown=master_cv,
                    job_title=job['job_title'],
                    company_name=job['company_name'],
                    job_description=job['description'],
                    field=field
                )
                results[job_id] = tailored_cv

            except Exception as e:
                print(f"   ❌ Failed to tailor CV for job {job_id}: {e}")
                continue

        print(f"\n✅ Successfully tailored {len(results)}/{len(jobs)} CVs")
        return results


class CVQualityChecker:
    """Helper class to validate CV quality."""

    @staticmethod
    def check_cv_quality(cv_markdown: str, job_description: str) -> Dict[str, Any]:
        """
        Check if a tailored CV meets quality standards.

        Returns:
            Dictionary with quality metrics and suggestions
        """
        issues = []
        score = 100

        # Check length
        if len(cv_markdown) < 500:
            issues.append("CV is too short (< 500 characters)")
            score -= 30

        if len(cv_markdown) > 8000:
            issues.append("CV is too long (> 8000 characters, likely > 2 pages)")
            score -= 10

        # Check for placeholders
        placeholder_patterns = [r'\[.*?\]', r'TODO', r'PLACEHOLDER', r'XXX', r'<<<', r'>>>']
        for pattern in placeholder_patterns:
            if re.search(pattern, cv_markdown, re.IGNORECASE):
                issues.append(f"Contains placeholder text: {pattern}")
                score -= 20

        # Check for key sections
        required_sections = ['experience', 'skill', 'education']
        for section in required_sections:
            if section.lower() not in cv_markdown.lower():
                issues.append(f"Missing {section} section")
                score -= 15

        # Check for quantified achievements
        if not re.search(r'\d+%|\d+x|\d+\s*(users|customers|projects|team)', cv_markdown):
            issues.append("No quantified achievements found (consider adding numbers/metrics)")
            score -= 10

        return {
            'score': max(0, score),
            'passed': score >= 70,
            'issues': issues,
            'word_count': len(cv_markdown.split()),
            'char_count': len(cv_markdown)
        }
