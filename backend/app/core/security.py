from cryptography.fernet import Fernet, InvalidToken

from app.core.exceptions import ConfigurationError


class CredentialCipher:
    def __init__(self, encryption_key: str) -> None:
        try:
            self._fernet = Fernet(encryption_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise ConfigurationError("SECRET_ENCRYPTION_KEY is invalid") from exc

    def encrypt_secret(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt_secret(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise ConfigurationError("Stored database credentials could not be decrypted") from exc
