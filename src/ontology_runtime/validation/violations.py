"""The single violation shape returned by every validation layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Violation:
    code: str
    path: str
    message: str
    objectType: str | None = None
    objectRef: str | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "severity": self.severity,
        }
        if self.objectType:
            payload["objectType"] = self.objectType
        if self.objectRef:
            payload["objectRef"] = self.objectRef
        return payload


@dataclass
class ViolationList:
    items: list[Violation] = field(default_factory=list)

    def add(self, code: str, path: str, message: str, **extra: Any) -> None:
        self.items.append(Violation(code=code, path=path, message=message, **extra))

    def extend(self, other: ViolationList) -> None:
        self.items.extend(other.items)

    @property
    def ok(self) -> bool:
        return not self.items

    def to_dicts(self) -> list[dict[str, Any]]:
        return [v.to_dict() for v in self.items]

    def __len__(self) -> int:
        return len(self.items)
