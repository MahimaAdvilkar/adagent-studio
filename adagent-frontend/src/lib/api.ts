export type CampaignBrief = {
  brand: string;
  goal: string;
  audience: string;
  budget: number;
};

export type CampaignApiResponse = Record<string, unknown>;

type ApiError = Error & { status?: number };

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000";

async function postJson(endpoint: string, payload: CampaignBrief): Promise<CampaignApiResponse> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = "";
    try {
      const err = await response.json();
      detail = typeof err?.detail === "string" ? err.detail : JSON.stringify(err);
    } catch {
      detail = await response.text();
    }
    const error = new Error(detail || `Request failed with status ${response.status}`) as ApiError;
    error.status = response.status;
    throw error;
  }

  return (await response.json()) as CampaignApiResponse;
}

export async function runCampaign(brief: CampaignBrief): Promise<CampaignApiResponse> {
  try {
    return await postJson("/run-campaign", brief);
  } catch (error) {
    const apiError = error as ApiError;
    if (apiError.status !== 404) {
      throw error;
    }
  }

  return postJson("/createblueprint", brief);
}
