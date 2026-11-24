from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_prefix="SUPER_SCHOLAR_",
        extra="ignore",
    )

    app_name: str = "Super Scholar Backend"
    api_prefix: str = "/api/v1"
    environment: str = "development"
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'super_scholar.db').as_posix()}"
    storage_dir: Path = BASE_DIR / "storage"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_upload_mb: int = 256
    outbound_timeout_seconds: float = 15.0
    venue_cache_ttl_hours: int = 6

    # OpenAlex is used only for scholarly semantic retrieval during venue recommendation.
    # A key is optional; when configured it increases the available daily API budget.
    openalex_api_key: str = ""
    # Deprecated compatibility input: OpenAlex no longer uses mailto for the polite pool.
    # It is retained only so old .env files keep loading; runtime requests ignore it.
    openalex_max_results: int = 50
    crossref_email: str = ""
    crossref_api_key: str = ""
    semantic_scholar_api_key: str = ""
    # Official Clarivate Web of Science Journals API. Access is optional and
    # requires an entitled API key from the Clarivate Developer Portal.
    clarivate_journals_api_key: str = ""
    clarivate_journal_limit: int = 36
    scholarly_request_timeout_seconds: int = 20

    tesseract_cmd: str = ""
    ocr_languages: str = "eng"
    ocr_min_native_text_chars: int = 80

    openai_api_key: str = ""
    openai_model: str = "gpt-5.6"
    openai_reasoning_effort: str = "medium"
    ai_streaming_enabled: bool = True
    ai_transport_profile: str = "auto"
    ai_max_text_chars: int = 220_000
    ai_max_visual_assets: int = 8
    ai_max_pdf_files: int = 2
    ai_file_expiry_seconds: int = 3600
    ai_max_output_tokens: int = 12_000
    ai_chunk_text_chars: int = 10_000
    ai_chunk_output_tokens: int = 1_800
    ai_synthesis_max_chars: int = 24_000
    ai_max_provider_calls: int = 8
    ai_visuals_per_chunk: int = 1
    ai_request_timeout_seconds: int = 180

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def ai_configured(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def clamped_file_expiry_seconds(self) -> int:
        return max(3600, min(int(self.ai_file_expiry_seconds), 2_592_000))


@lru_cache
def get_settings() -> Settings:
    return Settings()
