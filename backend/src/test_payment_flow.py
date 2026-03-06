"""
Full Nevermined buy/sell transaction test.

SELL side: client orders AdAgent Studio's plan → generates x402 token → calls /run-campaign
BUY side:  AdAgent Studio generates token for Creative Lady → calls their endpoint
"""

import os
import requests
from dotenv import load_dotenv

try:
    from payments_py import Payments, PaymentOptions
except Exception:
    if __name__ == "__main__":
        raise SystemExit("payments_py is not installed. Install deps before running this script.")
    import pytest
    pytest.skip("payments_py is not installed; skipping integration script.", allow_module_level=True)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

# ── Config ──────────────────────────────────────────────────────────────────
NVM_API_KEY = (os.getenv("NVM_API_KEY") or "").strip()
NVM_ENVIRONMENT = (os.getenv("NVM_ENVIRONMENT", "sandbox") or "sandbox").strip()
OUR_PLAN_ID = (os.getenv("NVM_PLAN_ID") or "").strip()
OUR_AGENT_ID = (os.getenv("NVM_AGENT_ID") or "").strip()
CREATIVE_LADY_PLAN = (os.getenv("CREATIVE_LADY_PLAN_ID") or "").strip()
CREATIVE_LADY_URL = (os.getenv("CREATIVE_LADY_URL") or "").strip()
OUR_ENDPOINT = (os.getenv("OUR_ENDPOINT") or "https://adagent-studio-seven.vercel.app/api/run-campaign").strip()

if not NVM_API_KEY or not OUR_PLAN_ID:
    raise SystemExit("Missing NVM_API_KEY or NVM_PLAN_ID in backend/.env")

p = Payments.get_instance(PaymentOptions(nvm_api_key=NVM_API_KEY, environment=NVM_ENVIRONMENT))

# ════════════════════════════════════════════════════════════════════════════
# SELL SIDE — simulate a client paying us
# ════════════════════════════════════════════════════════════════════════════
print("\n── SELL SIDE ──────────────────────────────────────────────")

# Step 1: Order our own plan (subscribe) — in real life the CLIENT does this
print("1. Ordering AdAgent Studio plan...")
order = p.plans.order_plan(plan_id=OUR_PLAN_ID)
print(f"   Order result: {order}")

# Step 2: Generate an x402 access token for our plan
print("2. Generating x402 token for our plan...")
token_result = p.x402.get_x402_access_token(
    plan_id=OUR_PLAN_ID,
    agent_id=OUR_AGENT_ID or None,
    redemption_limit=1
)
our_token = token_result.get("accessToken", "")
print(f"   Token (first 60 chars): {our_token[:60]}...")

# Step 3: Call our own /run-campaign endpoint with the token
print("3. Calling /run-campaign with payment token...")
resp = requests.post(
    OUR_ENDPOINT,
    json={"brand": "TestBrand", "goal": "drive signups", "audience": "founders", "budget": 15},
    headers={"payment-signature": our_token, "Content-Type": "application/json"},
    timeout=60,
)
print(f"   Status: {resp.status_code}")
print(f"   Response: {resp.json()}")

# ════════════════════════════════════════════════════════════════════════════
# BUY SIDE — pay Creative Lady
# ════════════════════════════════════════════════════════════════════════════
print("\n── BUY SIDE ───────────────────────────────────────────────")

# Step 4: Order Creative Lady's plan (subscribe to their service)
if CREATIVE_LADY_PLAN and CREATIVE_LADY_URL:
    print("4. Ordering Creative Lady plan...")
    cl_order = p.plans.order_plan(plan_id=CREATIVE_LADY_PLAN)
    print(f"   Order result: {cl_order}")

    # Step 5: Generate token for Creative Lady
    print("5. Generating x402 token for Creative Lady...")
    cl_token_result = p.x402.get_x402_access_token(plan_id=CREATIVE_LADY_PLAN, redemption_limit=1)
    cl_token = cl_token_result.get("accessToken", "")
    print(f"   Token (first 60 chars): {cl_token[:60]}...")

    # Step 6: Call Creative Lady's endpoint
    print("6. Calling Creative Lady's endpoint with payment token...")
    cl_resp = requests.post(
        CREATIVE_LADY_URL,
        json={"brief": "Create ad creatives for TestBrand targeting founders"},
        headers={"payment-signature": cl_token, "Content-Type": "application/json"},
        timeout=30,
    )
    print(f"   Status: {cl_resp.status_code}")
    try:
        print(f"   Response: {cl_resp.json()}")
    except Exception:
        print(f"   Response text: {cl_resp.text[:200]}")
else:
    print("4-6. Skipping vendor buy-side test (CREATIVE_LADY_PLAN_ID / CREATIVE_LADY_URL not set).")

print("\n── DONE ───────────────────────────────────────────────────")
