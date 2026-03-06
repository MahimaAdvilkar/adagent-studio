"""
Standalone Twitter flow tester for AdAgent Studio.

Runs only the Mindra-backed Twitter agent path with a dummy brief.
No full graph execution required.

Usage:
  cd backend/src
  ..\..\.venv\Scripts\python.exe test_twitter_flow.py

Optional flags:
  --approve    Auto-approve when an approval_id is returned
  --reject     Auto-reject when an approval_id is returned
  --reason     Reason string for approve/reject actions
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from app.agents.vendor_client import VendorClient
from utils.config import MINDRA_API_KEY, MINDRA_TIMEOUT_SECONDS


def _action_url(execution_id: str, approval_id: str, action: str) -> str:
    return f"https://api.mindra.co/v1/workflows/execute/{execution_id}/{action}/{approval_id}"


def _approve_or_reject(
    execution_id: str,
    approval_id: str,
    action: str,
    reason: str,
) -> dict:
    if action not in {"approve", "reject"}:
        return {"ok": False, "error": f"Unsupported action: {action}"}
    if not MINDRA_API_KEY:
        return {"ok": False, "error": "MINDRA_API_KEY missing"}

    url = _action_url(execution_id, approval_id, action)
    headers = {
        "x-api-key": MINDRA_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=MINDRA_TIMEOUT_SECONDS) as client:
            resp = client.post(url, headers=headers, json={"reason": reason})
        return {
            "ok": resp.status_code < 400,
            "status_code": resp.status_code,
            "body": resp.text[:500],
            "url": url,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": url}


def main() -> int:
    parser = argparse.ArgumentParser(description="Test only the Mindra Twitter posting flow")
    parser.add_argument("--approve", action="store_true", help="Approve pending tool request")
    parser.add_argument("--reject", action="store_true", help="Reject pending tool request")
    parser.add_argument(
        "--reason",
        default="Approved by tester script",
        help="Reason sent to approve/reject endpoint",
    )
    args = parser.parse_args()

    if args.approve and args.reject:
        print("Choose only one of --approve or --reject")
        return 2

    dummy_brief = {
        "brand": "TechStartup X",
        "goal": "drive signups",
        "audience": "SF tech founders 25-40",
        "budget": 15,
        "creatives": [
            {
                "headline": "Move faster with one stack",
                "body": "Cut context-switching and launch faster with TechStartup X.",
                "cta": "Start free",
                "format": "twitter",
            }
        ],
    }

    print("Running Twitter agent test with dummy brief...")
    result = VendorClient.create_and_post_twitter(dummy_brief)

    output = {
        "status": result.get("status"),
        "status_reason": result.get("status_reason"),
        "execution_id": result.get("execution_id"),
        "workflow_slug": result.get("workflow_slug"),
        "pending_approval": result.get("pending_approval"),
        "approval_id": result.get("approval_id"),
        "twitter_tool_used": result.get("twitter_tool_used"),
        "tool_names": result.get("tool_names"),
        "tweet_text": result.get("tweet_text"),
        "post_url": result.get("post_url"),
    }
    print(json.dumps(output, indent=2, ensure_ascii=True))

    if result.get("pending_approval"):
        print("Approval is required before posting can complete.")

    execution_id = str(result.get("execution_id") or "")
    approval_id = str(result.get("approval_id") or "")

    if (args.approve or args.reject) and execution_id and approval_id:
        action = "approve" if args.approve else "reject"
        print(f"Sending {action} for approval_id={approval_id} ...")
        action_result = _approve_or_reject(
            execution_id=execution_id,
            approval_id=approval_id,
            action=action,
            reason=args.reason,
        )
        print(json.dumps(action_result, indent=2, ensure_ascii=True))
    elif (args.approve or args.reject) and (not execution_id or not approval_id):
        print("Cannot approve/reject because execution_id or approval_id is missing.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
