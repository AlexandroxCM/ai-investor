"""Tiny .env loader — no dependency needed. Reads KEY=VALUE lines from the
project-root .env file into the environment. Real environment variables
always win over file values, and the file never gets committed (.gitignore)."""
from __future__ import annotations

import os
from pathlib import Path


def load_env(project_root: Path) -> None:
    env_file = project_root / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
