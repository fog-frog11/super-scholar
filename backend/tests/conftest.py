from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SUPER_SCHOLAR_ENVIRONMENT", "test")
os.environ.setdefault("SUPER_SCHOLAR_DATABASE_URL", "sqlite:///./data/test_super_scholar.db")
os.environ.setdefault("SUPER_SCHOLAR_STORAGE_DIR", "./storage-test")


def pytest_sessionfinish(session, exitstatus):  # type: ignore[no-untyped-def]
    Path("./data/test_super_scholar.db").unlink(missing_ok=True)
