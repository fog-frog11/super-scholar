from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..models import ScholarlyDataSettings
from ..security import decrypt_secret, encrypt_secret, secret_hint


@dataclass(frozen=True)
class ScholarlyRuntime:
    openalex_enabled: bool
    openalex_api_key: str
    openalex_max_results: int
    crossref_enabled: bool
    crossref_email: str
    crossref_api_key: str
    semantic_scholar_enabled: bool
    semantic_scholar_api_key: str
    dblp_enabled: bool
    clarivate_enabled: bool
    clarivate_api_key: str
    clarivate_journal_limit: int
    request_timeout_seconds: int
    source: Literal["ui", "environment"]

    @property
    def any_live_source_enabled(self) -> bool:
        return any((self.openalex_enabled, self.crossref_enabled, self.semantic_scholar_enabled, self.dblp_enabled, self.clarivate_enabled))


def _environment_runtime(settings: Settings | None = None) -> ScholarlyRuntime:
    settings = settings or get_settings()
    return ScholarlyRuntime(
        openalex_enabled=True,
        openalex_api_key=settings.openalex_api_key.strip(),
        openalex_max_results=max(10, min(int(settings.openalex_max_results), 50)),
        crossref_enabled=True,
        crossref_email=settings.crossref_email.strip(),
        crossref_api_key=settings.crossref_api_key.strip(),
        semantic_scholar_enabled=True,
        semantic_scholar_api_key=settings.semantic_scholar_api_key.strip(),
        dblp_enabled=True,
        clarivate_enabled=bool(settings.clarivate_journals_api_key.strip()),
        clarivate_api_key=settings.clarivate_journals_api_key.strip(),
        clarivate_journal_limit=max(6, min(int(settings.clarivate_journal_limit), 80)),
        request_timeout_seconds=max(5, min(int(settings.scholarly_request_timeout_seconds), 120)),
        source="environment",
    )


def load_scholarly_runtime(db: Session, settings: Settings | None = None) -> ScholarlyRuntime:
    row = db.get(ScholarlyDataSettings, 1)
    if row is None:
        return _environment_runtime(settings)
    return ScholarlyRuntime(
        openalex_enabled=bool(row.openalex_enabled),
        openalex_api_key=decrypt_secret(row.openalex_api_key_encrypted),
        openalex_max_results=max(10, min(int(row.openalex_max_results), 50)),
        crossref_enabled=bool(row.crossref_enabled),
        crossref_email=str(row.crossref_email or "").strip(),
        crossref_api_key=decrypt_secret(row.crossref_api_key_encrypted),
        semantic_scholar_enabled=bool(row.semantic_scholar_enabled),
        semantic_scholar_api_key=decrypt_secret(row.semantic_scholar_api_key_encrypted),
        dblp_enabled=bool(row.dblp_enabled),
        clarivate_enabled=bool(row.clarivate_enabled),
        clarivate_api_key=decrypt_secret(row.clarivate_api_key_encrypted),
        clarivate_journal_limit=max(6, min(int(row.clarivate_journal_limit), 80)),
        request_timeout_seconds=max(5, min(int(row.request_timeout_seconds), 120)),
        source="ui",
    )


def save_scholarly_runtime(db: Session, payload: Any, settings: Settings | None = None) -> ScholarlyRuntime:
    row = db.get(ScholarlyDataSettings, 1)
    current = load_scholarly_runtime(db, settings)
    if row is None:
        row = ScholarlyDataSettings(id=1)
        db.add(row)

    row.openalex_enabled = bool(payload.openalex_enabled)
    row.openalex_max_results = max(10, min(int(payload.openalex_max_results), 50))
    if payload.openalex_api_key is not None:
        value = payload.openalex_api_key.strip()
        row.openalex_api_key_encrypted = encrypt_secret(value) if value else None
    elif row.openalex_api_key_encrypted is None and current.openalex_api_key:
        row.openalex_api_key_encrypted = encrypt_secret(current.openalex_api_key)

    row.crossref_enabled = bool(payload.crossref_enabled)
    row.crossref_email = payload.crossref_email.strip()
    if payload.crossref_api_key is not None:
        value = payload.crossref_api_key.strip()
        row.crossref_api_key_encrypted = encrypt_secret(value) if value else None
    elif row.crossref_api_key_encrypted is None and current.crossref_api_key:
        row.crossref_api_key_encrypted = encrypt_secret(current.crossref_api_key)

    row.semantic_scholar_enabled = bool(payload.semantic_scholar_enabled)
    if payload.semantic_scholar_api_key is not None:
        value = payload.semantic_scholar_api_key.strip()
        row.semantic_scholar_api_key_encrypted = encrypt_secret(value) if value else None
    elif row.semantic_scholar_api_key_encrypted is None and current.semantic_scholar_api_key:
        row.semantic_scholar_api_key_encrypted = encrypt_secret(current.semantic_scholar_api_key)

    row.dblp_enabled = bool(payload.dblp_enabled)
    row.clarivate_enabled = bool(payload.clarivate_enabled)
    row.clarivate_journal_limit = max(6, min(int(payload.clarivate_journal_limit), 80))
    if payload.clarivate_api_key is not None:
        value = payload.clarivate_api_key.strip()
        row.clarivate_api_key_encrypted = encrypt_secret(value) if value else None
    elif row.clarivate_api_key_encrypted is None and current.clarivate_api_key:
        row.clarivate_api_key_encrypted = encrypt_secret(current.clarivate_api_key)
    row.request_timeout_seconds = max(5, min(int(payload.request_timeout_seconds), 120))
    db.commit()
    db.refresh(row)
    return load_scholarly_runtime(db, settings)


def scholarly_runtime_to_public(runtime: ScholarlyRuntime, *, last_test: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "openalexEnabled": runtime.openalex_enabled,
        "openalexApiKeyConfigured": bool(runtime.openalex_api_key),
        "openalexApiKeyHint": secret_hint(runtime.openalex_api_key),
        "openalexMaxResults": runtime.openalex_max_results,
        "crossrefEnabled": runtime.crossref_enabled,
        "crossrefEmail": runtime.crossref_email,
        "crossrefApiKeyConfigured": bool(runtime.crossref_api_key),
        "crossrefApiKeyHint": secret_hint(runtime.crossref_api_key),
        "semanticScholarEnabled": runtime.semantic_scholar_enabled,
        "semanticScholarApiKeyConfigured": bool(runtime.semantic_scholar_api_key),
        "semanticScholarApiKeyHint": secret_hint(runtime.semantic_scholar_api_key),
        "dblpEnabled": runtime.dblp_enabled,
        "clarivateEnabled": runtime.clarivate_enabled,
        "clarivateApiKeyConfigured": bool(runtime.clarivate_api_key),
        "clarivateApiKeyHint": secret_hint(runtime.clarivate_api_key),
        "clarivateJournalLimit": runtime.clarivate_journal_limit,
        "requestTimeoutSeconds": runtime.request_timeout_seconds,
        "source": runtime.source,
        "lastTest": last_test,
    }


def load_last_scholarly_test(db: Session) -> dict[str, Any] | None:
    row = db.get(ScholarlyDataSettings, 1)
    return row.last_test_json if row is not None else None


def update_last_scholarly_test(db: Session, result: dict[str, Any], settings: Settings | None = None) -> None:
    row = db.get(ScholarlyDataSettings, 1)
    if row is None:
        # Preserve environment-backed credentials/options when the diagnostic API
        # is invoked before the user has ever saved the UI form. Creating a bare
        # default row here would otherwise shadow valid environment configuration.
        current = _environment_runtime(settings)
        row = ScholarlyDataSettings(
            id=1,
            openalex_enabled=current.openalex_enabled,
            openalex_api_key_encrypted=encrypt_secret(current.openalex_api_key) if current.openalex_api_key else None,
            openalex_max_results=current.openalex_max_results,
            crossref_enabled=current.crossref_enabled,
            crossref_email=current.crossref_email,
            crossref_api_key_encrypted=encrypt_secret(current.crossref_api_key) if current.crossref_api_key else None,
            semantic_scholar_enabled=current.semantic_scholar_enabled,
            semantic_scholar_api_key_encrypted=encrypt_secret(current.semantic_scholar_api_key) if current.semantic_scholar_api_key else None,
            dblp_enabled=current.dblp_enabled,
            clarivate_enabled=current.clarivate_enabled,
            clarivate_api_key_encrypted=encrypt_secret(current.clarivate_api_key) if current.clarivate_api_key else None,
            clarivate_journal_limit=current.clarivate_journal_limit,
            request_timeout_seconds=current.request_timeout_seconds,
        )
        db.add(row)
    row.last_test_json = result
    db.commit()
