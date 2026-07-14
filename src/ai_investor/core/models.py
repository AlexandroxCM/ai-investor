"""Domain models. Every message between agents is one of these — no raw dicts."""
from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, Field

from .enums import OrderStatus, RiskAction, Signal


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Bar(BaseModel):
    ticker: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class Article(BaseModel):
    ticker: str
    headline: str
    body: str
    published: datetime
    source: str = ""
    tier: int = 3  # 1 = regulatory filing, 2 = earnings-related, 3 = general news


class AgentReport(BaseModel):
    agent: str
    ticker: str
    score: float = Field(ge=-1.0, le=1.0)   # -1 bearish .. +1 bullish
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    evidence: list[str] = []


class TradeProposal(BaseModel):
    ticker: str
    signal: Signal
    quantity: float
    confidence: float = Field(ge=0.0, le=1.0)
    thesis: str
    cited_reports: list[str] = []           # agent names this thesis relies on


class Objection(BaseModel):
    id: str
    text: str


class Rebuttal(BaseModel):
    objection_id: str
    response: str


class RiskVerdict(BaseModel):
    action: RiskAction
    approved_quantity: float
    rules_triggered: list[str] = []
    note: str = ""


class Position(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float


class PortfolioState(BaseModel):
    cash: float
    positions: list[Position] = []
    equity: float                            # cash + market value of positions


class Order(BaseModel):
    ticker: str
    signal: Signal
    quantity: float
    client_order_id: str | None = None  # idempotency key — prevents double-orders on retry
    status: OrderStatus = OrderStatus.SUBMITTED
    fill_price: float | None = None
    filled_at: datetime | None = None


class RunRecord(BaseModel):
    """One full pipeline cycle — the audit trail unit. Answers 'why did we trade X on date Y'."""
    run_id: str
    strategy: str = "momentum"  # momentum | earnings — scored separately in reports
    started_at: datetime = Field(default_factory=utcnow)
    reports: list[AgentReport] = []
    proposal: TradeProposal | None = None
    objections: list[Objection] = []
    rebuttals: list[Rebuttal] = []
    verdict: RiskVerdict | None = None
    order: Order | None = None
    portfolio_after: PortfolioState | None = None
    benchmark_value: float | None = None
    notes: list[str] = []
