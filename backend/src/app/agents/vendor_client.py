"""
Vendor client for AdAgent Studio.

Each method calls one external vendor agent with an x402 payment token.
All vendor plan IDs and URLs come from .env — swap in real values at the hackathon.
"""

import httpx
import json
import time
from urllib.parse import urlparse

from utils.payments import call_vendor, _mock_vendor_response
from utils.config import (
    DEV_MODE,
    WEBSITE_GUY_PLAN_ID, WEBSITE_GUY_URL,
    CREATIVE_LADY_PLAN_ID, CREATIVE_LADY_URL,
    EXA_PLAN_ID, EXA_URL,
    ZEROCLICK_PLAN_ID, ZEROCLICK_URL,
    MINDRA_API_KEY,
    MINDRA_API_URL,
    MINDRA_WORKFLOW_SLUG,
    MINDRA_TWITTER_API_URL,
    MINDRA_TWITTER_WORKFLOW_SLUG,
    MINDRA_TIMEOUT_SECONDS,
    MINDRA_CHILD_NODE_ENABLED,
    MINDRA_STREAM_WAIT_SECONDS,
)


def _mindra_run_url() -> str:
    if MINDRA_API_URL:
        return MINDRA_API_URL
    if MINDRA_WORKFLOW_SLUG:
        return f"https://api.mindra.co/v1/workflows/{MINDRA_WORKFLOW_SLUG}/run"
    return ""


def _mindra_twitter_run_url() -> str:
    if MINDRA_TWITTER_API_URL:
        return MINDRA_TWITTER_API_URL
    if MINDRA_TWITTER_WORKFLOW_SLUG:
        return f"https://api.mindra.co/v1/workflows/{MINDRA_TWITTER_WORKFLOW_SLUG}/run"
    return _mindra_run_url()


def _mindra_create_creatives(brief: dict) -> dict:
    """Invoke Mindra workflow as a creative/content child node."""
    if not MINDRA_API_KEY:
        raise RuntimeError("MINDRA child node enabled but MINDRA_API_KEY is missing")

    run_url = _mindra_run_url()
    if not run_url:
        raise RuntimeError(
            "MINDRA child node enabled but MINDRA_API_URL/MINDRA_WORKFLOW_SLUG is missing"
        )

    task = (
        f"Create ad creatives for brand '{brief.get('brand', '')}'. "
        f"Goal: {brief.get('goal', '')}. Audience: {brief.get('audience', '')}. "
        "Generate 3 concise ad variants with headline, body, and CTA."
    )

    payload = {
        "task": task,
        "metadata": {
            "source": "adagent-studio-child-node",
            "role": "creative_lady",
            "brief": brief,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": MINDRA_API_KEY,
    }

    with httpx.Client(timeout=MINDRA_TIMEOUT_SECONDS) as client:
        response = client.post(run_url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise RuntimeError(
            f"Mindra creative node failed: {response.status_code} {response.text[:300]}"
        )

    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Mindra creative node returned non-object JSON")

    execution_id = str(data.get("execution_id", ""))
    stream_url = str(data.get("stream_url", ""))

    stream_result = _collect_mindra_stream_output(
        headers=headers,
        execution_id=execution_id,
        stream_url=stream_url,
    )

    creatives = _extract_creatives(stream_result)
    status = "done" if creatives else str(data.get("status", "running"))

    return {
        "status": status,
        "provider": "mindra",
        "workflow_slug": str(data.get("workflow_slug", MINDRA_WORKFLOW_SLUG)),
        "execution_id": execution_id,
        "stream_url": stream_url,
        "creatives": creatives,
        "stream_events": stream_result,
        "raw": data,
    }


def _mindra_create_and_post_twitter(brief: dict) -> dict:
    """Invoke Mindra workflow to create and post one X/Twitter campaign update."""
    if not MINDRA_API_KEY:
        raise RuntimeError("MINDRA twitter node enabled but MINDRA_API_KEY is missing")

    run_url = _mindra_twitter_run_url()
    if not run_url:
        raise RuntimeError(
            "MINDRA twitter node enabled but twitter or default Mindra workflow URL/slug is missing"
        )

    creatives = brief.get("creatives", []) if isinstance(brief.get("creatives"), list) else []
    first_creative = creatives[0] if creatives and isinstance(creatives[0], dict) else {}
    headline = str(first_creative.get("headline", "")).strip()
    body = str(first_creative.get("body", "")).strip()

    task = (
        f"For brand '{brief.get('brand', '')}', create one concise Twitter/X post for goal "
        f"'{brief.get('goal', '')}' targeting '{brief.get('audience', '')}'. "
        "Use the provided creative context if available. Then publish it using the connected "
        "Twitter/X integration tool. Do not stop at drafting. Execute the posting tool. "
        "Return strict JSON with keys: post_content, post_url, posted (true/false), reason."
    )

    payload = {
        "task": task,
        "metadata": {
            "source": "adagent-studio-child-node",
            "role": "twitter_agent",
            "brief": brief,
            "creative_context": {
                "headline": headline,
                "body": body,
            },
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": MINDRA_API_KEY,
    }

    with httpx.Client(timeout=MINDRA_TIMEOUT_SECONDS) as client:
        response = client.post(run_url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise RuntimeError(
            f"Mindra twitter node failed: {response.status_code} {response.text[:300]}"
        )

    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Mindra twitter node returned non-object JSON")

    execution_id = str(data.get("execution_id", ""))
    stream_url = str(data.get("stream_url", ""))

    stream_result = _collect_mindra_stream_output(
        headers=headers,
        execution_id=execution_id,
        stream_url=stream_url,
    )

    tweet_text, post_url, pending_approval, approval_id = _extract_twitter_result(stream_result)
    tool_names: list[str] = []
    for event in stream_result.get("tool_events", []):
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        for key in ["tool_name", "name", "tool"]:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                tool_names.append(value.strip())
                break

    # Deduplicate while preserving order.
    seen_tools = set()
    deduped_tool_names: list[str] = []
    for name in tool_names:
        if name in seen_tools:
            continue
        seen_tools.add(name)
        deduped_tool_names.append(name)

    twitter_tool_used = any("twitter" in name.lower() or "tweet" in name.lower() for name in deduped_tool_names)

    status = str(data.get("status", "running"))
    status_reason = ""
    if pending_approval:
        status = "pending_approval"
        status_reason = "Posting requires approval; approve using execution_id + approval_id."
    elif post_url:
        status = "done"
        status_reason = "Tweet posted successfully."
    elif tweet_text:
        status = "generated_only"
        status_reason = "Tweet text generated but no post URL returned by workflow/tool."
    else:
        status = "not_posted"
        status_reason = "No generated tweet text or post URL returned by workflow."

    return {
        "status": status,
        "provider": "mindra",
        "workflow_slug": str(data.get("workflow_slug", MINDRA_WORKFLOW_SLUG)),
        "execution_id": execution_id,
        "stream_url": stream_url,
        "tweet_text": tweet_text,
        "post_url": post_url,
        "pending_approval": pending_approval,
        "approval_id": approval_id,
        "twitter_tool_used": twitter_tool_used,
        "tool_names": deduped_tool_names,
        "status_reason": status_reason,
        "stream_events": stream_result,
        "raw": data,
    }


def _collect_mindra_stream_output(headers: dict, execution_id: str, stream_url: str) -> dict:
    """Read Mindra SSE stream until done or timeout and capture content events."""
    if not stream_url:
        return {"status": "missing_stream_url", "chunks": [], "done": None}

    endpoint_candidates = _build_stream_candidates(stream_url, execution_id)

    started = time.monotonic()
    chunks: list[str] = []
    done_payload = None
    last_event = ""
    tool_events: list[dict] = []
    http_errors: list[str] = []

    try:
        with httpx.Client(timeout=MINDRA_TIMEOUT_SECONDS) as client:
            for endpoint in endpoint_candidates:
                with client.stream(
                    "GET",
                    endpoint,
                    headers={"x-api-key": headers["x-api-key"], "Accept": "text/event-stream"},
                ) as response:
                    if response.status_code >= 400:
                        http_errors.append(f"{endpoint} -> {response.status_code}")
                        continue

                    for line in response.iter_lines():
                        if time.monotonic() - started > MINDRA_STREAM_WAIT_SECONDS:
                            return {
                                "status": "timeout",
                                "chunks": chunks,
                                "done": done_payload,
                                "tool_events": tool_events,
                                "stream_endpoint": endpoint,
                                "http_errors": http_errors,
                            }

                        if not line:
                            continue

                        if line.startswith("event: "):
                            last_event = line[7:].strip()
                            continue

                        if not line.startswith("data: "):
                            continue

                        raw_data = line[6:].strip()
                        try:
                            payload = json.loads(raw_data)
                        except Exception:
                            payload = {"raw": raw_data}

                        # Many SSE implementations include event names, but some only send data payloads.
                        if last_event == "chunk":
                            content = _extract_text_from_payload(payload)
                            if content:
                                chunks.append(content)
                        elif last_event in {"tool_executing", "tool_result", "approval_request"}:
                            if isinstance(payload, dict):
                                tool_events.append({"event": last_event, "payload": payload})
                                if last_event == "tool_result":
                                    tool_text = _extract_text_from_payload(payload.get("result"))
                                    if tool_text:
                                        chunks.append(tool_text)
                        elif last_event == "done":
                            if isinstance(payload, dict):
                                done_payload = payload
                            # Some responses send an empty done payload first; keep reading for real content.
                            done_has_content = bool(_extract_text_from_payload(done_payload))
                            if done_has_content or chunks:
                                return {
                                    "status": "done",
                                    "chunks": chunks,
                                    "done": done_payload,
                                    "tool_events": tool_events,
                                    "stream_endpoint": endpoint,
                                    "http_errors": http_errors,
                                }

                        # Generic fallback: parse text-like payloads even when event labels are missing.
                        if last_event not in {"tool_executing", "tool_result", "approval_request"}:
                            generic_text = _extract_text_from_payload(payload)
                            if generic_text and generic_text not in chunks:
                                chunks.append(generic_text)

                    # If this endpoint produced no useful stream payload, try next candidate.
                    if not chunks and not _extract_text_from_payload(done_payload) and not tool_events:
                        http_errors.append(f"{endpoint} -> empty_stream")
                        continue

                    return {
                        "status": "ended",
                        "chunks": chunks,
                        "done": done_payload,
                        "tool_events": tool_events,
                        "stream_endpoint": endpoint,
                        "http_errors": http_errors,
                    }

    except Exception as exc:
        return {
            "status": f"stream_error: {str(exc)}",
            "chunks": chunks,
            "done": done_payload,
            "tool_events": tool_events,
            "http_errors": http_errors,
        }

    return {
        "status": "stream_unreachable",
        "chunks": chunks,
        "done": done_payload,
        "tool_events": tool_events,
        "http_errors": http_errors,
    }


def _build_stream_candidates(stream_url: str, execution_id: str = "") -> list[str]:
    parsed_base = urlparse(MINDRA_API_URL) if MINDRA_API_URL else None
    base = (
        f"{parsed_base.scheme}://{parsed_base.netloc}"
        if parsed_base and parsed_base.scheme and parsed_base.netloc
        else "https://api.mindra.co"
    )

    candidates: list[str] = []
    if stream_url.startswith("http://") or stream_url.startswith("https://"):
        candidates.append(stream_url)
    else:
        path = stream_url if stream_url.startswith("/") else f"/{stream_url}"
        candidates.append(f"{base}{path}")
        if path.startswith("/api/v1/"):
            candidates.append(f"{base}{path.replace('/api/v1/', '/v1/', 1)}")
        if path.startswith("/v1/"):
            candidates.append(f"{base}{path.replace('/v1/', '/api/v1/', 1)}")

    # Also try explicit execution-based stream paths regardless of returned stream_url.
    if execution_id:
        candidates.append(f"{base}/v1/workflows/execute/{execution_id}/stream")
        candidates.append(f"{base}/api/v1/workflows/execute/{execution_id}/stream")

    deduped: list[str] = []
    seen = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _extract_creatives(stream_result: dict) -> list[dict]:
    """Build creative variants from stream done payload or chunked content."""
    done_payload = stream_result.get("done") if isinstance(stream_result, dict) else None
    chunks = stream_result.get("chunks", []) if isinstance(stream_result, dict) else []

    # 1) Prefer explicit tool outputs (usually one entry per generated variant).
    tool_creatives: list[dict] = []
    seen_bodies: set[str] = set()
    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, str):
                continue
            text = chunk.strip()
            if not text.startswith("{"):
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue

            content = payload.get("content") or payload.get("post_content")
            if not isinstance(content, str) or not content.strip():
                continue

            body = content.strip()
            if body in seen_bodies:
                continue
            seen_bodies.add(body)

            topic = payload.get("topic") if isinstance(payload.get("topic"), str) else ""
            tone = payload.get("tone") if isinstance(payload.get("tone"), str) else ""
            platform = payload.get("platform") if isinstance(payload.get("platform"), str) else ""

            title = topic.strip() if topic else "Ad Variant"
            if len(title) > 90:
                title = title[:87] + "..."

            tool_creatives.append(
                {
                    "headline": title,
                    "body": body,
                    "cta": "Use this copy",
                    "format": platform or tone or "text",
                }
            )

    if tool_creatives:
        # Keep top 3 variants for clean UX.
        return tool_creatives[:3]

    final_answer = ""
    if isinstance(done_payload, dict):
        maybe = (
            done_payload.get("final_answer")
            or done_payload.get("answer")
            or done_payload.get("result")
            or done_payload.get("content")
            or done_payload.get("message")
            or done_payload.get("output")
        )
        final_answer = _extract_text_from_payload(maybe)

    if not final_answer and isinstance(chunks, list):
        final_answer = "\n".join(c for c in chunks if isinstance(c, str) and c.strip()).strip()

    if not final_answer:
        return []

    # 2) Parse markdown-style "Variant" blocks from final answer when present.
    if "Variant 1" in final_answer and "Variant 2" in final_answer:
        parts = final_answer.split("## ")
        parsed_variants: list[dict] = []
        for part in parts:
            section = part.strip()
            if not section.startswith("🚀 Variant") and not section.startswith("🤝 Variant") and not section.startswith("😤 Variant") and not section.startswith("Variant"):
                continue
            lines = section.splitlines()
            headline = "Ad Variant"
            cta = "Use this copy"
            body_lines: list[str] = []
            for line in lines:
                l = line.strip()
                if l.startswith("**Headline:**"):
                    headline = l.replace("**Headline:**", "").strip(" >")
                elif l.startswith("**CTA:**"):
                    cta = l.replace("**CTA:**", "").strip(" >")
                elif l.startswith("**Body:**"):
                    body_lines.append(l.replace("**Body:**", "").strip(" >"))
                elif l.startswith(">"):
                    body_lines.append(l.lstrip("> "))
            body = "\n".join([b for b in body_lines if b]).strip()
            if body:
                parsed_variants.append(
                    {
                        "headline": headline,
                        "body": body,
                        "cta": cta,
                        "format": "text",
                    }
                )

        if parsed_variants:
            return parsed_variants[:3]

    # If final answer itself is JSON containing creatives, prefer that shape.
    try:
        parsed = json.loads(final_answer)
        if isinstance(parsed, dict) and isinstance(parsed.get("creatives"), list):
            return [c for c in parsed["creatives"] if isinstance(c, dict)]
        if isinstance(parsed, list):
            return [c for c in parsed if isinstance(c, dict)]
    except Exception:
        pass

    return [
        {
            "headline": "Generated Content",
            "body": final_answer,
            "cta": "Use this copy",
            "format": "text",
        }
    ]


def _extract_text_from_payload(value) -> str:
    """Best-effort extraction of meaningful text from varying event payload shapes."""
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for key in ["content", "text", "delta", "answer", "final_answer", "result", "message", "output"]:
            if key in value:
                text = _extract_text_from_payload(value.get(key))
                if text:
                    return text

        # Last resort: serialize compactly if no obvious key exists.
        try:
            return json.dumps(value, ensure_ascii=True)
        except Exception:
            return ""

    if isinstance(value, list):
        parts = [_extract_text_from_payload(item) for item in value]
        return "\n".join([p for p in parts if p]).strip()

    return ""


def _extract_twitter_result(stream_result: dict) -> tuple[str, str, bool, str]:
    """Extract tweet body + post URL from stream result payloads."""
    if not isinstance(stream_result, dict):
        return "", "", False, ""

    pending_approval = False
    approval_id = ""
    post_url = ""
    candidates: list[str] = []

    for event in stream_result.get("tool_events", []):
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("event", ""))
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event_type == "approval_request":
            pending_approval = True
            maybe_approval_id = payload.get("approval_id")
            if isinstance(maybe_approval_id, str) and maybe_approval_id.strip():
                approval_id = maybe_approval_id.strip()
            else:
                maybe_approval_id = payload.get("approvalId")
                if isinstance(maybe_approval_id, str) and maybe_approval_id.strip():
                    approval_id = maybe_approval_id.strip()
        for key in ["post_url", "url", "tweet_url"]:
            value = payload.get(key)
            if isinstance(value, str) and value.startswith("http"):
                post_url = value

    done = stream_result.get("done") if isinstance(stream_result.get("done"), dict) else {}
    for key in ["final_answer", "answer", "result", "content", "message", "output"]:
        text = _extract_text_from_payload(done.get(key))
        if text:
            candidates.append(text)

    for chunk in stream_result.get("chunks", []):
        if isinstance(chunk, str) and chunk.strip():
            candidates.append(chunk.strip())

    tweet_text = ""
    # Use latest meaningful text first; early chunks are often planning/thinking traces.
    for text in reversed(candidates):
        stripped = text.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if (
            lower.startswith("let me ")
            or lower.startswith("i will ")
            or "checking for any stored context" in lower
            or "recalling relevant memories" in lower
        ):
            continue
        if stripped.startswith("{"):
            try:
                payload = json.loads(stripped)
            except Exception:
                payload = None
            if isinstance(payload, dict):
                posted = payload.get("posted")
                if isinstance(posted, bool) and not posted:
                    # Keep scanning for a successful posted payload.
                    pass
                for key in ["post_content", "content", "tweet", "text"]:
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        tweet_text = value.strip()
                        break
                for key in ["post_url", "url", "tweet_url"]:
                    value = payload.get(key)
                    if isinstance(value, str) and value.startswith("http"):
                        post_url = value
                if tweet_text:
                    break
        elif len(stripped) <= 1000:
            tweet_text = stripped
            break

    return tweet_text, post_url, pending_approval, approval_id


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
        if MINDRA_CHILD_NODE_ENABLED:
            return _mindra_create_creatives(brief)

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

    # ── Twitter Agent (Mindra workflow tools) ─────────────────────────────────

    @staticmethod
    def create_and_post_twitter(brief: dict) -> dict:
        """Create and post campaign tweet using Mindra workflow integration."""
        return _mindra_create_and_post_twitter(brief)
