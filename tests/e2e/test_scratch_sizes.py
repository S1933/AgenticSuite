"""E2E scratch — format_bytes must round-trip correctly (real bug on main)."""

from __future__ import annotations

import pytest

from scratch.sizes import format_bytes

pytestmark = pytest.mark.e2e


def test_binary_kib() -> None:
    assert format_bytes(1024, binary=True) == "1.0 KiB"


def test_binary_mib() -> None:
    assert format_bytes(1024 * 1024, binary=True) == "1.0 MiB"


def test_binary_gib() -> None:
    assert format_bytes(1024**3, binary=True) == "1.0 GiB"


def test_decimal_units_convert() -> None:
    """Non-binary mode must convert to KB/MB with divisor 1000."""
    assert format_bytes(1500, binary=False) == "1.5 KB"


def test_decimal_megabytes() -> None:
    assert format_bytes(1_500_000, binary=False) == "1.5 MB"