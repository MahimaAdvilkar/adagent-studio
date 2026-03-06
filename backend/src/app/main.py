from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from app.agents.blueprint import Blueprint
from app.agents.executor import execute_graph
from app.agents.mindra_provider import MindraApiError, run_mindra_flow
from app.agents.orchestration import build_campaign_response, workflow_preview
from app.models.agent_graph import AgentGraph
from utils.payments import verify_payment_token, payment_status
from utils.trust_net_reviews import (
    TrustNetReviewApiError,
    get_free_reviews,
    submit_free_review,
)

app = FastAPI(title="AdAgent Studio", version="1.0.0")
blueprint = Blueprint()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CampaignBrief(BaseModel):
    brand: str
    goal: str
    audience: str
    budget: float = 15.0


class FreeReviewRequest(BaseModel):
    agent_id: str
    reviewer_address: str
    verification_tx: str
    score: int = Field(ge=1, le=10)
    comment: str
    score_accuracy: int | None = Field(default=None, ge=1, le=10)
    score_speed: int | None = Field(default=None, ge=1, le=10)
    score_value: int | None = Field(default=None, ge=1, le=10)
    score_reliability: int | None = Field(default=None, ge=1, le=10)


@app.get("/")
@app.get("/api")
@app.get("/api/")
async def read_root():
    return {"message": "AdAgent Studio backend is running!"}


@app.post("/createblueprint", response_model=AgentGraph)
@app.post("/api/createblueprint", response_model=AgentGraph)
async def create_blueprint(brief: CampaignBrief):
    try:
        return blueprint.create(brief.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Model returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/createblueprint/summary")
@app.post("/api/createblueprint/summary")
async def create_blueprint_summary(brief: CampaignBrief):
    try:
        graph = blueprint.create(brief.model_dump())
        return graph.summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workflow/preview")
@app.post("/api/workflow/preview")
async def preview_workflow(brief: CampaignBrief):
    return workflow_preview(brief.model_dump())


@app.post("/mindra/run")
@app.post("/api/mindra/run")
async def run_mindra(brief: CampaignBrief):
    try:
        return run_mindra_flow(brief.model_dump(), blueprint)
    except MindraApiError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run-campaign")
@app.post("/api/run-campaign")
async def run_campaign(brief: CampaignBrief, request: Request):
    """
    Payment-protected endpoint.
    Client must send a valid x402 token in the 'payment-signature' header.
    15 credits per call.
    """
    # Real-mode only: always require and verify payment token.
    token = request.headers.get("payment-signature", "")
    if not verify_payment_token(token, resource_url=str(request.url), http_verb=request.method):
        raise HTTPException(
            status_code=402,
            detail="Payment required. Send a valid x402 token in 'payment-signature' header."
        )

    try:
        # Step 1: Blueprint — LLM designs the agent graph
        brief_payload = brief.model_dump()
        graph = blueprint.create(brief_payload)

        # Step 2: Execute — run all agents in dependency order
        graph = execute_graph(graph)

        # Step 3: Normalize outputs for dashboard + orchestration view
        return build_campaign_response(graph, brief_payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/nvm-status")
@app.get("/api/nvm-status")
async def nvm_status():
    return payment_status()


@app.post("/trust-net/reviews")
@app.post("/api/trust-net/reviews")
async def trust_net_submit_review(review: FreeReviewRequest):
    try:
        return await submit_free_review(review.model_dump(exclude_none=True))
    except TrustNetReviewApiError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@app.get("/trust-net/reviews")
@app.get("/api/trust-net/reviews")
async def trust_net_list_reviews(agent_id: str):
    if not agent_id.strip():
        raise HTTPException(status_code=400, detail="agent_id is required")
    try:
        return await get_free_reviews(agent_id.strip())
    except TrustNetReviewApiError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
