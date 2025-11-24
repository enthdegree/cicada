"""Signature payload implementation."""
from __future__ import annotations

import base64
import csv
import struct
import time
from dataclasses import dataclass
from typing import Iterable, List, Tuple
import warnings

import blst

from .base import Payload
from cicada.util import count_non_ascii
from cicada import speech

DST = b"BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_"	# domain separation tag

def _escape_csv_text_field(value: str) -> str:
	escaped = value.encode("unicode_escape").decode("ascii")
	return (
		escaped.replace(",", "\\u002c")
		.replace("\"", "\\u0022")
		.replace("'", "\\u0027")
	)

def _unescape_csv_text_field(value: str) -> str:
	return bytes(value, "utf-8").decode("unicode_escape")

@dataclass
class SignaturePayloadHeader:
	timestamp: float
	word_count: int
	message: str

	@classmethod
	def from_bytes(cls, ch: bytes, n_header_message_chars: int = 11):
		ts_bytes = ch[0:4]
		timestamp = float(struct.unpack(">I", ts_bytes)[0])
		wc_bytes = ch[4:5]
		word_count = struct.unpack(">B", wc_bytes)[0]
		header_bytes = ch[5:(5 + n_header_message_chars)]
		header_message = header_bytes.rstrip(b"\x00").decode("ascii", errors="replace")
		return cls(timestamp, word_count, header_message)

	def to_bytes(self, n_header_message_chars: int = 11):
		timestamp_bytes = struct.pack(">I", int(self.timestamp))
		word_count_bytes = struct.pack(">B", self.word_count)
		message = self.message.encode("ascii", errors="replace")
		if len(message) > n_header_message_chars:
			warnings.warn(
				f"header_message too long ({len(message)} bytes); truncating to {n_header_message_chars} bytes",
				UserWarning,
			)
			message = message[:n_header_message_chars]
		message_bytes = message.ljust(n_header_message_chars, b"\x00")
		return timestamp_bytes + word_count_bytes + message_bytes

class SignaturePayload(Payload):
	payload_type = "signature"
	requires_bls_keys = True
	needs_transcript = True

	header: SignaturePayloadHeader
	bls_signature: bytes

	@classmethod
	def from_transcript(cls, chunk_text: str, **kwargs) -> "SignaturePayload":
		header_message = kwargs.get("header_message")
		bls_privkey: blst.SecretKey | None = kwargs.get("bls_privkey")
		bls_pubkey_bytes: bytes | None = kwargs.get("bls_pubkey_bytes")
		ts = kwargs.get("timestamp", time.time())
		if not header_message or bls_privkey is None or bls_pubkey_bytes is None:
			raise ValueError("SignaturePayload.from_transcript requires header_message, bls_privkey, and bls_pubkey_bytes.")
		l_tokens = speech.regularize_transcript(chunk_text)
		pl = cls.__new__(cls)
		pl.header = SignaturePayloadHeader(ts, len(l_tokens), header_message)
		pl.bls_signature = pl.calculate_signature(l_tokens, bls_privkey, bls_pubkey_bytes)
		return pl

	@classmethod
	def from_bytes(cls, pl_bytes: bytes, n_header_message_chars: int = 11, **kwargs) -> "SignaturePayload":
		pl = cls.__new__(cls)
		pl.header = SignaturePayloadHeader.from_bytes(pl_bytes, n_header_message_chars=n_header_message_chars)
		pl.bls_signature = bytes(pl_bytes[(5 + n_header_message_chars):(5 + n_header_message_chars + 48)])
		return pl

	@classmethod
	def decode_frames(cls, l_frames: List[bytes], l_start_idx: List[int], discard_threshold: int = 0, **kwargs):
		payloads: List[SignaturePayload] = []
		starts: List[int] = []
		for frame, start in zip(l_frames, l_start_idx):
			pl = cls.from_bytes(frame, **kwargs)
			if count_non_ascii(pl.header.message) <= discard_threshold:
				payloads.append(pl)
				starts.append(start)
		return payloads, starts

	@classmethod
	def write_csv(cls, l_payloads: List[Payload], l_sam_idx: List[int] = None, out_csv: str = "out.csv", **kwargs):
		if l_sam_idx is None:
			l_sam_idx = [-1] * len(l_payloads)
		with open(out_csv, "w", newline="") as f:
			writer = csv.writer(f)
			writer.writerow(["frame_start_sam", "timestamp", "word_count", "header_message", "bls_signature"])
			for pl, sam_idx in zip(l_payloads, l_sam_idx):
				pl_sig: SignaturePayload = pl  # type: ignore[assignment]
				ts_field = f"{int(pl_sig.header.timestamp):010d}"
				wc_field = str(pl_sig.header.word_count)
				header_field = _escape_csv_text_field(pl_sig.header.message)
				sig_b64 = base64.b64encode(pl_sig.bls_signature).decode("ascii")
				writer.writerow([sam_idx, ts_field, wc_field, header_field, sig_b64])

	@classmethod
	def load_csv(cls, in_csv: str, **kwargs) -> Tuple[List[Payload], List[int]]:
		l_payloads: List[Payload] = []
		l_sam_idx: List[int] = []
		with open(in_csv, newline="") as f:
			reader = csv.DictReader(f)
			for row in reader:
				sam_idx = int(row["frame_start_sam"])
				ts = int(row["timestamp"])
				wc = int(row["word_count"])
				header_message = _unescape_csv_text_field(row["header_message"])
				sig_b64 = row["bls_signature"]
				bls_sig = base64.b64decode(sig_b64)

				pl = cls.__new__(cls)
				hdr = SignaturePayloadHeader.__new__(SignaturePayloadHeader)
				hdr.timestamp = float(ts)
				hdr.word_count = wc
				hdr.message = header_message
				pl.header = hdr
				pl.bls_signature = bls_sig

				l_payloads.append(pl)
				l_sam_idx.append(sam_idx)
		return l_payloads, l_sam_idx

	def to_bytes(self, n_header_message_chars: int = 11):
		header_bytes = self.header.to_bytes(n_header_message_chars=n_header_message_chars)
		return header_bytes + self.bls_signature

	def calculate_signature(self, l_tokens: Iterable, bls_privkey: blst.SecretKey, bls_pubkey_bytes: bytes) -> bytes:
		header_bytes = self.header.to_bytes()
		msg = bytearray(header_bytes)
		for tok in l_tokens:
			msg += (tok.text.encode("utf-8") + b"\x00")
		sig = blst.P1().hash_to(msg, DST, bls_pubkey_bytes).sign_with(bls_privkey).compress()
		return sig

	def match_chunk(self, chunk_text: str, bls_pubkey_bytes: bytes = None, n_header_message_chars: int = 11, **kwargs) -> int:
		if bls_pubkey_bytes is None:
			raise ValueError("SignaturePayload.match_chunk requires bls_pubkey_bytes.")
		l_tokens = speech.regularize_transcript(chunk_text)
		word_count = self.header.word_count
		if len(l_tokens) < word_count:
			warnings.warn("Not enough tokens in this chunk to match this payload.", UserWarning)
			return -1
		try:
			pl_sig = blst.P1_Affine(bytearray(self.bls_signature))
		except Exception:
			warnings.warn("Corrupted payload signature.", UserWarning)
			return -1
		bls_pubkey = blst.P2_Affine(bls_pubkey_bytes)
		header_bytes = self.header.to_bytes(n_header_message_chars=n_header_message_chars)
		for idx in range(len(l_tokens) - word_count + 1):
			msg = bytearray(header_bytes)
			for tok in l_tokens[idx:(idx + word_count)]:
				msg += (tok.text.encode("utf-8") + b"\x00")
			try:
				ctx = blst.Pairing(True, DST)
				ctx.aggregate(bls_pubkey, pl_sig, msg, bls_pubkey_bytes)
				ctx.commit()
				if ctx.finalverify():
					return idx
			except Exception:
				continue
		return -1

	def describe(self, start_sam: int | None, wav_fs_Hz: float) -> str:
		start_desc = f"sample {start_sam}" if start_sam is not None else "unknown sample"
		start_sec = (start_sam / wav_fs_Hz) if (start_sam is not None and wav_fs_Hz) else None
		ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.header.timestamp))
		return (
			f"BLS signature payload near {start_desc}" 
			f"{f' ({start_sec:.2f} sec)' if start_sec is not None else ''}. "
			f"header='{self.header.message}', "
			f"timestamp={ts_str} UTC, "
			f"words={self.header.word_count}, "
			f"signature={self.bls_signature.hex()}"
		)