from dotenv import load_dotenv
import os

load_dotenv()

# ── Google ──
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is not set.")

# ── Nevermined (seller) ──
NVM_API_KEY      = os.getenv("NVM_API_KEY", "")
NVM_ENVIRONMENT  = os.getenv("NVM_ENVIRONMENT", "sandbox")
NVM_PLAN_ID      = os.getenv("NVM_PLAN_ID", "")
NVM_AGENT_ID     = os.getenv("NVM_AGENT_ID", "")

# ── Vendors (buyer targets) ──
WEBSITE_GUY_PLAN_ID   = os.getenv("WEBSITE_GUY_PLAN_ID", "")
WEBSITE_GUY_URL       = os.getenv("WEBSITE_GUY_URL", "")

CREATIVE_LADY_PLAN_ID = os.getenv("CREATIVE_LADY_PLAN_ID", "")
CREATIVE_LADY_URL     = os.getenv("CREATIVE_LADY_URL", "")

EXA_PLAN_ID           = os.getenv("EXA_PLAN_ID", "")
EXA_URL               = os.getenv("EXA_URL", "")

ZEROCLICK_PLAN_ID     = os.getenv("ZEROCLICK_PLAN_ID", "")
ZEROCLICK_URL         = os.getenv("ZEROCLICK_URL", "")
