"""Encrypt the build output for the owner of the artifact key.

Format: u16 len(wrapped key) | RSA-OAEP(SHA-256) wrapped AES key | 12 byte nonce | AES-256-GCM ciphertext
"""

import os
import struct
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def main(pub_path, src, dst):
    pub = serialization.load_pem_public_key(Path(pub_path).read_bytes())
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    wrapped = pub.encrypt(
        key,
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    ct = AESGCM(key).encrypt(nonce, Path(src).read_bytes(), None)
    Path(dst).write_bytes(struct.pack(">H", len(wrapped)) + wrapped + nonce + ct)


if __name__ == "__main__":
    main(*sys.argv[1:4])
