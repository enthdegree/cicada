"""Data palyload structures."""
from __future__ import annotations
import warnings, time, struct, base64, csv, blst
from typing import Iterable
from dataclasses import dataclass

def _escape_csv_text_field(value: str) -> str:
	"""Encode arbitrary text into a CSV-safe ASCII representation."""
	escaped = value.encode("unicode_escape").decode("ascii")
	return (escaped
		.replace(",", "\\u002c")
		.replace("\"", "\\u0022")
		.replace("'", "\\u0027"))

def _unescape_csv_text_field(value: str) -> str:
	"""Undo _escape_csv_text_field."""
	return bytes(value, "utf-8").decode("unicode_escape")

DST = b"BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_"	# domain separation tag

@dataclass
class SignaturePayloadHeader: # 128-bit header structure for signature payloads; see DESIGN_NOTES.md 
	timestamp: float # bits 0-31; 32-bit big-endian unix timestamp 
	word_count: int # bits 32-39; 8-bit unsigned word count
	message: str # bits 40-127; 11-character ascii header message

	@classmethod
	def from_bytes(cls, ch: bytearray, n_header_message_chars: int = 11):
		ts_bytes = ch[0:4] 
		timestamp = float(struct.unpack(">I", ts_bytes)[0])

		wc_bytes = ch[4:5]
		word_count = struct.unpack(">B", wc_bytes)[0]

		header_bytes = ch[5:(5+n_header_message_chars)]
		header_message = header_bytes.rstrip(b"\x00").decode("ascii", errors="replace")
		return cls(timestamp, word_count, header_message)
	
	def to_bytes(self, n_header_message_chars: int = 11):
		timestamp_bytes = struct.pack(">I", int(self.timestamp))
		word_count_bytes = struct.pack(">B", self.word_count) 
		message = self.message.encode("ascii", errors="replace")
		if len(message) > n_header_message_chars:
			warnings.warn(f"header_message too long ({len(message)} bytes); truncating to {n_header_message_chars} bytes", UserWarning)
			message = message[:n_header_message_chars]
		message_bytes = message.ljust(n_header_message_chars, b"\x00") 
		return timestamp_bytes + word_count_bytes + message_bytes

class SignaturePayload: # 512-bit payload structure; see DESIGN_NOTES.md
	header: SignaturePayloadHeader # bits 0-127; 128-bit header
	bls_signature: bytes # bits 128-511; 384-bit BLS short signature
	
	@classmethod
	def from_token_list(cls, l_tokens: list, header_message: str, bls_privkey: blst.SecretKey, bls_pubkey_bytes: bytes, ts = time.time()):
		"""Construct a Payload from a list of tokens and sign it with the given BLS key."""
		pl = cls.__new__(cls) 
		pl.header = SignaturePayloadHeader(ts, len(l_tokens), header_message)
		pl.bls_signature = pl.calculate_signature(l_tokens, bls_privkey, bls_pubkey_bytes)
		return pl
	
	@classmethod
	def from_bytes(cls, pl_bytes: bytearray, n_header_message_chars: int=11):
		pl = cls.__new__(cls) 
		pl.header = SignaturePayloadHeader.from_bytes(pl_bytes, n_header_message_chars=n_header_message_chars)
		pl.bls_signature = bytes(pl_bytes[(5+n_header_message_chars):(5+n_header_message_chars+48)])
		return pl
	
	@classmethod
	def from_base64(cls, pl_b64: str, n_header_message_chars: int=11):
		pl_bytes = base64.b64decode(pl_b64)
		return cls.from_bytes(pl_bytes, n_header_message_chars=n_header_message_chars)
	
	@classmethod
	def write_csv(cls, l_payloads: list[SignaturePayload], l_sam_idx: list[int] = None, out_csv: str = "out.csv", n_header_message_chars: int = 11):
		if l_sam_idx is None: l_sam_idx = [-1] * len(l_payloads)
		with open(out_csv, "w", newline="") as f:
			writer = csv.writer(f)
			writer.writerow(["frame_start_sam", "timestamp", "word_count", "header_message", "bls_signature"])
			for i in range(len(l_payloads)):
				pl = l_payloads[i]
				sam_idx = l_sam_idx[i]
				ts_field = f"{int(pl.header.timestamp):010d}"
				wc_field = str(pl.header.word_count)
				header_field = _escape_csv_text_field(pl.header.message)
				sig_b64 = base64.b64encode(pl.bls_signature).decode("ascii")
				writer.writerow([sam_idx, ts_field, wc_field, header_field, sig_b64])

	@classmethod 
	def load_csv(cls, in_csv: str, n_header_message_chars: int = 11):
		"""
		Load CSV written by write_csv. Returns (l_payloads, l_sam_idx).
		Reconstructs SignaturePayload objects with header fields and signature bytes.
		"""
		l_payloads = list()
		l_sam_idx = list()
		with open(in_csv, newline='') as f:
			reader = csv.DictReader(f)
			for row in reader:
				sam_idx = int(row['frame_start_sam'])
				ts = int(row['timestamp'])
				wc = int(row['word_count'])
				header_message = _unescape_csv_text_field(row['header_message'])
				sig_b64 = row['bls_signature']
				bls_sig = base64.b64decode(sig_b64)

				# construct SignaturePayload instance without calling a constructor
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
	
	def to_base64(self, n_header_message_chars: int = 11):
		pl_bytes = self.to_bytes(n_header_message_chars=n_header_message_chars)
		return base64.b64encode(pl_bytes).decode("ascii")
	
	def calculate_signature(self, l_tokens: Iterable, bls_privkey: blst.SecretKey, bls_pubkey_bytes: bytes) -> bytes:
		"""Calculate the BLS signature for this payload given the list of tokens and BLS keys."""
		header_bytes = self.header.to_bytes()
		msg = bytearray(header_bytes)
		for tok in l_tokens: msg += (tok.text.encode("utf-8") + b"\x00")
		sig = blst.P1().hash_to(msg, DST, bls_pubkey_bytes) \
			.sign_with(bls_privkey).compress()
		return sig # 48 bytes (384 bits) BLS short signature
	
	def find_in_token_list(self, l_tokens: list, bls_pubkey_bytes: bytes, n_header_message_chars: int = 11):
		""" Given a payload and a list l_tokens, try and find (if and) where pl starts in l_tokens. 
		return the index or -1 if no match
		"""
		word_count = self.header.word_count
		if len(l_tokens) < word_count: 
			warnings.warn('Not enough tokens in this list to match this payload.', UserWarning)
			return -1 
		try: pl_sig = blst.P1_Affine(bytearray(self.bls_signature))
		except Exception:
			warnings.warn('Corrupted payload signature.', UserWarning)
			return -1 
		
		bls_pubkey = blst.P2_Affine(bls_pubkey_bytes)
		header_bytes = self.header.to_bytes(n_header_message_chars=n_header_message_chars)
		for idx in range(len(l_tokens) - word_count + 1):
			msg = bytearray(header_bytes)
			for tok in l_tokens[idx:(idx+word_count)]: msg += (tok.text.encode("utf-8") + b"\x00")
			try: # verify msg against bls_public_key and pl_sig
				ctx = blst.Pairing(True, DST)
				ctx.aggregate(bls_pubkey, pl_sig, msg, bls_pubkey_bytes)
				ctx.commit()
				if ctx.finalverify(): return idx
			except: pass
		return -1
	
	def print(self):
		print(f"Timestamp: {self.header.timestamp} ({time.ctime(self.header.timestamp)})")
		print(f"Word count: {self.header.word_count}")
		print(f"Header message: {self.header.message}")
		print(f"BLS signature (base64): {base64.b64encode(self.bls_signature).decode('ascii')}")

class PlaintextPayload:
	"""For tests and waveform debugging, sometimes it's easier to just tx plaintext data
	instead of signatures.
	"""
	content: str

	@classmethod
	def from_string(cls, s: str, n_content_chars: int = 64, pad_string: str = 'ASDFGHJKLZXCVBNMqwertyuiop'):
		pl = cls.__new__(cls)
		s = (s + pad_string * ((n_content_chars // len(pad_string)) + 1))[:n_content_chars]
		pl.content = s
		return pl

	@classmethod
	def from_bytes(cls, pl_bytes: bytearray):
		pl = cls.__new__(cls)
		pl.content = pl_bytes.decode("ascii", errors="replace")
		return pl

	@classmethod
	def write_csv(cls, l_payloads: list[PlaintextPayload], l_sam_idx: list[int] = None, out_csv: str = "out.csv"):
		if l_sam_idx is None: l_sam_idx = [-1] * len(l_payloads)
		with open(out_csv, "w", newline="") as f:
			writer = csv.writer(f)
			writer.writerow(["frame_start_sam", "content"])
			for i in range(len(l_payloads)):
				pl = l_payloads[i]
				sam_idx = l_sam_idx[i]
				content_field = _escape_csv_text_field(pl.content)
				writer.writerow([sam_idx, content_field])

	@classmethod 
	def load_csv(cls, in_csv: str):
		l_payloads = list()
		l_sam_idx = list()
		with open(in_csv, newline='') as f:
			reader = csv.DictReader(f)
			for row in reader:
				sam_idx = int(row['frame_start_sam'])
				content = _unescape_csv_text_field(row['content'])
				pl = cls.__new__(cls)
				pl.content = content
				l_payloads.append(pl)
				l_sam_idx.append(sam_idx)
		return l_payloads, l_sam_idx
	
	def to_bytes(self): 
		return self.content.encode("ascii")
	
	def print(self):
		print(f"Content: {self.content}")
