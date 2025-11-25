#!/usr/bin/env python3
import os
import argparse
import stat
import blst

def save_keypair(private_key_path: str, public_key_path: str, force: bool = False) -> None:
	for p in (private_key_path, public_key_path):
		if os.path.exists(p) and not force:
			raise SystemExit(f"Refusing to overwrite existing file: {p} (use --force)")
	bls_privkey = blst.SecretKey()
	bls_privkey.keygen(os.urandom(32)) # secret key
	bls_privkey_bytes = bls_privkey.to_bendian()
	bls_pubkey_bytes = blst.P2(bls_privkey).serialize()
	with open(private_key_path, "wb") as f:
		f.write(bls_privkey_bytes) # 32 bytes
	with open(public_key_path, "wb") as f:
		f.write(bls_pubkey_bytes) # 96 bytes
	try: # lock down private key permissions on POSIX
		os.chmod(private_key_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
	except Exception: pass

def main():
	ap = argparse.ArgumentParser(description="Generate and save a BLS keypair (min-sig).")
	ap.add_argument("--privkey", default="bls_privkey.bin", help="Private key output path (default: bls_privkey.bin)")
	ap.add_argument("--pubkey", default="bls_pubkey.bin", help="Public key output path (default: bls_pubkey.bin)")
	ap.add_argument("--force", action="store_true", help="Overwrite existing files")
	args = ap.parse_args()
	save_keypair(args.privkey, args.pubkey, args.force)

if __name__ == "__main__":
	main()
