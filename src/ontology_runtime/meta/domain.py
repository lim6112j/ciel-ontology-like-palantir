"""Domain manifest: the identity of one business domain.

Each `ontology/domains/<name>/domain.yaml` declares how the domain is named,
which RID namespace it mints, and where its Python implementations live. The
runtime loads the manifest before the domain's definitions so the rest of the
stack never has to read a global setting to know which domain it is serving.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, model_validator

#: A domain name is a lowercase slug; it becomes a directory name and API prefix.
DOMAIN_NAME_PATTERN = r"^[a-z][a-z0-9]*$"
#: The generated client base must be `/api/<domain>` so the dev proxy can rewrite it.
API_BASE_PATTERN = re.compile(r"^/api/([a-z][a-z0-9]*)$")


class WebConfig(BaseModel):
    """How the domain appears in the web console."""

    model_config = {"extra": "forbid"}

    enabled: bool = True
    #: Landing-page sort order; lower comes first.
    order: int = 100
    tagline: str = ""
    #: Path prefix the generated client calls, e.g. `/api/liquor`.
    apiBase: str | None = None
    #: Dev proxy target for this domain's backend instance.
    backendUrl: str = "http://localhost:8000"

    @model_validator(mode="after")
    def _check_api_base(self) -> WebConfig:
        if self.apiBase is not None and not API_BASE_PATTERN.match(self.apiBase):
            raise ValueError(f"web.apiBase must match /api/<domain>, got {self.apiBase!r}")
        return self


class DomainManifest(BaseModel):
    model_config = {"extra": "forbid"}

    apiName: str = Field(pattern=DOMAIN_NAME_PATTERN)
    displayName: str
    description: str | None = None
    #: RID prefix: ri.<ridNamespace>.object.<type>.<id>
    ridNamespace: str | None = None
    #: Dotted module path holding this domain's Python implementations.
    pythonPackage: str | None = None
    web: WebConfig = Field(default_factory=WebConfig)

    @property
    def namespace(self) -> str:
        """The RID namespace, defaulting to the domain name."""
        return self.ridNamespace or self.apiName

    @property
    def web_api_base(self) -> str:
        return self.web.apiBase or f"/api/{self.apiName}"
