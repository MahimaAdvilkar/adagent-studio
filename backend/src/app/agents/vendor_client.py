"""
Vendor client for AdAgent Studio.

Each method calls one external vendor agent with an x402 payment token.
All vendor plan IDs and URLs come from .env — swap in real values at the hackathon.
"""

from utils.payments import call_vendor, _mock_vendor_response
from utils.config import (
    DEV_MODE,
    WEBSITE_GUY_PLAN_ID, WEBSITE_GUY_URL,
    CREATIVE_LADY_PLAN_ID, CREATIVE_LADY_URL,
    EXA_PLAN_ID, EXA_URL,
    ZEROCLICK_PLAN_ID, ZEROCLICK_URL,
)


class VendorClient:

    # ── Website Guy ($3) ──────────────────────────────────────────────────────

    @staticmethod
    def build_landing_page(brief: dict) -> dict:
        """
        Ask Website Guy to build a landing page for the campaign.
        Input: campaign brief (brand, goal, audience, messaging)
        Output: { landing_page_url, sections, status }
        """
        if not WEBSITE_GUY_URL:
            if DEV_MODE:
                return _mock_vendor_response("website")
            return {"status": "skipped", "reason": "WEBSITE_GUY_URL not configured"}

        payload = {
            "client": brief.get("brand"),
            "goal": brief.get("goal"),
            "audience": brief.get("audience"),
            "messaging": brief.get("messaging", []),
            "deadline": "2 hours",
        }
        return call_vendor(WEBSITE_GUY_URL, WEBSITE_GUY_PLAN_ID, payload)

    # ── Creative Lady ($2) ────────────────────────────────────────────────────

    @staticmethod
    def create_ad_creatives(brief: dict) -> dict:
        """
        Ask Creative Lady to produce ad creatives and copy.
        Input: campaign brief
        Output: { creatives: [ { headline, body, cta, format } ] }
        """
        if not CREATIVE_LADY_URL:
            if DEV_MODE:
                return _mock_vendor_response("creative")
            return {"status": "skipped", "reason": "CREATIVE_LADY_URL not configured"}

        payload = {
            "brand": brief.get("brand"),
            "audience": brief.get("audience"),
            "messaging": brief.get("messaging", []),
            "formats": ["banner ad", "native ad", "headline"],
            "variations": 3,
        }
        return call_vendor(CREATIVE_LADY_URL, CREATIVE_LADY_PLAN_ID, payload)

    # ── Exa ($0.50) ───────────────────────────────────────────────────────────

    @staticmethod
    def research_audience(brief: dict) -> dict:
        """
        Ask Exa for market research on the target audience.
        Input: campaign brief
        Output: { insights, competitors, messaging_angles }
        """
        if not EXA_URL:
            if DEV_MODE:
                return _mock_vendor_response("research")
            return {"status": "skipped", "reason": "EXA_URL not configured"}

        payload = {
            "query": (
                f"Who is the target audience for '{brief.get('brand')}'? "
                f"Audience: {brief.get('audience')}. "
                f"Goal: {brief.get('goal')}."
            )
        }
        return call_vendor(EXA_URL, EXA_PLAN_ID, payload)

    # ── ZeroClick ($2) ────────────────────────────────────────────────────────

    @staticmethod
    def place_ads(brief: dict) -> dict:
        """
        Send creatives to ZeroClick for ad placement + A/B testing.
        The brief should contain upstream creative outputs merged in.
        Output: { campaign_id, impressions, clicks, status }
        """
        if not ZEROCLICK_URL:
            if DEV_MODE:
                return _mock_vendor_response("ads")
            return {"status": "skipped", "reason": "ZEROCLICK_URL not configured"}

        payload = {
            "brand": brief.get("brand"),
            "goal": brief.get("goal"),
            "audience": brief.get("audience"),
            "creatives": brief.get("creatives", []),
            "budget": brief.get("budget", 15),
        }
        return call_vendor(ZEROCLICK_URL, ZEROCLICK_PLAN_ID, payload)
