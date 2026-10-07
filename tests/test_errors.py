# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
from __future__ import annotations

from pathlib import Path

import pytest

from opera_vlm.errors import ERROR_CODES, InputValidationError

DOC = Path(__file__).parents[1] / "docs" / "error-codes.md"


def test_every_error_code_is_documented():
    text = DOC.read_text()
    missing = [code for code in ERROR_CODES if f"| {code} |" not in text]
    assert not missing, f"document these codes in {DOC}: {missing}"


def test_undocumented_code_rejected():
    with pytest.raises(ValueError):
        InputValidationError("x", 9999)
