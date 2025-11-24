"""Base payload interface and helpers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Type, Tuple, List

class Payload(ABC):
	"""Base interface for all payload types."""
	payload_type: str = "base"
	requires_bls_keys: bool = False
	needs_transcript: bool = False
	_registry: Dict[str, Type["Payload"]] = {}

	def __init_subclass__(cls, **kwargs):
		super().__init_subclass__(**kwargs)
		if getattr(cls, "payload_type", None):
			Payload._registry[cls.payload_type] = cls

	@classmethod
	def get_class(cls, payload_type: str) -> Type["Payload"]:
		try:
			return cls._registry[payload_type]
		except KeyError as exc:
			raise ValueError(f"Unknown payload type '{payload_type}'") from exc

	@classmethod
	def choices(cls) -> Tuple[str, ...]:
		return tuple(cls._registry.keys())

	@classmethod
	def decode_frames(cls, l_frames: List[bytes], l_start_idx: List[int], **kwargs) -> Tuple[List["Payload"], List[int]]:
		payloads = [cls.from_bytes(frame, **kwargs) for frame in l_frames]
		return payloads, list(l_start_idx)

	@classmethod
	def filter_payloads(cls, payloads: List["Payload"], starts: List[int], **kwargs) -> Tuple[List["Payload"], List[int]]:
		return payloads, starts

	@classmethod
	@abstractmethod
	def from_transcript(cls, chunk_text: str, **kwargs) -> "Payload":
		raise NotImplementedError

	@classmethod
	@abstractmethod
	def from_bytes(cls, pl_bytes: bytes, **kwargs) -> "Payload":
		raise NotImplementedError

	@classmethod
	@abstractmethod
	def write_csv(cls, l_payloads: List["Payload"], l_sam_idx: List[int], out_csv: str, **kwargs):
		raise NotImplementedError

	@classmethod
	@abstractmethod
	def load_csv(cls, in_csv: str, **kwargs) -> Tuple[List["Payload"], List[int]]:
		raise NotImplementedError

	@abstractmethod
	def to_bytes(self) -> bytes:
		raise NotImplementedError

	def match_chunk(self, chunk_text: str, **kwargs) -> int:
		return -1

	@abstractmethod
	def describe(self, start_sam: int | None, wav_fs_Hz: float) -> str:
		raise NotImplementedError

def get_payload_class(payload_type: str) -> Type[Payload]:
	return Payload.get_class(payload_type)

def payload_type_choices() -> Tuple[str, ...]:
	return tuple(sorted(Payload.choices()))
