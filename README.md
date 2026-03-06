# adagent-studio
Autonomous Ad Agency — AI agents that buy data, create and place ads, and optimize campaigns via Nevermined

## Mindra Provider Setup

Backend supports two Mindra modes for `POST /mindra/run`:

- `MINDRA_PROVIDER=local` runs the internal graph orchestrator (default).
- `MINDRA_PROVIDER=api` calls an external Mindra endpoint.

When using `api`, set these in `backend/.env`:

```
MINDRA_PROVIDER=api
MINDRA_API_URL=https://<your-mindra-endpoint>
MINDRA_API_KEY=<optional-bearer-token>
MINDRA_TIMEOUT_SECONDS=180
```

Behavior is explicit: if `MINDRA_PROVIDER=api` and config/request fails, backend returns an error instead of silently falling back.
