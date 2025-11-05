# imprint/bls_min_sig.py — BLS12-381 min-sig (48B sigs, 96B pubkeys), SWIG blst
import os
import blst

DST = b"BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_"

def _sk_bytes(sk) -> bytes:
    for name in ("to_bytes", "serialize", "as_bytes"):
        fn = getattr(sk, name, None)
        if callable(fn):
            return fn()
    # last resort: some builds expose .b or .value as a bytes-like
    for name in ("b", "value"):
        v = getattr(sk, name, None)
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
    raise RuntimeError("SecretKey has no to_bytes()/serialize()/as_bytes().")

def _p2_bytes(p2_aff) -> bytes:
    for name in ("serialize", "compress"):
        fn = getattr(p2_aff, name, None)
        if callable(fn):
            return fn()
    raise RuntimeError("Cannot serialize P2_Affine (no serialize/compress).")

def _p1_bytes(p1_aff) -> bytes:
    for name in ("serialize", "compress"):
        fn = getattr(p1_aff, name, None)
        if callable(fn):
            return fn()
    raise RuntimeError("Cannot serialize P1_Affine (no serialize/compress).")

def _p1_aff_from_bytes(b: bytes):
    if hasattr(blst, "p1_uncompress"):
        return blst.p1_uncompress(b)
    try:
        return blst.P1_Affine(b)
    except Exception:
        return None

def _p2_aff_from_bytes(b: bytes):
    if hasattr(blst, "p2_uncompress"):
        return blst.p2_uncompress(b)
    try:
        return blst.P2_Affine(b)
    except Exception:
        return None

def _sk_to_pk2_aff(sk):
    # try instance methods
    for name in ("sk_to_pk2", "sk_to_pk_in_g2", "to_pk2", "to_public_key_g2",
                 "public_key_g2", "get_public_key_g2"):
        fn = getattr(sk, name, None)
        if callable(fn):
            return fn()
    # module-level helpers
    for name in ("sk_to_pk2", "sk_to_pk_in_g2", "to_pk2", "to_public_key_g2",
                 "public_key_g2", "get_public_key_g2", "pk_from_sk2", "pk_in_g2_from_sk"):
        fn = getattr(blst, name, None)
        if callable(fn):
            return fn(sk)
    # constructors
    for cls_name in ("PublicKey", "P2_Affine", "PkInG2"):
        cls = getattr(blst, cls_name, None)
        if cls:
            try:
                return cls(sk)
            except Exception:
                pass
    raise RuntimeError("No G2 public-key generator found in this blst build.")

def keygen(seed: bytes | None = None) -> tuple[bytes, bytes]:
    if seed is None:
        seed = os.urandom(32)
    sk = blst.SecretKey()
    if hasattr(sk, "keygen"):
        sk.keygen(seed)
    elif hasattr(sk, "from_bendian"):
        sk.from_bendian(seed)  # some builds
    else:
        raise RuntimeError("SecretKey lacks keygen()/from_bendian().")
    pk_aff = _sk_to_pk2_aff(sk)
    return _sk_bytes(sk), _p2_bytes(pk_aff)  # 32B, 96B

def sign(sk_bytes: bytes, msg: bytes) -> bytes:
    sk = blst.SecretKey()
    # re-derive deterministically from stored 32 bytes
    if hasattr(sk, "keygen"):
        sk.keygen(sk_bytes)
    elif hasattr(sk, "from_bendian"):
        sk.from_bendian(sk_bytes)
    else:
        raise RuntimeError("SecretKey lacks keygen()/from_bendian().")
    sig_aff = blst.sign_pk_in_g1(sk, msg, DST, b"")
    return _p1_bytes(sig_aff)  # 48B

def verify(pk_bytes: bytes, msg: bytes, sig_bytes: bytes) -> bool:
    pk_aff = _p2_aff_from_bytes(pk_bytes)
    sig_aff = _p1_aff_from_bytes(sig_bytes)
    if pk_aff is None or sig_aff is None:
        return False
    err = blst.core_verify_pk_in_g2(sig_aff, pk_aff, True, msg, DST, b"")
    return err == 0 or getattr(err, "name", "") == "BLST_SUCCESS"
