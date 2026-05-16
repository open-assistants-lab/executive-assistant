import os
import shutil
from pathlib import Path

import pytest

TEST_DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def chroma_tmp_path(tmp_path):
    p = str(tmp_path / "chroma_memory")
    yield p
    if os.path.exists(p):
        shutil.rmtree(p, ignore_errors=True)


@pytest.fixture
def hybrid_tmp_path(tmp_path):
    p = str(tmp_path / "hybrid_memory")
    yield p
    if os.path.exists(p):
        shutil.rmtree(p, ignore_errors=True)


@pytest.fixture
def sample_messages():
    return [
        {"role": "user", "content": "My name is Alice. I live in Denver."},
        {"role": "assistant", "content": "Nice to meet you, Alice from Denver!"},
        {"role": "user", "content": "I love building model kits. Finished a Spitfire and an F-15."},
        {"role": "assistant", "content": "That's impressive! Two kits completed."},
        {"role": "user", "content": "Just bought a B-29 bomber and a 69 Camaro kit."},
        {"role": "user", "content": "My current project is a Tiger I tank."},
    ]
