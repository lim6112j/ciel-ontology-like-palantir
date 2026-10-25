"""Typed error hierarchy mapped to HTTP status codes by the API layer."""

from __future__ import annotations

from typing import Any


class OntologyError(Exception):
    """Base class for all ontology runtime errors."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class SchemaError(OntologyError):
    status_code = 500
    code = "schema_error"


class NotFoundError(OntologyError):
    status_code = 404
    code = "not_found"


class ConflictError(OntologyError):
    status_code = 409
    code = "conflict"


class ValidationFailed(OntologyError):
    status_code = 422
    code = "validation_failed"

    def __init__(self, violations: list[dict[str, Any]]) -> None:
        super().__init__("validation failed", violations=violations)
        self.violations = violations


class ActionNotFound(NotFoundError):
    code = "action_not_found"


class FunctionNotFound(NotFoundError):
    code = "function_not_found"


class ObjectTypeNotFound(NotFoundError):
    code = "object_type_not_found"


class LinkTypeNotFound(NotFoundError):
    code = "link_type_not_found"


class IdempotencyConflict(ConflictError):
    code = "idempotency_conflict"


class VersionConflict(ConflictError):
    code = "version_conflict"


class _ProposalStateError(ConflictError):
    code = "proposal_state_invalid"


class PolicyViolation(OntologyError):
    status_code = 403
    code = "policy_violation"
