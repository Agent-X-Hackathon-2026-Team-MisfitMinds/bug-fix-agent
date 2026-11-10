"""AES-256-GCM encryption for GitHub access tokens at rest."""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ASSOCIATED_DATA = b"bug-fix-agent:github-token"


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt_token(token: str, secret: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_key(secret)).encrypt(nonce, token.encode("utf-8"), _ASSOCIATED_DATA)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_token(blob: str, secret: str) -> str:
    raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    nonce, ciphertext = raw[:12], raw[12:]
    plaintext = AESGCM(_derive_key(secret)).decrypt(nonce, ciphertext, _ASSOCIATED_DATA)
    return plaintext.decode("utf-8")
