from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from datetime import datetime, timezone


class AgentStatus(str, Enum):
    PENDING   = "pending"    # waiting for dependencies
    READY     = "ready"      # dependencies met, can run
    RUNNING   = "running"    # currently executing
    DONE      = "done"       # completed successfully
    FAILED    = "failed"     # execution error
    SKIPPED   = "skipped"    # not needed for this campaign


class NodeType(str, Enum):
    ORCHESTRATOR = "orchestrator"  # spawns sub-agents
    LEAF         = "leaf"          # executes directly


class AgentNode(BaseModel):
    # Identity
    id: str
    name: str
    icon: str = ""
    level: int                          # 1 = top-level, 2 = sub-agent, 3 = leaf
    node_type: NodeType

    # Graph edges
    depends_on: list[str] = Field(default_factory=list)   # ids this node waits for
    children: list[str] = Field(default_factory=list)     # ids of sub-agents it spawns

    # What it does
    description: str
    spawns_subagents: bool = False
    subgraph_hint: str = ""            # instruction fed to Level N+1 prompt

    # Execution state
    status: AgentStatus = AgentStatus.PENDING

    # I/O
    input: Optional[dict] = None       # payload passed in from parent/brief
    output: Optional[dict] = None      # result produced by this agent

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def mark_running(self) -> None:
        self.status = AgentStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def mark_done(self, output: dict) -> None:
        self.status = AgentStatus.DONE
        self.output = output
        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        self.status = AgentStatus.FAILED
        self.output = {"error": error}
        self.completed_at = datetime.now(timezone.utc)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class AgentGraph(BaseModel):
    # Campaign identity
    campaign_id: str
    brand: str
    goal: str
    total_budget: float

    # All nodes keyed by id for O(1) lookup
    nodes: dict[str, AgentNode] = Field(default_factory=dict)

    # Ordered list of node ids showing activation sequence
    execution_order: list[str] = Field(default_factory=list)

    # Graph-level state
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    # ── helpers ──────────────────────────────────────────────

    def add_node(self, node: AgentNode) -> None:
        self.nodes[node.id] = node

    def get_node(self, node_id: str) -> Optional[AgentNode]:
        return self.nodes.get(node_id)

    def get_ready_nodes(self) -> list[AgentNode]:
        """Return all PENDING nodes whose dependencies are all DONE."""
        ready = []
        for node in self.nodes.values():
            if node.status != AgentStatus.PENDING:
                continue
            deps_done = all(
                self.nodes[dep].status == AgentStatus.DONE
                for dep in node.depends_on
                if dep in self.nodes
            )
            if deps_done:
                ready.append(node)
        return ready

    def get_nodes_by_level(self, level: int) -> list[AgentNode]:
        return [n for n in self.nodes.values() if n.level == level]

    def get_orchestrators(self) -> list[AgentNode]:
        return [n for n in self.nodes.values() if n.node_type == NodeType.ORCHESTRATOR]

    def is_complete(self) -> bool:
        return all(
            n.status in (AgentStatus.DONE, AgentStatus.SKIPPED, AgentStatus.FAILED)
            for n in self.nodes.values()
        )

    def summary(self) -> dict:
        statuses = {}
        for s in AgentStatus:
            statuses[s.value] = sum(1 for n in self.nodes.values() if n.status == s)
        return {
            "campaign_id": self.campaign_id,
            "brand": self.brand,
            "goal": self.goal,
            "total_budget": self.total_budget,
            "total_agents": len(self.nodes),
            "statuses": statuses,
            "is_complete": self.is_complete(),
        }
