from enum import Enum


class Signal(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class RiskAction(str, Enum):
    APPROVE = "approve"
    RESIZE = "resize"
    REJECT = "reject"


class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    FILLED = "filled"
    REJECTED = "rejected"
