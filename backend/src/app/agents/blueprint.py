from utils.config import GOOGLE_API_KEY
from app.models.agent_graph import AgentGraph, AgentNode, NodeType
import json
import os

try:
    from google import genai
except Exception:
    genai = None

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")


class Blueprint:
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY) if (genai and GOOGLE_API_KEY) else None
        self.model = "gemini-2.5-flash"

    def _load_prompt(self, filename: str) -> str:
        with open(os.path.join(PROMPTS_DIR, filename), "r", encoding="utf-8") as f:
            return f.read()

    def _strip_fences(self, raw: str) -> str:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return raw.strip()

    def _parse_graph(self, raw_data: dict, brief: dict) -> AgentGraph:
        graph = AgentGraph(
            campaign_id=raw_data.get("campaign_id", "unknown"),
            brand=raw_data.get("brand", brief.get("brand", "")),
            goal=raw_data.get("goal", brief.get("goal", "")),
            total_budget=raw_data.get("total_budget", brief.get("budget", 0)),
            execution_order=raw_data.get("execution_order", []),
        )

        for agent_data in raw_data.get("agents", []):
            node = AgentNode(
                id=agent_data["id"],
                name=agent_data["name"],
                icon=agent_data.get("icon", ""),
                level=agent_data.get("level", 1),
                node_type=NodeType(agent_data.get("node_type", "leaf")),
                depends_on=agent_data.get("depends_on", []),
                description=agent_data.get("description", ""),
                spawns_subagents=agent_data.get("spawns_subagents", False),
                subgraph_hint=agent_data.get("subgraph_hint", ""),
                input=brief,
            )
            graph.add_node(node)

        return graph

    def _fallback_graph(self, brief: dict) -> AgentGraph:
        raw_data = {
            "campaign_id": "fallback-campaign",
            "brand": brief.get("brand", ""),
            "goal": brief.get("goal", ""),
            "total_budget": brief.get("budget", 0),
            "execution_order": ["ceo", "strategy", "analytics", "budget_manager"],
            "agents": [
                {
                    "id": "ceo",
                    "name": "CEO Agent",
                    "icon": "👔",
                    "level": 1,
                    "node_type": "orchestrator",
                    "depends_on": [],
                    "description": "Coordinates campaign execution and vendors."
                },
                {
                    "id": "strategy",
                    "name": "Strategy Agent",
                    "icon": "🎯",
                    "level": 2,
                    "node_type": "leaf",
                    "depends_on": ["ceo"],
                    "description": "Builds targeting, messaging, and channel strategy."
                },
                {
                    "id": "analytics",
                    "name": "Analytics Agent",
                    "icon": "📊",
                    "level": 2,
                    "node_type": "leaf",
                    "depends_on": ["ceo"],
                    "description": "Tracks campaign performance and ROI."
                },
                {
                    "id": "budget_manager",
                    "name": "Budget Manager Agent",
                    "icon": "💰",
                    "level": 2,
                    "node_type": "leaf",
                    "depends_on": ["ceo"],
                    "description": "Enforces budget constraints and spend allocation."
                },
            ],
        }
        return self._parse_graph(raw_data, brief)

    def create(self, brief: dict) -> AgentGraph:
        if not self.client:
            return self._fallback_graph(brief)

        system_prompt = self._load_prompt("root_agent_prompt.txt")
        user_message = json.dumps(brief, indent=2)
        full_prompt = f"{system_prompt}\n\nClient Brief:\n{user_message}"
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=full_prompt
            )
            raw = self._strip_fences(response.text.strip())
            raw_data = json.loads(raw)
            return self._parse_graph(raw_data, brief)
        except Exception:
            return self._fallback_graph(brief)
