from pathlib import Path

import pytest

from conciliacao.armazenamento import Armazenamento


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    return entrada


@pytest.fixture
def armazenamento(tmp_path: Path) -> Armazenamento:
    return Armazenamento(tmp_path / "estado.sqlite")
