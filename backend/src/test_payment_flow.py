"""
Full Nevermined buy/sell transaction test.

SELL side: client orders AdAgent Studio's plan → generates x402 token → calls /run-campaign
BUY side:  AdAgent Studio generates token for Creative Lady → calls their endpoint
"""

import requests
from payments_py import Payments, PaymentOptions

# ── Config ──────────────────────────────────────────────────────────────────
NVM_API_KEY = "nvm-key:eyJhbGciOiJFUzI1NksifQ.eyJpc3MiOiIweDZCMTZEMGIzMzQ4MjQ1ODFCNGEyNEE0OUZkN2ZjYkQ2NTA5Q0U1ZGEiLCJzdWIiOiIweEUwNTU4MTZENTQxNDA1YmY1NzdFOGFEMjZFMjE1M0U1ZjU2MkU5RjYiLCJqdGkiOiIweDA3NjQzOTRmMTI4MDFlMzkwZWY1MWFkMmY3MjUyNDAyYmRjMWIxOWQ1YTkwNmJkMGJiYWUyOTA5NWY2MjJmZTIiLCJleHAiOjQ5Mjg1MTQzNjMsIm8xMXkiOiJzay1oZWxpY29uZS10cW5vNjRxLXl4NmVxcnEtdHBqeXJpcS1ybHY3aHVpIn0.hCDG6u6zeZ98w5oWbwTKRjcgkWIcnDjrvZUmLuCF1AkZx0ps58UXzREKNcNPjTEMYe1rqCOoyQGfVeWfuR9Zlhs"

OUR_PLAN_ID        = "43955667645714568092057142565359274237259428265532767327265493246604990476175"
CREATIVE_LADY_PLAN = "9661082042009636068072391467054896427087238025772062250717418964278633341785"
CREATIVE_LADY_URL  = "https://beneficial-essence-production-99c7.up.railway.app/mcp"
OUR_ENDPOINT       = "https://adagent-studio-seven.vercel.app/run-campaign"

p = Payments.get_instance(PaymentOptions(nvm_api_key=NVM_API_KEY, environment="sandbox"))

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
token_result = p.x402.get_x402_access_token(plan_id=OUR_PLAN_ID, redemption_limit=1)
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

print("\n── DONE ───────────────────────────────────────────────────")
