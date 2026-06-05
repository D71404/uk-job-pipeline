// Approve job review and move to bd_job_intel
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface ApproveRequest {
  review_id: string;
  reviewer_user_id: string;
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { review_id, reviewer_user_id }: ApproveRequest = await req.json();

    if (!review_id || !reviewer_user_id) {
      return new Response(
        JSON.stringify({ error: "review_id and reviewer_user_id required" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Call the database function to approve
    const { data, error } = await supabase.rpc("approve_job_to_intel", {
      review_job_id: review_id,
      reviewer_user_id: reviewer_user_id,
    });

    if (error) throw error;

    return new Response(
      JSON.stringify({ success: true, job_id: data }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
