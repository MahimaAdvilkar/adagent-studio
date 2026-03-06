from utils.config import GOOGLE_API_KEY, MINDRA_CHILD_NODE_ENABLED, MINDRA_TWITTER_AGENT_ENABLED
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

        if MINDRA_CHILD_NODE_ENABLED:
            self._inject_mindra_content_child(graph)
        if MINDRA_TWITTER_AGENT_ENABLED:
            self._inject_mindra_twitter_child(graph)

        return graph

    def _inject_mindra_content_child(self, graph: AgentGraph) -> None:
        """Ensure content generation runs before website creation using a Mindra child node."""
        website_node = None
        creative_node = None
        for node in graph.nodes.values():
            name_low = node.name.lower()
            id_low = node.id.lower()
            if "website" in name_low or "website" in id_low:
                website_node = node
            if "creative" in name_low or "creative" in id_low:
                creative_node = node

        if website_node is None:
            return

        # Prefer existing creative node so we don't duplicate creative calls.
        if creative_node is not None:
            child_node_id = creative_node.id
            creative_node.name = "Content Creator Agent"
            creative_node.level = 3
        else:
            child_node_id = "mindra_creative_content"
            child_depends = list(website_node.depends_on)
            child_node = AgentNode(
                id=child_node_id,
                name="Content Creator Agent",
                icon="✨",
                level=3,
                node_type=NodeType.LEAF,
                depends_on=child_depends,
                description=(
                    "Generate website-ready ad/content copy variants before website build. "
                    "This node is executed by the external content workflow."
                ),
                input=website_node.input,
            )
            graph.add_node(child_node)

            # Place the new node right before website execution when possible.
            if website_node.id in graph.execution_order:
                idx = graph.execution_order.index(website_node.id)
                if child_node_id not in graph.execution_order:
                    graph.execution_order.insert(idx, child_node_id)
            elif child_node_id not in graph.execution_order:
                graph.execution_order.append(child_node_id)

        # Website must wait for the Mindra content output.
        if child_node_id not in website_node.depends_on:
            website_node.depends_on.append(child_node_id)

        # If analytics has explicit dependencies, make sure it includes the child node.
        for node in graph.nodes.values():
            low = f"{node.id} {node.name}".lower()
            if "analytics" in low and child_node_id not in node.depends_on:
                node.depends_on.append(child_node_id)

    def _inject_mindra_twitter_child(self, graph: AgentGraph) -> None:
        """Ensure there is a Twitter posting node driven by Mindra after creatives are ready."""
        creative_node = None
        for node in graph.nodes.values():
            low = f"{node.id} {node.name}".lower()
            if "creative" in low or "content creator" in low:
                creative_node = node
                break

        if creative_node is None:
            return

        twitter_node = None
        for node in graph.nodes.values():
            low = f"{node.id} {node.name}".lower()
            if "twitter" in low or "x post" in low:
                twitter_node = node
                break

        twitter_node_id = "mindra_twitter_agent"
        if twitter_node is None:
            twitter_node = AgentNode(
                id=twitter_node_id,
                name="Twitter Agent",
                icon="X",
                level=3,
                node_type=NodeType.LEAF,
                depends_on=[creative_node.id],
                description=(
                    "Create one campaign tweet from creative outputs and post via connected "
                    "Twitter/X integration using Mindra workflow tools."
                ),
                input=creative_node.input,
            )
            graph.add_node(twitter_node)
        else:
            twitter_node.name = "Twitter Agent"
            twitter_node.level = max(3, twitter_node.level)
            if creative_node.id not in twitter_node.depends_on:
                twitter_node.depends_on.append(creative_node.id)
            twitter_node_id = twitter_node.id

        if twitter_node_id not in graph.execution_order:
            if creative_node.id in graph.execution_order:
                idx = graph.execution_order.index(creative_node.id)
                graph.execution_order.insert(idx + 1, twitter_node_id)
            else:
                graph.execution_order.append(twitter_node_id)

    def create(self, brief: dict) -> AgentGraph:
        if not self.client:
            raise RuntimeError("GOOGLE_API_KEY is missing or Gemini client is unavailable.")

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
        except Exception as e:
            raise RuntimeError(f"Blueprint generation failed: {str(e)}")
