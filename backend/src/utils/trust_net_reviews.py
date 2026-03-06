"""Free Trust Net reviews API helpers (no x402 token required)."""

import httpx

from utils.config import TRUST_NET_BASE_URL


class TrustNetReviewApiError(Exception):
    """Represents an upstream Trust Net API failure."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


async def submit_free_review(payload: dict) -> dict:
    """Submit a community review via Trust Net free REST API."""
    url = f"{TRUST_NET_BASE_URL}/api/reviews"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise TrustNetReviewApiError(502, f"Trust Net request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text.strip() or "Unknown Trust Net API error"
        raise TrustNetReviewApiError(response.status_code, detail)

    return response.json()


async def get_free_reviews(agent_id: str) -> dict:
    """Fetch free community reviews for a given agent_id."""
    url = f"{TRUST_NET_BASE_URL}/api/reviews"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params={"agent_id": agent_id})
    except httpx.HTTPError as exc:
        raise TrustNetReviewApiError(502, f"Trust Net request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text.strip() or "Unknown Trust Net API error"
        raise TrustNetReviewApiError(response.status_code, detail)

    return response.json()
