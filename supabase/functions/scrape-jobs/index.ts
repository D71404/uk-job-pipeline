// Supabase Edge Function: scrape-jobs
// Scrapes jobs from a URL using Firecrawl and saves to review queue

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface ScrapeRequest {
  url: string;
  company_name?: string;
  limit?: number;
}

// Career URL patterns
const CAREER_PATTERNS = [
  /\/careers?($|\/)/i,
  /\/jobs?($|\/)/i,
  /\/positions?($|\/)/i,
  /\/openings?($|\/)/i,
  /\/hiring($|\/)/i,
  /\/join-us/i,
  /\/work-with-us/i,
];

function isCareerUrl(url: string): boolean {
  return CAREER_PATTERNS.some((pattern) => pattern.test(url));
}

async function crawlWebsite(url: string, apiKey: string, limit: number = 50) {
  const response = await fetch("https://api.firecrawl.dev/v2/crawl", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      url,
      limit,
      scrapeOptions: {
        formats: ["markdown"],
        onlyMainContent: true,
      },
    }),
  });

  if (!response.ok) {
    throw new Error(`Crawl failed: ${response.statusText}`);
  }

  const data = await response.json();

  // Poll for completion
  let status = data.status;
  let result = data;

  while (status === "scraping" && result.id) {
    await new Promise((resolve) => setTimeout(resolve, 2000));

    const statusRes = await fetch(`https://api.firecrawl.dev/v2/crawl/${result.id}`, {
      headers: { "Authorization": `Bearer ${apiKey}` },
    });

    result = await statusRes.json();
    status = result.status;
  }

  return result.data || [];
}

async function extractJobs(urls: string[], apiKey: string) {
  const schema = {
    type: "object",
    properties: {
      jobs: {
        type: "array",
        items: {
          type: "object",
          properties: {
            title: { type: "string" },
            department: { type: "string" },
            location: { type: "string" },
            type: { type: "string" },
            description: { type: "string" },
            requirements: { type: "array", items: { type: "string" } },
            responsibilities: { type: "array", items: { type: "string" } },
            salary_range: { type: "string" },
            apply_url: { type: "string" },
            posted_date: { type: "string" },
          },
          required: ["title"],
        },
      },
    },
    required: ["jobs"],
  };

  const prompt = `
    Extract all job listings from these pages. For each job, capture:
    - Job title
    - Department/team
    - Location
    - Employment type
    - Full job description
    - Required qualifications/skills
    - Job responsibilities
    - Salary range (if mentioned)
    - Application link/URL
    - Posted date

    Return empty array if no job listings found.
  `;

  // Firecrawl beta limit: 10 URLs per request
  const batchSize = 10;
  const allJobs: any[] = [];

  for (let i = 0; i < urls.length; i += batchSize) {
    const batch = urls.slice(i, i + batchSize);

    const response = await fetch("https://api.firecrawl.dev/v2/extract", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        urls: batch,
        prompt,
        schema,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      const jobs = data.data?.jobs || [];
      allJobs.push(...jobs);
    }
  }

  return allJobs;
}

function parseSalary(salaryText: string): [number | null, number | null] {
  if (!salaryText) return [null, null];

  const pattern1 = /\$?(\d+)[kK]?\s*-\s*\$?(\d+)[kK]?/;
  const match1 = salaryText.match(pattern1);
  if (match1) {
    let min = parseInt(match1[1]);
    let max = parseInt(match1[2]);
    if (salaryText.toLowerCase().includes("k")) {
      min *= 1000;
      max *= 1000;
    }
    return [min, max];
  }

  const pattern2 = /\$?(\d+)[kK]?/g;
  const matches = [...salaryText.matchAll(pattern2)];
  if (matches.length > 0) {
    const nums = matches.map((m) => {
      const n = parseInt(m[1]);
      return salaryText.toLowerCase().includes("k") ? n * 1000 : n;
    });
    return [Math.min(...nums), Math.max(...nums)];
  }

  return [null, null];
}

function detectRemoteType(location: string, description: string): string {
  const text = `${location} ${description}`.toLowerCase();
  if (text.includes("remote") || text.includes("work from home") || text.includes("wfh")) {
    return "Remote";
  } else if (text.includes("hybrid")) {
    return "Hybrid";
  }
  return "On-site";
}

function detectSeniority(title: string, description: string): string {
  const text = `${title} ${description}`.toLowerCase();
  if (/\b(principal|staff|distinguished|fellow)\b/.test(text)) {
    return "Principal/Staff";
  } else if (/\b(senior|sr\.|lead|staff)\b/.test(text)) {
    return "Senior";
  } else if (/\b(manager|director|head of)\b/.test(text)) {
    return "Manager";
  } else if (/\b(junior|jr\.|entry|associate|intern)\b/.test(text)) {
    return "Junior";
  }
  return "Mid-level";
}

function detectCategory(title: string, department: string): [string, string] {
  const text = `${title} ${department}`.toLowerCase();

  if (/\b(engineer|developer|devops|sre|architect)\b/.test(text)) {
    return ["Engineering", text.includes("frontend") ? "swe_frontend" :
            text.includes("backend") ? "swe_backend" :
            text.includes("full") ? "swe_fullstack" : "swe"];
  } else if (/\b(data scientist|data engineer|data analyst|ml engineer)\b/.test(text)) {
    return ["Data", "data_scientist"];
  } else if (/\b(product manager|product owner)\b/.test(text)) {
    return ["Product", "product_manager"];
  } else if (/\b(designer|ux|ui)\b/.test(text)) {
    return ["Design", "designer"];
  } else if (/\b(marketing|growth|seo|content)\b/.test(text)) {
    return ["Marketing", "marketing"];
  } else if (/\b(sales|account executive|sdr)\b/.test(text)) {
    return ["Sales", "sales"];
  }

  return ["Other", "other"];
}

function mapScrapedJob(scraped: any, companyName: string, sourceUrl: string): any {
  const title = scraped.title || "";
  const description = scraped.description || "";
  const requirements = Array.isArray(scraped.requirements) ? scraped.requirements.join("\n") : "";
  const location = scraped.location || "";

  const [salaryMin, salaryMax] = parseSalary(scraped.salary_range || "");
  const remoteType = detectRemoteType(location, description);
  const seniority = detectSeniority(title, description);
  const [category, subcategory] = detectCategory(title, scraped.department || "");

  const summary = `${title} at ${companyName || "Company"}. ` +
    `${location ? `Located in ${location}. ` : ""}` +
    `${remoteType} position.`;

  return {
    job_title: title,
    job_title_normalized: subcategory,
    company_name: companyName,
    job_url: scraped.apply_url || "",
    job_description_url: sourceUrl,
    full_job_description: description,
    job_description_summary: summary,
    job_category: category,
    job_subcategory: subcategory,
    location: location,
    remote_type: remoteType,
    seniority_level: seniority,
    department: scraped.department || "",
    salary_min: salaryMin,
    salary_max: salaryMax,
    skills_mentioned: [],
    required_experiences: [],
    is_leadership_role: /\b(lead|manager|director|head|principal|staff)\b/i.test(title),
    source_url: sourceUrl,
    source_type: "firecrawl_scraper",
    scraped_at: new Date().toISOString(),
    raw_scraped_data: scraped,
    review_status: "pending",
  };
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { url, company_name, limit = 50 }: ScrapeRequest = await req.json();

    if (!url) {
      return new Response(
        JSON.stringify({ error: "URL is required" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Get secrets
    const firecrawlKey = Deno.env.get("FIRECRAWL_API_KEY");
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

    if (!firecrawlKey || !supabaseUrl || !supabaseKey) {
      return new Response(
        JSON.stringify({ error: "Missing environment variables" }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Create Supabase client
    const supabase = createClient(supabaseUrl, supabaseKey);

    console.log(`🔍 Crawling ${url}...`);

    // Crawl website
    const pages = await crawlWebsite(url, firecrawlKey, limit);
    console.log(`✅ Crawled ${pages.length} pages`);

    // Filter career URLs
    const careerUrls = pages
      .map((p: any) => p.metadata?.sourceURL || p.metadata?.url)
      .filter((u: string) => u && isCareerUrl(u));

    const uniqueUrls = [...new Set(careerUrls)];
    console.log(`🎯 Found ${uniqueUrls.length} career URLs`);

    if (uniqueUrls.length === 0) {
      return new Response(
        JSON.stringify({ success: true, jobs_found: 0, message: "No career pages found" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Extract jobs
    console.log(`🤖 Extracting jobs from ${uniqueUrls.length} pages...`);
    const jobs = await extractJobs(uniqueUrls.slice(0, 20), firecrawlKey); // Limit to 20 URLs
    console.log(`✅ Found ${jobs.length} jobs`);

    if (jobs.length === 0) {
      return new Response(
        JSON.stringify({ success: true, jobs_found: 0, message: "No jobs extracted" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Map and insert jobs
    const mappedJobs = jobs.map((j) => mapScrapedJob(j, company_name || "", url));

    const { data: inserted, error } = await supabase
      .from("bd_job_reviews")
      .insert(mappedJobs)
      .select("id");

    if (error) {
      throw error;
    }

    console.log(`💾 Saved ${inserted?.length || 0} jobs to review queue`);

    return new Response(
      JSON.stringify({
        success: true,
        message: `Found ${jobs.length} jobs. Saved to review queue.`,
        jobs_found: jobs.length,
        review_ids: inserted?.map((d) => d.id) || [],
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (error) {
    console.error("Error:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
