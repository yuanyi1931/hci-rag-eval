import tempfile
from pathlib import Path
import pytest

import main


def test_reuse_flag_missing_file_raises(tmp_path):
    gens_path = tmp_path / "outputs" / "generations.jsonl"
    # Ensure file does not exist
    if gens_path.exists():
        gens_path.unlink()
    with pytest.raises(FileNotFoundError):
        main._maybe_load_generations(gens_path, reuse_flag=True)


def test_default_does_not_reuse_even_if_file_exists(tmp_path):
    gens_dir = tmp_path / "outputs"
    gens_dir.mkdir(exist_ok=True)
    gens_path = gens_dir / "generations.jsonl"
    # write a dummy content
    gens_path.write_text('{"query_id": 1}\n')
    # When reuse_flag is False, helper should return None (no reuse)
    res = main._maybe_load_generations(gens_path, reuse_flag=False)
    assert res is None
