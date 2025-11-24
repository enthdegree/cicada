"""Plaintext payload implementation."""
from __future__ import annotations

import csv
from typing import List, Tuple

from .base import Payload
from .signature import _escape_csv_text_field, _unescape_csv_text_field
from cicada.util import count_non_ascii

class PlaintextPayload(Payload):
	payload_type = "plaintext"
	requires_bls_keys = False
	needs_transcript = False

	content: str

	@classmethod
	def from_transcript(cls, chunk_text: str, **kwargs):
		pl = cls.__new__(cls)
		pl.content = chunk_text
		return pl

	@classmethod
	def from_string(cls, s: str, **kwargs):
		return cls.from_transcript(s, **kwargs)

	@classmethod
	def from_bytes(cls, pl_bytes: bytes, **kwargs):
		pl = cls.__new__(cls)
		pl.content = pl_bytes.decode("ascii", errors="replace")
		return pl

	@classmethod
	def write_csv(cls, l_payloads: List[Payload], l_sam_idx: List[int] = None, out_csv: str = "out.csv", **kwargs):
		if l_sam_idx is None:
			l_sam_idx = [-1] * len(l_payloads)
		with open(out_csv, "w", newline="") as f:
			writer = csv.writer(f)
			writer.writerow(["frame_start_sam", "content"])
			for pl, sam_idx in zip(l_payloads, l_sam_idx):
				pl_pt: PlaintextPayload = pl  # type: ignore[assignment]
				content_field = _escape_csv_text_field(pl_pt.content)
				writer.writerow([sam_idx, content_field])

	@classmethod
	def load_csv(cls, in_csv: str, **kwargs):
		l_payloads: List[Payload] = []
		l_sam_idx: List[int] = []
		with open(in_csv, newline="") as f:
			reader = csv.DictReader(f)
			for row in reader:
				sam_idx = int(row["frame_start_sam"])
				content = _unescape_csv_text_field(row["content"])
				pl = cls.__new__(cls)
				pl.content = content
				l_payloads.append(pl)
				l_sam_idx.append(sam_idx)
		return l_payloads, l_sam_idx

	@classmethod
	def filter_payloads(cls, payloads: List["Payload"], starts: List[int], ascii_threshold: int = 4, **kwargs):
		filtered_payloads: List[Payload] = []
		filtered_starts: List[int] = []
		for pl, start in zip(payloads, starts):
			pl_pt: PlaintextPayload = pl  # type: ignore[assignment]
			if count_non_ascii(pl_pt.content) <= ascii_threshold:
				filtered_payloads.append(pl_pt)
				filtered_starts.append(start)
		return filtered_payloads, filtered_starts

	def to_bytes(self):
		return self.content.encode("ascii", errors="replace")

	def describe(self, start_sam: int | None, wav_fs_Hz: float) -> str:
		start_desc = f"sample {start_sam}" if start_sam is not None else "unknown sample"
		start_sec = (start_sam / wav_fs_Hz) if (start_sam is not None and wav_fs_Hz) else None
		return (
			f"Plaintext payload near {start_desc}"
			f"{f' ({start_sec:.2f} sec)' if start_sec is not None else ''}. "
			f"Content: {self.content}"
		)

	def match_chunk(self, chunk_text: str, **kwargs) -> int: return -1

	@classmethod
	def decode_frames(cls, l_frames: List[bytes], l_start_idx: List[int], discard_threshold: int = 0, **kwargs):
		payloads = [cls.from_bytes(frame) for frame in l_frames]
		return cls.filter_payloads(payloads, l_start_idx, ascii_threshold=discard_threshold)
