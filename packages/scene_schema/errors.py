"""Error types for scene validation, with a stable, LLM-repair-friendly
string representation."""
from __future__ import annotations

from pydantic import ValidationError


class SceneValidationError(Exception):
    """Wraps a Pydantic ValidationError (or a manual raise) with a
    formatted message suitable for both human debugging output and
    feeding back into the LLM repair loop (§14)."""

    def __init__(self, message: str, raw: ValidationError | None = None):
        super().__init__(message)
        self.message = message
        self.raw = raw

    @classmethod
    def from_pydantic(cls, exc: ValidationError) -> "SceneValidationError":
        lines = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            lines.append(f"[{loc}]: {err['msg']}")
        return cls("; ".join(lines), raw=exc)

    def as_repair_context(self) -> str:
        """Formatted specifically for the repair-loop prompt (§14) —
        short, specific, no stack trace noise."""
        return self.message
