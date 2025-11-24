"""Base payload interface and helpers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
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
	def tokenize_text(cls, chunk_text: str) -> List["TranscriptToken"]:
		"""Return token list with character offsets; subclasses may override."""
		tokens: List[TranscriptToken] = []
		search_start = 0
		for tok in chunk_text.split():
			idx = chunk_text.find(tok, search_start)
			idx = idx if idx >= 0 else search_start
			tokens.append(TranscriptToken(text=tok, idx=idx))
			search_start = idx + len(tok)
		return tokens

	@classmethod
	@abstractmethod
	def from_transcript(cls, chunk_text: str, **kwargs) -> "Payload":
		"""Create a payload from a text transcript chunk."""
		raise NotImplementedError

	@classmethod
	@abstractmethod
	def from_bytes(cls, pl_bytes: bytes, **kwargs) -> "Payload":
		raise NotImplementedError

	@classmethod
	@abstractmethod
	def write_csv(cls, l_payloads: List["Payload"], l_sam_idx: List[int], out_csv: str, **kwargs):
		"""Write a list of payloads and their start sample indices to a CSV file."""
		raise NotImplementedError

	@classmethod
	@abstractmethod
	def load_csv(cls, in_csv: str, **kwargs) -> Tuple[List["Payload"], List[int]]:
		"""Load a list of payloads and their start sample indices from a CSV file."""
		raise NotImplementedError

	@abstractmethod
	def to_bytes(self) -> bytes:
		raise NotImplementedError

	@abstractmethod
	def describe(self, start_sam: int | None, wav_fs_Hz: float) -> str:
		raise NotImplementedError
	
	@abstractmethod
	def annotate_chunk(self, chunk_text: str, l_payloads, l_payload_start_sam, wav_fs_Hz=44100) -> str:
		"""Given a transcript string (chunk_text) and a list of payloads, find where those payloads 
		match the transcript string, and produce an annotated version describing the matches. 
		Returns a string with annotated markdown.
		"""
		raise NotImplementedError

	@abstractmethod
	def make_footnote(self, slug: int, start_sam: int | None, wav_fs_Hz: float = 44100.0) -> str:
		"""Create a self-describing footnote for text transcript annotation.
		 Something like "[2]: Payload at timestamp {start_sam} matched the transcript with the following info..." 
		 """
		raise NotImplementedError

def payload_type_choices() -> Tuple[str, ...]:
	return tuple(sorted(Payload.choices()))
