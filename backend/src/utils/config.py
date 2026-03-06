from dotenv import load_dotenv
from pathlib import Path
import os

# Walk up: config.py → utils/ → src/ → backend/ → find .env
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ── Google ──
GOOGLE_API_KEY = (os.getenv("GOOGLE_API_KEY") or "").strip()

# ── Nevermined (seller) ──
NVM_API_KEY      = (os.getenv("NVM_API_KEY", "") or "").strip()
NVM_ENVIRONMENT  = (os.getenv("NVM_ENVIRONMENT", "sandbox") or "sandbox").strip()
NVM_PLAN_ID      = (os.getenv("NVM_PLAN_ID", "") or "").strip()
NVM_AGENT_ID     = (os.getenv("NVM_AGENT_ID", "") or "").strip()

# ── Vendors (buyer targets) ──
WEBSITE_GUY_PLAN_ID   = (os.getenv("WEBSITE_GUY_PLAN_ID", "") or "").strip()
WEBSITE_GUY_URL       = (os.getenv("WEBSITE_GUY_URL", "") or "").strip()

CREATIVE_LADY_PLAN_ID = (os.getenv("CREATIVE_LADY_PLAN_ID", "") or "").strip()
CREATIVE_LADY_URL     = (os.getenv("CREATIVE_LADY_URL", "") or "").strip()

EXA_PLAN_ID           = (os.getenv("EXA_PLAN_ID", "") or "").strip()
EXA_URL               = (os.getenv("EXA_URL", "") or "").strip()

ZEROCLICK_PLAN_ID     = (os.getenv("ZEROCLICK_PLAN_ID", "") or "").strip()
ZEROCLICK_URL         = (os.getenv("ZEROCLICK_URL", "") or "").strip()

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
