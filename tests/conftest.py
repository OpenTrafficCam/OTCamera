import shutil
from pathlib import Path

import pytest


@pytest.fixture
def test_dir() -> Path:
    test_dir = Path(__file__).parent / "data"
    test_dir.mkdir(exist_ok=True)
    yield test_dir
    for f in test_dir.iterdir():
        try:
            f.unlink()
        except FileNotFoundError:
            shutil.rmtree(f)
