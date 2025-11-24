"""Generic utility helpers."""
from __future__ import annotations

import base64

def count_non_ascii(s: str) -> int:
	return sum(1 for ch in s if ord(ch) > 127)
