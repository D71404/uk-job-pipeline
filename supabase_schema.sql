-- ============================================================
-- Lovable Job Scraper Integration Schema
-- ============================================================
-- Run this in your Supabase SQL Editor

-- 1. Create staging/review table (mirrors bd_job_intel structure)
-- Jobs land here first for human review before pushing to bd_job_intel

CREATE TABLE IF NOT EXISTS bd_job_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core job info (from scraper)
    job_title text NOT NULL,
    job_title_normalized text,
    company_name text,  -- Temporary until linked to company_id
    company_id uuid REFERENCES bd_companies(id),  -- NULL until approved
    company_linkedin_url text,
    job_url text,
    job_description_url text,
    full_job_description text,
    job_description_summary text,
    job_category text,
    job_subcategory text,
    location text,
    remote_type text,
    seniority_level text,
    department text,
    clearance_required text,
    salary_min numeric,
    salary_max numeric,
    equity_range text,
    bonus_target numeric,
    bonus_type text,
    skills_mentioned text[],
    nice_to_have_skills text[],
    required_experiences text[],
    years_experience_min integer,
    years_experience_max integer,
    travel_requirement text,
    team_size integer,
    is_leadership_role boolean DEFAULT false,

    -- Review workflow fields
    review_status text DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected', 'needs_info')),
    reviewed_by uuid REFERENCES auth.users(id),
    reviewed_at timestamptz,
    reviewer_notes text,

    -- Source tracking
    source_url text,  -- URL that was scraped
    source_type text DEFAULT 'firecrawl_scraper',
    scraped_at timestamptz DEFAULT NOW(),

    -- Raw scraped data (for debugging/reprocessing)
    raw_scraped_data jsonb,

    -- Metadata
    metadata jsonb,
    created_at timestamptz DEFAULT NOW(),
    updated_at timestamptz DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_job_reviews_status ON bd_job_reviews(review_status);
CREATE INDEX IF NOT EXISTS idx_job_reviews_company ON bd_job_reviews(company_name);
CREATE INDEX IF NOT EXISTS idx_job_reviews_created ON bd_job_reviews(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_reviews_source ON bd_job_reviews(source_url);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_job_reviews_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_job_reviews_updated_at ON bd_job_reviews;
CREATE TRIGGER trigger_job_reviews_updated_at
    BEFORE UPDATE ON bd_job_reviews
    FOR EACH ROW
    EXECUTE FUNCTION update_job_reviews_updated_at();

-- ============================================================
-- 2. Function to approve job and copy to bd_job_intel
-- ============================================================

CREATE OR REPLACE FUNCTION approve_job_to_intel(review_job_id uuid, reviewer_user_id uuid)
RETURNS uuid AS $$
DECLARE
    new_job_id uuid;
    review_record RECORD;
    company_uuid uuid;
BEGIN
    -- Get the review record
    SELECT * INTO review_record FROM bd_job_reviews WHERE id = review_job_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Review job not found: %', review_job_id;
    END IF;

    -- Try to find existing company by name
    SELECT id INTO company_uuid FROM bd_companies
    WHERE name ILIKE review_record.company_name
    LIMIT 1;

    -- Insert into bd_job_intel
    INSERT INTO bd_job_intel (
        job_title,
        job_title_normalized,
        company_id,
        company_linkedin_url,
        job_url,
        job_description_url,
        full_job_description,
        job_description_summary,
        job_category,
        job_subcategory,
        location,
        remote_type,
        seniority_level,
        department,
        clearance_required,
        salary_min,
        salary_max,
        equity_range,
        bonus_target,
        bonus_type,
        skills_mentioned,
        nice_to_have_skills,
        required_experiences,
        years_experience_min,
        years_experience_max,
        travel_requirement,
        team_size,
        is_leadership_role,
        is_active,
        first_seen_at,
        last_seen_at,
        scraped_at,
        source_type,
        data_sources,
        metadata
    ) VALUES (
        review_record.job_title,
        review_record.job_title_normalized,
        company_uuid,  -- May be NULL if company not found
        review_record.company_linkedin_url,
        review_record.job_url,
        review_record.job_description_url,
        review_record.full_job_description,
        review_record.job_description_summary,
        review_record.job_category,
        review_record.job_subcategory,
        review_record.location,
        review_record.remote_type,
        review_record.seniority_level,
        review_record.department,
        review_record.clearance_required,
        review_record.salary_min,
        review_record.salary_max,
        review_record.equity_range,
        review_record.bonus_target,
        review_record.bonus_type,
        review_record.skills_mentioned,
        review_record.nice_to_have_skills,
        review_record.required_experiences,
        review_record.years_experience_min,
        review_record.years_experience_max,
        review_record.travel_requirement,
        review_record.team_size,
        review_record.is_leadership_role,
        true,  -- is_active
        NOW(),
        NOW(),
        review_record.scraped_at,
        'firecrawl_scraper',  -- source_type
        ARRAY['firecrawl_scraper'],  -- data_sources
        review_record.metadata
    )
    RETURNING id INTO new_job_id;

    -- Update review record
    UPDATE bd_job_reviews SET
        review_status = 'approved',
        reviewed_by = reviewer_user_id,
        reviewed_at = NOW(),
        company_id = company_uuid
    WHERE id = review_job_id;

    RETURN new_job_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 3. Function to reject job
-- ============================================================

CREATE OR REPLACE FUNCTION reject_job_review(review_job_id uuid, reviewer_user_id uuid, notes text DEFAULT NULL)
RETURNS void AS $$
BEGIN
    UPDATE bd_job_reviews SET
        review_status = 'rejected',
        reviewed_by = reviewer_user_id,
        reviewed_at = NOW(),
        reviewer_notes = notes
    WHERE id = review_job_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 4. View for pending reviews (convenience for Lovable)
-- ============================================================

CREATE OR REPLACE VIEW pending_job_reviews AS
SELECT
    jr.*,
    c.name as matched_company_name
FROM bd_job_reviews jr
LEFT JOIN bd_companies c ON jr.company_id = c.id
WHERE jr.review_status = 'pending'
ORDER BY jr.created_at DESC;

-- ============================================================
-- 5. Row Level Security (RLS) - Optional but recommended
-- ============================================================

-- Enable RLS
ALTER TABLE bd_job_reviews ENABLE ROW LEVEL SECURITY;

-- Policy: Allow all authenticated users to view pending jobs
CREATE POLICY "Allow authenticated to view reviews"
ON bd_job_reviews FOR SELECT
TO authenticated
USING (true);

-- Policy: Allow authenticated users to insert (for the scraper)
CREATE POLICY "Allow authenticated to insert reviews"
ON bd_job_reviews FOR INSERT
TO authenticated
WITH CHECK (true);

-- Policy: Only allow updates to pending jobs
CREATE POLICY "Allow updates to pending reviews"
ON bd_job_reviews FOR UPDATE
TO authenticated
USING (review_status = 'pending')
WITH CHECK (true);

-- ============================================================
-- USAGE EXAMPLES:
-- ============================================================

-- Insert scraped jobs (done by Python scraper):
-- INSERT INTO bd_job_reviews (job_title, company_name, location, ...)
-- VALUES ('Senior Engineer', 'Acme Corp', 'Remote', ...);

-- Get pending reviews (for Lovable review page):
-- SELECT * FROM pending_job_reviews;

-- Approve a job (moves to bd_job_intel):
-- SELECT approve_job_to_intel('uuid-here', auth.uid());

-- Reject a job:
-- SELECT reject_job_review('uuid-here', auth.uid(), 'Duplicate listing');
