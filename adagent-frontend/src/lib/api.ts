export type CampaignBrief = {
  brand: string;
  goal: string;
  audience: string;
  budget: number;
};

export type CampaignApiResponse = Record<string, unknown>;

type ApiError = Error & { status?: number };

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ||
  (import.meta.env.DEV ? "http://localhost:8000" : "/api");

const PAYMENT_SIGNATURE =
  (import.meta.env.VITE_X402_PAYMENT_SIGNATURE as string | undefined)?.trim() || "";

async function postJson(endpoint: string, payload: CampaignBrief): Promise<CampaignApiResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (PAYMENT_SIGNATURE) {
    headers["payment-signature"] = PAYMENT_SIGNATURE;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers,
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
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as CampaignApiResponse;
}

export async function runMindraCampaign(brief: CampaignBrief): Promise<CampaignApiResponse> {
  return postJson("/mindra/run", brief);
}

export async function runCampaign(brief: CampaignBrief): Promise<CampaignApiResponse> {
  try {
    return await runMindraCampaign(brief);
  } catch (error) {
    const apiError = error as ApiError;
    if (apiError.status !== 402 && apiError.status !== 404 && apiError.status !== 500) {
      throw error;
    }
  }

  try {
    return await postJson("/workflow/preview", brief);
  } catch {
    return postJson("/createblueprint", brief);
  }
}
