from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return an Argon2id hash string, with algorithm, parameters, and salt embedded."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verification. Returns False rather than raising on bad input.

    A malformed stored hash means the row is corrupt; that should be a failed
    login, not a 500 that tells an attacker something interesting happened.
    """
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the hash used weaker parameters than the current defaults.

    Login re-hashes on success when this is True, so raising the cost parameters
    later upgrades existing users transparently as they log in.
    """
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True