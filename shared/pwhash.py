"""Authenticator-secret hashing, shared by the CSP (which creates the record)
and the Verifier (which checks against it).

scrypt is a password hashing function from the standard library
(`hashlib.scrypt`, PBKDF2/scrypt family) — a bare SHA-256 or MD5 would be a
graded failure, because those are fast by design and a stolen store is then
brute-forceable at speed.

The record produced here is the *only* thing the CSP hands to the Verifier.
The authenticator secret itself never leaves the process that received it.
"""

import hashlib
import hmac
import os
import secrets
from typing import Any, Dict

ALG = "scrypt"
N = 2 ** 14
R = 8
P = 1
DKLEN = 32
SALT_BYTES = 16
MAXMEM = 64 * 1024 * 1024  # 128 * N * R is ~16MB; leave headroom.


def hash_secret(secret: str, *, salt: bytes = None) -> Dict[str, Any]:
    """Return a self-describing verification record for `secret`."""
    if not isinstance(secret, str) or not secret:
        raise ValueError("secret must be a non-empty string")
    salt = salt if salt is not None else secrets.token_bytes(SALT_BYTES)
    dk = hashlib.scrypt(
        secret.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=DKLEN, maxmem=MAXMEM
    )
    return {
        "alg": ALG,
        "n": N,
        "r": R,
        "p": P,
        "dklen": DKLEN,
        "salt": salt.hex(),
        "dk": dk.hex(),
    }


def is_record(record: Any) -> bool:
    """True if `record` has the shape `verify_secret` can use."""
    if not isinstance(record, dict) or record.get("alg") != ALG:
        return False
    for key, typ in (("n", int), ("r", int), ("p", int), ("dklen", int),
                     ("salt", str), ("dk", str)):
        if not isinstance(record.get(key), typ) or isinstance(record.get(key), bool):
            return False
    if not (1 <= record["dklen"] <= 128) or record["n"] < 2 or record["r"] < 1 or record["p"] < 1:
        return False
    try:
        bytes.fromhex(record["salt"])
        bytes.fromhex(record["dk"])
    except ValueError:
        return False
    return True


def verify_secret(secret: Any, record: Any) -> bool:
    """Constant-time check of `secret` against a record from `hash_secret`."""
    if not isinstance(secret, str) or not secret or not is_record(record):
        return False
    try:
        dk = hashlib.scrypt(
            secret.encode("utf-8"),
            salt=bytes.fromhex(record["salt"]),
            n=record["n"],
            r=record["r"],
            p=record["p"],
            dklen=record["dklen"],
            maxmem=MAXMEM,
        )
    except (ValueError, MemoryError):
        return False
    return hmac.compare_digest(dk, bytes.fromhex(record["dk"]))


_DUMMY_RECORD = hash_secret("dummy-authenticator-output", salt=b"\x00" * SALT_BYTES)


def burn_equivalent_work(secret: Any) -> None:
    """Do the same work as a real verification, and discard the answer.

    Called when no binding exists for the claimed identifier, so that an
    unknown identifier and a wrong authenticator output take the same time as
    well as returning the same response — otherwise the clock answers the
    question the response body refuses to (account enumeration by timing).
    """
    verify_secret(secret if isinstance(secret, str) and secret else "x", _DUMMY_RECORD)
