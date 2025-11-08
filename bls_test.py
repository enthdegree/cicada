#!/usr/bin/env python3
import blst
#######################################################################

msg = b"this is my message asdfasdfasdf"		# this what we're signing
DST = b"BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_"	# domain separation tag

privkey = blst.SecretKey()
privkey.keygen(b"*"*32) # secret key
privkey_bytes = privkey.to_bendian()
privkey_rt = blst.SecretKey().from_bendian(privkey_bytes)
pubkey_bytes = blst.P2(privkey).serialize()
sig_bytes = blst.P1().hash_to(msg, DST, pubkey_bytes) \
                        .sign_with(privkey).compress()
print(len(sig_bytes))

########################################################################
# at this point 'privkey_bytes', 'sig_for_wire' and 'msg' are
# "sent over network," so now on "receiver" side

sig = blst.P1_Affine(sig_bytes)
pubkey  = blst.P2_Affine(pubkey_bytes)
if not pubkey.in_group(): # vet the public key
    raise AssertionError("disaster")
ctx = blst.Pairing(True, DST)
ctx.aggregate(pubkey, sig, msg, pubkey_bytes)
ctx.commit()
if not ctx.finalverify(): 
    raise AssertionError("disaster")

