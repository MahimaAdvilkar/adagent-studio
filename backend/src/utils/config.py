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
NVM_PLAN_ID_2    = (os.getenv("NVM_PLAN_ID_2", "") or "").strip()
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

# -- Mindra orchestration provider --
# local: existing internal graph flow
# api: call external Mindra endpoint
# Default is 'api' to avoid accidental fallback to local behavior.
MINDRA_PROVIDER = (os.getenv("MINDRA_PROVIDER", "api") or "api").strip().lower()
MINDRA_API_URL = (os.getenv("MINDRA_API_URL", "") or "").strip()
MINDRA_API_KEY = (os.getenv("MINDRA_API_KEY", "") or "").strip()
MINDRA_WORKFLOW_SLUG = (os.getenv("MINDRA_WORKFLOW_SLUG", "") or "").strip()
MINDRA_TWITTER_API_URL = (os.getenv("MINDRA_TWITTER_API_URL", "") or "").strip()
MINDRA_TWITTER_WORKFLOW_SLUG = (os.getenv("MINDRA_TWITTER_WORKFLOW_SLUG", "") or "").strip()
MINDRA_TIMEOUT_SECONDS = float((os.getenv("MINDRA_TIMEOUT_SECONDS", "180") or "180").strip())
MINDRA_CHILD_NODE_ENABLED = (os.getenv("MINDRA_CHILD_NODE_ENABLED", "true") or "true").strip().lower() == "true"
MINDRA_STREAM_WAIT_SECONDS = float((os.getenv("MINDRA_STREAM_WAIT_SECONDS", "90") or "90").strip())
MINDRA_TWITTER_AGENT_ENABLED = (os.getenv("MINDRA_TWITTER_AGENT_ENABLED", "true") or "true").strip().lower() == "true"

# -- Trust Net --
TRUST_NET_BASE_URL = (
	os.getenv("TRUST_NET_BASE_URL", "https://trust-net-mcp.rikenshah-02.workers.dev")
	or "https://trust-net-mcp.rikenshah-02.workers.dev"
).strip().rstrip("/")
