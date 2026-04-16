import os

import dotenv
from cryptography.fernet import Fernet


def _get_fernet_key() -> bytes:
    dotenv.load_dotenv()
    return bytes(os.getenv("MEROSHARE_KEY"), "utf-8")


def encrypt_password(password: str) -> str:
    fernet = Fernet(_get_fernet_key())
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    fernet = Fernet(_get_fernet_key())
    return fernet.decrypt(encrypted_password.encode()).decode()

