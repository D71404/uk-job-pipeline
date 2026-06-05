#!/usr/bin/env python3
"""
Master CV Upload Utility

Upload or update master CVs for each job field.
Master CVs are used as templates for AI tailoring.

Usage:
    python3 upload_master_cv.py AI_ENGINEER path/to/cv.md
    python3 upload_master_cv.py --field MARKETING --file marketing_cv.md
    python3 upload_master_cv.py --list  # List all master CVs
"""

import argparse
import sys
from pathlib import Path
from job_pipeline_client import JobPipelineClient


def upload_cv(field: str, cv_file_path: str):
    """Upload or update a master CV."""

    # Validate field
    valid_fields = ['AI_ENGINEER', 'TEACHING', 'PHD', 'MARKETING']
    if field not in valid_fields:
        print(f"❌ Invalid field. Must be one of: {', '.join(valid_fields)}")
        return False

    # Read CV file
    cv_path = Path(cv_file_path)
    if not cv_path.exists():
        print(f"❌ File not found: {cv_file_path}")
        return False

    print(f"📄 Reading CV from: {cv_file_path}")
    cv_content = cv_path.read_text()

    if not cv_content.strip():
        print("❌ CV file is empty")
        return False

    print(f"   ✓ Loaded {len(cv_content)} characters")

    # Upload to database
    print(f"☁️  Uploading to Supabase for field: {field}")

    try:
        db = JobPipelineClient()
        success = db.upsert_master_cv(field, cv_content)

        if success:
            print(f"✅ Master CV uploaded successfully for {field}")
            print(f"   This CV will be used to tailor applications for {field} jobs")
            return True
        else:
            print("❌ Upload failed")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def list_master_cvs():
    """List all master CVs in the database."""
    print("\n📋 Master CVs in Database")
    print("=" * 60)

    try:
        db = JobPipelineClient()

        fields = ['AI_ENGINEER', 'TEACHING', 'PHD', 'MARKETING']

        for field in fields:
            cv = db.get_master_cv(field)

            if cv:
                word_count = len(cv.split())
                char_count = len(cv)
                print(f"✓ {field:15} - {word_count:4} words, {char_count:5} chars")
            else:
                print(f"✗ {field:15} - NOT FOUND")

        print("=" * 60)
        print("\nTo upload a master CV:")
        print("  python3 upload_master_cv.py AI_ENGINEER path/to/cv.md")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")


def create_template_cv(field: str, output_path: str):
    """Create a template CV file."""

    template = f"""# Your Name

**Email:** your.email@example.com | **Phone:** +44 XXXX XXXXXX | **Location:** London, UK
**LinkedIn:** linkedin.com/in/yourname | **GitHub:** github.com/yourname

---

## Professional Summary

[Write a compelling 2-3 sentence summary highlighting your expertise in {field.lower().replace('_', ' ')} and key achievements. Focus on what makes you unique and valuable to employers.]

---

## Experience

### Job Title | Company Name
**Location** | *Start Date - End Date*

- Achievement-focused bullet point with quantifiable results (e.g., "Increased efficiency by 40%")
- Another accomplishment demonstrating impact and skills relevant to {field.lower().replace('_', ' ')}
- Technical project or responsibility showcasing expertise
- Leadership or collaboration example

### Previous Job Title | Company Name
**Location** | *Start Date - End Date*

- Key achievement with measurable impact
- Relevant technical skill or project
- Problem-solving example with positive outcome

---

## Skills

**Technical Skills:**
- [List relevant technical skills for {field}]
- Programming languages, frameworks, tools
- Methodologies and best practices

**Soft Skills:**
- Communication, leadership, problem-solving
- Project management, collaboration

---

## Education

### Degree Title
**University Name** | *Graduation Year*
- Relevant coursework, honors, or distinctions
- GPA (if strong), thesis topic (if relevant)

---

## Certifications & Awards

- Certification Name | Issuing Organization | Year
- Award or Achievement | Year

---

## Projects (Optional)

### Project Name
- Brief description of the project and your role
- Technologies used and outcomes achieved
- Link to demo/repository if applicable

---

*CV Template for {field} - Customize with your actual experience and achievements*
"""

    output_file = Path(output_path)
    output_file.write_text(template)
    print(f"✅ Template CV created: {output_path}")
    print(f"   Edit this file with your real information, then upload:")
    print(f"   python3 upload_master_cv.py {field} {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Upload master CVs for job pipeline'
    )

    # Positional arguments (simple usage)
    parser.add_argument(
        'field',
        nargs='?',
        choices=['AI_ENGINEER', 'TEACHING', 'PHD', 'MARKETING'],
        help='Job field for this CV'
    )
    parser.add_argument(
        'file',
        nargs='?',
        help='Path to CV file (markdown format)'
    )

    # Named arguments (alternative usage)
    parser.add_argument(
        '--field',
        dest='field_named',
        choices=['AI_ENGINEER', 'TEACHING', 'PHD', 'MARKETING'],
        help='Job field for this CV'
    )
    parser.add_argument(
        '--file',
        dest='file_named',
        help='Path to CV file (markdown format)'
    )

    # Actions
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all master CVs in database'
    )
    parser.add_argument(
        '--template',
        metavar='OUTPUT_FILE',
        help='Create a template CV file'
    )

    args = parser.parse_args()

    # List mode
    if args.list:
        list_master_cvs()
        return

    # Template mode
    if args.template:
        if args.field or args.field_named:
            field = args.field or args.field_named
            create_template_cv(field, args.template)
        else:
            print("❌ Please specify --field when using --template")
            print("   Example: python3 upload_master_cv.py --field AI_ENGINEER --template my_cv.md")
        return

    # Upload mode
    field = args.field or args.field_named
    file_path = args.file or args.file_named

    if not field or not file_path:
        parser.print_help()
        print("\n" + "=" * 60)
        print("Quick Start:")
        print("=" * 60)
        print("1. Create a template:")
        print("   python3 upload_master_cv.py --field AI_ENGINEER --template ai_cv.md")
        print()
        print("2. Edit the template with your real information")
        print()
        print("3. Upload to database:")
        print("   python3 upload_master_cv.py AI_ENGINEER ai_cv.md")
        print()
        print("4. Check what's uploaded:")
        print("   python3 upload_master_cv.py --list")
        print("=" * 60)
        return

    success = upload_cv(field, file_path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
