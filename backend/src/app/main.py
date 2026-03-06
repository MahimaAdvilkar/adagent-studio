from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from app.agents.blueprint import Blueprint
from app.models.agent_graph import AgentGraph
from utils.payments import verify_payment_token

app = FastAPI(title="AdAgent Studio", version="1.0.0")
blueprint = Blueprint()


class CampaignBrief(BaseModel):
    brand: str
    goal: str
    audience: str
    budget: float = 15.0


@app.get("/")
async def read_root():
    return {"message": "AdAgent Studio backend is running!"}


@app.post("/createblueprint", response_model=AgentGraph)
async def create_blueprint(brief: CampaignBrief):
    try:
        return blueprint.create(brief.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Model returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/createblueprint/summary")
async def create_blueprint_summary(brief: CampaignBrief):
    try:
        graph = blueprint.create(brief.model_dump())
        return graph.summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run-campaign")
async def run_campaign(brief: CampaignBrief, request: Request):
    """
    Payment-protected endpoint.
    Client must send a valid x402 token in the 'payment-signature' header.
    15 credits per call.
    """
    # Verify payment token
    token = request.headers.get("payment-signature", "")
    if not verify_payment_token(token):
        return HTTPException(
            status_code=402,
            detail="Payment required. Send x402 token in 'payment-signature' header."
        )

    try:
        graph = blueprint.create(brief.model_dump())
        return {
            "status": "accepted",
            "campaign_id": graph.campaign_id,
            "message": "Campaign blueprint created. Agents are queued for execution.",
            "graph_summary": graph.summary(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
