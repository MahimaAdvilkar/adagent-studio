"""
Nevermined payment utilities for AdAgent Studio.

Seller side  — verifies + settles incoming payment tokens on /run-campaign
Buyer side   — generates tokens to pay vendors (Website Guy, Creative Lady, etc.)
"""

import requests
from utils.config import NVM_API_KEY, NVM_ENVIRONMENT, NVM_PLAN_ID, NVM_AGENT_ID, DEV_MODE

# Lazy import — payments-py is optional; app still boots if unavailable
try:
    from payments_py import Payments, PaymentOptions
    from payments_py.x402.types import X402PaymentRequired, X402Scheme, X402Resource, X402SchemeExtra
    _NVM_AVAILABLE = True
except ImportError:
    _NVM_AVAILABLE = False

# Sandbox = Base Sepolia (eip155:84532), Mainnet = Base (eip155:8453)
_NETWORK = "eip155:84532" if NVM_ENVIRONMENT == "sandbox" else "eip155:8453"


def _get_client():
    if not _NVM_AVAILABLE:
        raise RuntimeError("payments-py not installed")
    return Payments.get_instance(
        PaymentOptions(
            nvm_api_key=NVM_API_KEY,
            environment=NVM_ENVIRONMENT,
        )
    )


def _build_payment_required(plan_id: str, resource_url: str, http_verb: str = "POST"):
    """Build the X402PaymentRequired object describing our protected endpoint."""
    scheme_extra = X402SchemeExtra(
        version="1",
        agent_id=NVM_AGENT_ID or None,
        http_verb=http_verb,
    )
    return X402PaymentRequired(
        x402_version=2,
        resource=X402Resource(
            url=resource_url,
            description="AdAgent Studio paid campaign execution endpoint",
            mime_type="application/json",
        ),
        accepts=[
            X402Scheme(
                scheme="nvm:erc4337",
                network=_NETWORK,
                plan_id=plan_id,
                extra=scheme_extra,
            )
        ],
        extensions={},
    )


# ── SELLER SIDE ───────────────────────────────────────────────────────────────

def verify_payment_token(token: str, resource_url: str = "", http_verb: str = "POST") -> bool:
    """
    Verify + settle an incoming x402 payment token from a client.
    Returns True if valid and credits were burnt.
    """
    if not NVM_API_KEY:
        print("[NVM] NVM_API_KEY is missing.")
        return False
    if not _NVM_AVAILABLE:
        print("[NVM] payments-py SDK is not available in non-dev mode.")
        return False
    if not token:
        return False
    try:
        p = _get_client()
        payment_required = _build_payment_required(
            NVM_PLAN_ID,
            resource_url=resource_url or "https://adagent-studio-seven.vercel.app/api/run-campaign",
            http_verb=http_verb,
        )

        # First verify (dry-run, doesn't burn credits)
        verification = p.facilitator.verify_permissions(
            payment_required=payment_required,
            x402_access_token=token,
        )
        if not verification.is_valid:
            print(f"[NVM] Token invalid: {verification}")
            return False

        # Then settle (burns credits)
        settlement = p.facilitator.settle_permissions(
            payment_required=payment_required,
            x402_access_token=token,
        )
        print(f"[NVM] Credits redeemed: {settlement.credits_redeemed}")
        return True
    except Exception as e:
        print(f"[NVM] Token verification/settlement failed: {e}")
        return False


# ── BUYER SIDE ────────────────────────────────────────────────────────────────

def generate_vendor_token(vendor_plan_id: str, vendor_agent_id: str = None) -> str:
    """
    Generate an x402 access token to pay a vendor.
    Returns the token string.
    """
    if not NVM_API_KEY:
        raise RuntimeError("NVM_API_KEY is missing; cannot generate vendor token.")
    if not vendor_plan_id:
        raise RuntimeError("Vendor plan ID is missing; cannot generate vendor token.")
    if not _NVM_AVAILABLE:
        raise RuntimeError("payments-py SDK is unavailable; cannot generate vendor token.")
    try:
        p = _get_client()
        result = p.x402.get_x402_access_token(
            plan_id=vendor_plan_id,
            agent_id=vendor_agent_id,
            redemption_limit=1,
        )
        token = result.get("accessToken", "")
        if not token:
            raise RuntimeError(f"Empty x402 access token for vendor plan {vendor_plan_id}.")
        return token
    except Exception as e:
        raise RuntimeError(f"[NVM] Token generation failed for plan {vendor_plan_id}: {e}") from e


def call_vendor(
    vendor_url: str,
    vendor_plan_id: str,
    payload: dict,
    vendor_agent_id: str = None,
) -> dict:
    """
    Call a vendor endpoint with an x402 payment token.
    """
    token = generate_vendor_token(vendor_plan_id, vendor_agent_id)

    headers = {"Content-Type": "application/json"}
    headers["payment-signature"] = token

    response = requests.post(vendor_url, json=payload, headers=headers, timeout=30)

    if response.status_code == 402:
        raise Exception("Payment required — token may be invalid or credits exhausted.")

    response.raise_for_status()
    return response.json()


def payment_status() -> dict:
    """Return non-sensitive Nevermined integration status for diagnostics."""
    return {
        "dev_mode": DEV_MODE,
        "sdk_available": _NVM_AVAILABLE,
        "api_key_set": bool(NVM_API_KEY),
        "environment": NVM_ENVIRONMENT or "unset",
        "plan_id_set": bool(NVM_PLAN_ID),
        "agent_id_set": bool(NVM_AGENT_ID),
    }
