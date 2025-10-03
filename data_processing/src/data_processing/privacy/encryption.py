"""Data encryption for secure storage and processing."""
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


@dataclass
class EncryptionConfig:
    """Configuration for data encryption."""
    key_derivation_iterations: int = 480000
    salt: bytes = b'anthropic-clio-2024'


class DataEncryptor:
    """Encrypts and decrypts data using Fernet (symmetric encryption)."""

    def __init__(self, password: str, config: EncryptionConfig):
        self.config = config
        self._key = self._derive_key(password)
        self._fernet = Fernet(self._key)

    def _derive_key(self, password: str) -> bytes:
        """Derive encryption key from password.

        Args:
            password: Master password

        Returns:
            Derived key bytes
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.config.salt,
            iterations=self.config.key_derivation_iterations,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt bytes.

        Args:
            data: Data to encrypt

        Returns:
            Encrypted data
        """
        return self._fernet.encrypt(data)

    def decrypt_bytes(self, encrypted_data: bytes) -> bytes:
        """Decrypt bytes.

        Args:
            encrypted_data: Encrypted data

        Returns:
            Decrypted data
        """
        return self._fernet.decrypt(encrypted_data)

    def encrypt_text(self, text: str) -> str:
        """Encrypt text.

        Args:
            text: Text to encrypt

        Returns:
            Base64-encoded encrypted text
        """
        encrypted = self.encrypt_bytes(text.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt_text(self, encrypted_text: str) -> str:
        """Decrypt text.

        Args:
            encrypted_text: Base64-encoded encrypted text

        Returns:
            Decrypted text
        """
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
        decrypted = self.decrypt_bytes(encrypted_bytes)
        return decrypted.decode()

    def encrypt_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> None:
        """Encrypt a file.

        Args:
            input_path: Path to input file
            output_path: Path to output encrypted file
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        with open(input_path, 'rb') as f:
            data = f.read()

        encrypted = self.encrypt_bytes(data)

        with open(output_path, 'wb') as f:
            f.write(encrypted)

    def decrypt_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> None:
        """Decrypt a file.

        Args:
            input_path: Path to encrypted file
            output_path: Path to output decrypted file
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        with open(input_path, 'rb') as f:
            encrypted_data = f.read()

        decrypted = self.decrypt_bytes(encrypted_data)

        with open(output_path, 'wb') as f:
            f.write(decrypted)

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key.

        Returns:
            Base64-encoded key
        """
        return Fernet.generate_key().decode()
