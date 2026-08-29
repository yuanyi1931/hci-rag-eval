from __future__ import annotations

from pathlib import Path

import pytest

import src.generate as generate_module


@pytest.fixture(autouse=True)
def _protect_real_outputs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent any test from writing into the project's real outputs/ directory.

    src.generate.generate_insights() writes to a module-level OUTPUT_PATH constant
    that points at the real outputs/generations.jsonl by default. If a test calls
    generate_insights() (directly or transitively) without redirecting this path,
    it silently overwrites production pipeline output. This fixture redirects the
    write target to an isolated tmp_path for every test, with no per-test opt-in
    required.
    """
    fake_outputs_dir = tmp_path / "outputs"
    fake_outputs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(generate_module, "OUTPUT_PATH", fake_outputs_dir / "generations.jsonl")
