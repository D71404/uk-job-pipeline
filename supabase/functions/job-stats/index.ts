// Get job review queue statistics
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Get counts by status
    const { data: pending } = await supabase
      .from("bd_job_reviews")
      .select("id", { count: "exact", head: true })
      .eq("review_status", "pending");

    const { data: approved } = await supabase
      .from("bd_job_reviews")
      .select("id", { count: "exact", head: true })
      .eq("review_status", "approved");

    const { data: rejected } = await supabase
      .from("bd_job_reviews")
      .select("id", { count: "exact", head: true })
      .eq("review_status", "rejected");

    const stats = {
      pending: pending?.length || 0,
      approved: approved?.length || 0,
      rejected: rejected?.length || 0,
    };

    return new Response(
      JSON.stringify(stats),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
