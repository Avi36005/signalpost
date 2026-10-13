from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def org_number(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{9}', value):
        raise ValueError('Organisation numbers must be nine-digit strings')
    check = 11 - sum(int(x)*w for x, w in zip(value[:8], [3, 2, 7, 6, 5, 4, 3, 2])) % 11
    if (0 if check == 11 else check) != int(value[-1]):
        raise ValueError('Invalid Norwegian organisation-number checksum')
    return value


class Availability(str, Enum):
    available = 'available'
    not_available = 'not_available'
    blocked = 'blocked'
    not_applicable = 'not_applicable'
    ambiguous = 'ambiguous'
    failed = 'failed'


class Evidence(BaseModel):
    id: str
    organisation_number: str
    source_url: str
    source_class: str
    retrieved_at: str
    content_sha256: str
    locator: str
    excerpt: str | None = None
    snapshot_path: str | None = None
    retention: str = 'permitted_open_data'
    extraction_method: str = 'aviscope-deterministic-v1'
    identity_basis: str


class Claim(BaseModel):
    id: str
    semantic_key: str
    field: str
    family: str
    value: Any
    availability: Availability = Availability.available
    evidence_ids: list[str] = Field(default_factory=list)
    period: dict | None = None
    effective_at: str | None = None
    currency: str | None = None
    original_unit: str | None = None
    scope: str = 'legal_entity'
    derived_from: list[str] = Field(default_factory=list)
    stale: bool = False
    first_observed_at: str
    last_observed_at: str


FAMILIES = ('legal_identity', 'brand', 'financials', 'financial_history', 'leadership', 'locations', 'group', 'website', 'company_profiles', 'jobs', 'public_activity')


class Profile(BaseModel):
    schema_version: str = 'aviscope-1'
    organisation_number: str
    name: str | None = None
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    source_snapshots: list[dict] = Field(default_factory=list)
    availability: dict[str, dict] = Field(default_factory=lambda: {k: {'state': 'not_available', 'reason': 'No supported evidence found', 'attempted_sources': []} for k in FAMILIES})
    identity_links: list[dict] = Field(default_factory=list)
    candidate_ledger: list[dict] = Field(default_factory=list)
    decisions: list[dict] = Field(default_factory=list)
    review_queue: list[dict] = Field(default_factory=list)
    changes: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    refresh: dict = Field(default_factory=dict)
    operations: dict = Field(default_factory=dict)
    researched_at: str = Field(default_factory=now)

    @model_validator(mode='after')
    def valid_evidence(self):
        org_number(self.organisation_number)
        ids = {e.id for e in self.evidence}
        if len(ids) != len(self.evidence):
            raise ValueError('Duplicate evidence IDs')
        if any(e.organisation_number != self.organisation_number for e in self.evidence):
            raise ValueError('Wrong-entity evidence')
        for c in self.claims:
            if not c.evidence_ids or not set(c.evidence_ids) <= ids:
                raise ValueError('Unresolved claim evidence')
            if c.value is None and c.availability == Availability.available:
                raise ValueError('Missing value marked available')
        return self


def add_claim(p: dict, family: str, field: str, value: Any, snapshot: dict, locator: str, *, period=None, currency=None, unit=None, scope='legal_entity', effective_at=None, key=None, excerpt=None, identity_basis='Exact organisation number in official endpoint and response') -> dict | None:
    if value is None:
        return None
    semantic = digest([p['organisation_number'], field, period, scope, key])
    ev_id = 'ev-' + digest([p['organisation_number'], snapshot['id'], locator])[:24]
    ev = Evidence(id=ev_id, organisation_number=p['organisation_number'], source_url=snapshot['final_url'], source_class=snapshot['source_class'], retrieved_at=snapshot['retrieved_at'], content_sha256=snapshot['content_sha256'], locator=locator, excerpt=excerpt, snapshot_path=snapshot.get('path'), retention=snapshot.get('retention', 'permitted_open_data'), identity_basis=identity_basis).model_dump(mode='json')
    if not any(e['id'] == ev_id for e in p['evidence']):
        p['evidence'].append(ev)
    claim = Claim(id='cl-' + digest([semantic, value, ev_id])[:24], semantic_key=semantic, field=field, family=family, value=value, evidence_ids=[ev_id], period=period, currency=currency, original_unit=unit, scope=scope, effective_at=effective_at, first_observed_at=snapshot['retrieved_at'], last_observed_at=snapshot['retrieved_at']).model_dump(mode='json')
    if not any(c['id'] == claim['id'] for c in p['claims']):
        p['claims'].append(claim)
    p['availability'][family].update(state='available', reason='Evidence-supported claims available')
    return claim
