from rag_anything.security.passwords import hash_password, needs_rehash, verify_password


def test_hash_is_argon2id() -> None:
    assert hash_password("correct horse battery staple").startswith("$argon2id$")


def test_hash_never_contains_the_plaintext() -> None:
    password = "correct horse battery staple"
    assert password not in hash_password(password)


def test_verify_accepts_the_right_password() -> None:
    password = "correct horse battery staple"
    assert verify_password(password, hash_password(password)) is True


def test_verify_rejects_the_wrong_password() -> None:
    assert verify_password("wrong", hash_password("right")) is False


def test_hashes_are_salted_and_therefore_differ() -> None:
    password = "same password"
    assert hash_password(password) != hash_password(password)


def test_verify_rejects_a_malformed_hash_instead_of_raising() -> None:
    assert verify_password("anything", "not-a-hash") is False


def test_verify_rejects_an_empty_hash_instead_of_raising() -> None:
    assert verify_password("anything", "") is False


def test_current_hashes_do_not_need_rehashing() -> None:
    assert needs_rehash(hash_password("password")) is False