"""
Minimal buyer client for AdAgent Studio.

Generates an x402 token from Nevermined and calls the paid endpoint:
POST /api/run-campaign
"""

import os
import time
from pathlib import Path
import requests
from dotenv import load_dotenv
from payments_py import Payments, PaymentOptions
from payments_py.x402.types import X402PaymentRequired, X402Scheme, X402Resource, X402SchemeExtra


def main() -> None:
    # Load env from common project locations (backend/.env, root .ENV, root .env).
    src_dir = Path(__file__).resolve().parent
    backend_dir = src_dir.parent
    repo_dir = backend_dir.parent
    # Load root env files first, then backend/.env last so backend values win.
    for env_path in [repo_dir / ".ENV", repo_dir / ".env", backend_dir / ".env"]:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)

    nvm_api_key = (os.getenv("NVM_BUYER_API_KEY") or os.getenv("NVM_API_KEY") or "").strip()
    nvm_environment = (os.getenv("NVM_ENVIRONMENT", "sandbox") or "sandbox").strip()
    nvm_plan_id = (os.getenv("NVM_PLAN_ID") or "").strip()
    nvm_agent_id = (os.getenv("NVM_AGENT_ID") or "").strip()
    endpoint = (os.getenv("OUR_ENDPOINT") or "https://adagent-studio-seven.vercel.app/api/run-campaign").strip()

    if not nvm_api_key or not nvm_plan_id:
        raise SystemExit("Missing NVM_API_KEY or NVM_PLAN_ID in backend/.env")

    p = Payments.get_instance(
        PaymentOptions(
            nvm_api_key=nvm_api_key,
            environment=nvm_environment,
        )
    )

    # Optional: subscribe buyer to the seller plan before token generation.
    # Default is OFF because sandbox order API can hang/fail intermittently.
    order_first = (os.getenv("ORDER_PLAN_FIRST", "false") or "false").strip().lower() == "true"
    if order_first:
        try:
            p.plans.order_plan(plan_id=nvm_plan_id)
        except Exception as e:
            print("order_plan warning:", e)
            print("continuing with token generation...")

    def _extract_agent_id(plan_info) -> str:
        if isinstance(plan_info, dict):
            return (
                str(plan_info.get("agentId") or plan_info.get("agent_id") or "").strip()
                or str((plan_info.get("agent") or {}).get("id") or "").strip()
            )

        agent_id = getattr(plan_info, "agentId", None) or getattr(plan_info, "agent_id", None)
        if agent_id:
            return str(agent_id).strip()

        agent_obj = getattr(plan_info, "agent", None)
        if agent_obj:
            nested = getattr(agent_obj, "id", None)
            if nested:
                return str(nested).strip()
        return ""

    # If agent_id not set, try to infer it from the plan.
    if not nvm_agent_id:
        try:
            plan_info = p.plans.get_plan(plan_id=nvm_plan_id)
            inferred_agent_id = _extract_agent_id(plan_info)
            if inferred_agent_id:
                nvm_agent_id = inferred_agent_id
                print("inferred NVM_AGENT_ID from plan:", nvm_agent_id)
        except Exception as e:
            print("plan lookup warning:", e)

    token_result = None
    last_err = None

    # Try multiple agent-id variants because plan-agent association can be strict.
    candidate_agent_ids = []
    if nvm_agent_id:
        candidate_agent_ids.append(nvm_agent_id)
    candidate_agent_ids.append(None)

    for attempt in range(1, 4):
        for candidate_agent_id in candidate_agent_ids:
            try:
                token_kwargs = {
                    "plan_id": nvm_plan_id,
                    "redemption_limit": 1,
                }
                if candidate_agent_id:
                    token_kwargs["agent_id"] = candidate_agent_id

                token_result = p.x402.get_x402_access_token(**token_kwargs)
                if candidate_agent_id != nvm_agent_id:
                    nvm_agent_id = candidate_agent_id or ""
                break
            except Exception as e:
                last_err = e
                print(
                    f"token attempt {attempt}/3 with agent_id={candidate_agent_id or '<none>'} failed:",
                    e,
                )

        if token_result is not None:
            break

        # Common sandbox fix: subscribe buyer to plan before requesting x402 token.
        if "not associated to the agent" in str(last_err).lower():
            try:
                print("trying order_plan(...) to establish association before next retry...")
                p.plans.order_plan(plan_id=nvm_plan_id)
            except Exception as order_err:
                print("order_plan retry warning:", order_err)

        if attempt < 3:
            time.sleep(2 * attempt)
    if token_result is None:
        raise SystemExit(f"Failed to generate x402 access token after retries: {last_err}")

    token = token_result.get("accessToken", "")
    if not token:
        raise SystemExit("Failed to generate x402 access token.")
    print("token generated:", bool(token), "len:", len(token))

    # Local diagnostics: verify token against the same plan definition.
    try:
        network = "eip155:84532" if nvm_environment == "sandbox" else "eip155:8453"
        endpoint_url = endpoint
        payment_required = X402PaymentRequired(
            x402_version=2,
            resource=X402Resource(
                url=endpoint_url,
                description="AdAgent Studio paid campaign execution endpoint",
                mime_type="application/json",
            ),
            accepts=[
                X402Scheme(
                    scheme="nvm:erc4337",
                    network=network,
                    plan_id=nvm_plan_id,
                    extra=X402SchemeExtra(
                        version="1",
                        agent_id=nvm_agent_id or None,
                        http_verb="POST",
                    ),
                )
            ],
            extensions={},
        )
        verification = p.facilitator.verify_permissions(
            payment_required=payment_required,
            x402_access_token=token,
        )
        print("verify_permissions.is_valid:", verification.is_valid)
    except Exception as e:
        print("verify_permissions warning:", e)

    payload = {
        "brand": "TechStartup X",
        "goal": "drive signups",
        "audience": "SF tech founders 25-40",
        "budget": 15,
    }
    resp = requests.post(
        endpoint,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "payment-signature": token,
        },
        timeout=60,
    )

    print("status:", resp.status_code)
    try:
        print("response:", resp.json())
    except Exception:
        print("response_text:", resp.text[:500])


if __name__ == "__main__":
    main()
