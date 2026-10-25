"""Edit batch primitives: the single representation of pending writes."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EditKind(StrEnum):
    OBJECT_CREATE = "createObject"
    OBJECT_MODIFY = "modifyObject"
    OBJECT_DELETE = "deleteObject"
    LINK_CREATE = "createLink"
    LINK_DELETE = "deleteLink"


@dataclass
class ObjectCreate:
    object_type: str
    rid: str
    properties: dict[str, Any]


@dataclass
class ObjectModify:
    object_type: str
    rid: str
    properties: dict[str, Any]
    before: dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectDelete:
    object_type: str
    rid: str
    before: dict[str, Any] = field(default_factory=dict)


@dataclass
class LinkCreate:
    link_type: str
    from_rid: str
    to_rid: str


@dataclass
class LinkDelete:
    link_type: str
    from_rid: str
    to_rid: str


Edit = ObjectCreate | ObjectModify | ObjectDelete | LinkCreate | LinkDelete

EDIT_KIND_OF: dict[type, EditKind] = {
    ObjectCreate: EditKind.OBJECT_CREATE,
    ObjectModify: EditKind.OBJECT_MODIFY,
    ObjectDelete: EditKind.OBJECT_DELETE,
    LinkCreate: EditKind.LINK_CREATE,
    LinkDelete: EditKind.LINK_DELETE,
}


@dataclass
class EditBatch:
    """Ordered list of edits. Every action, declarative or function-backed, produces one."""

    edits: list[Edit] = field(default_factory=list)

    def append(self, edit: Edit) -> Edit:
        self.edits.append(edit)
        return edit

    def extend(self, other: EditBatch) -> None:
        self.edits.extend(other.edits)

    def __len__(self) -> int:
        return len(self.edits)

    def __iter__(self) -> Iterator[Edit]:
        return iter(self.edits)

    def touched_object_rids(self) -> set[str]:
        rids: set[str] = set()
        for edit in self.edits:
            if isinstance(edit, ObjectCreate | ObjectModify | ObjectDelete):
                rids.add(edit.rid)
        return rids

    def created_rids_by_type(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for edit in self.edits:
            if isinstance(edit, ObjectCreate):
                result.setdefault(edit.object_type, []).append(edit.rid)
        return result
