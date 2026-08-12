from cryptography.fernet import Fernet

from app.core.security import CredentialCipher


def test_credential_cipher_round_trip() -> None:
    cipher = CredentialCipher(Fernet.generate_key().decode("ascii"))

    encrypted = cipher.encrypt_secret("sensitive-password")

    assert encrypted != "sensitive-password"
    assert cipher.decrypt_secret(encrypted) == "sensitive-password"
