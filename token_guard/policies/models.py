from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PolicyContext:
    user_id: str
    model: str = "default"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.total_tokens == 0 and (self.input_tokens > 0 or self.output_tokens > 0):
            object.__setattr__(self, "total_tokens", self.input_tokens + self.output_tokens)


@dataclass
class PolicyResult:
    allowed: bool
    reason: Optional[str] = None
    retry_after: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
