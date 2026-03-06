"""
Nevermined payment utilities for AdAgent Studio.

Seller side  — verifies + settles incoming payment tokens on /run-campaign
Buyer side   — generates tokens to pay vendors (Website Guy, Creative Lady, etc.)
"""

import requests
from utils.config import NVM_API_KEY, NVM_ENVIRONMENT, NVM_PLAN_ID, NVM_AGENT_ID

# Lazy import — payments-py is optional; app still boots if unavailable
try:
    from payments_py import Payments, PaymentOptions
    from payments_py.x402.types import X402PaymentRequired, X402Scheme
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


def _build_payment_required(plan_id: str):
    """Build the X402PaymentRequired object describing our plan."""
    return X402PaymentRequired(
        x402_version=2,
        accepts=[
            X402Scheme(
                scheme="nvm:erc4337",
                network=_NETWORK,
                plan_id=plan_id,
            )
        ],
        extensions={},
    )


# ── SELLER SIDE ───────────────────────────────────────────────────────────────

def verify_payment_token(token: str) -> bool:
    """
    Verify + settle an incoming x402 payment token from a client.
    Returns True if valid and credits were burnt, or True in dev if NVM not set.
    """
    if not NVM_API_KEY or not _NVM_AVAILABLE:
        return True  # dev mode — no NVM configured yet
    if not token:
        return False
    try:
        p = _get_client()
        payment_required = _build_payment_required(NVM_PLAN_ID)

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
    Returns the token string, or empty string if NVM not configured.
    """
    if not NVM_API_KEY or not vendor_plan_id or not _NVM_AVAILABLE:
        return ""
    try:
        p = _get_client()
        result = p.x402.get_x402_access_token(
            plan_id=vendor_plan_id,
            agent_id=vendor_agent_id,
            redemption_limit=1,
        )
        return result.get("accessToken", "")
    except Exception as e:
        print(f"[NVM] Token generation failed for plan {vendor_plan_id}: {e}")
        return ""


def call_vendor(
    vendor_url: str,
    vendor_plan_id: str,
    payload: dict,
    vendor_agent_id: str = None,
) -> dict:
    """
    Call a vendor endpoint with an x402 payment token.
    Falls back to direct call (no payment) if NVM is not configured.
    """
    token = generate_vendor_token(vendor_plan_id, vendor_agent_id)

    headers = {"Content-Type": "application/json"}
    if token:
        headers["payment-signature"] = token

    response = requests.post(vendor_url, json=payload, headers=headers, timeout=30)

    if response.status_code == 402:
        raise Exception("Payment required — token may be invalid or credits exhausted.")

    response.raise_for_status()
    return response.json()
