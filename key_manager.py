"""
key_manager.py — Менеджер ключів SecureMsg
==========================================
Відповідає за збереження, завантаження та організацію ключів на диску.

Структура директорій:
  ~/.securemsg/
    keys/
      my_private.pem     — приватний ключ поточного користувача
      my_public.pem      — публічний ключ для передачі колегам
    contacts/
      <ім'я>.pem         — публічні ключі колег та клієнтів
"""

import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from crypto_engine import (
    generate_key_pair, serialize_private_key, serialize_public_key,
    load_private_key, load_public_key,
)

BASE_DIR = Path.home() / ".securemsg"
KEYS_DIR = BASE_DIR / "keys"
CONTACTS_DIR = BASE_DIR / "contacts"

PRIVATE_KEY_PATH = KEYS_DIR / "my_private.pem"
PUBLIC_KEY_PATH = KEYS_DIR / "my_public.pem"


def ensure_dirs():
    """Створює директорії якщо їх немає."""
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    CONTACTS_DIR.mkdir(parents=True, exist_ok=True)


def has_own_keys() -> bool:
    return PRIVATE_KEY_PATH.exists() and PUBLIC_KEY_PATH.exists()


def create_own_keys(password: str | None = None) -> RSAPublicKey:
    """Генерує нову пару ключів і зберігає на диску. Повертає публічний ключ."""
    ensure_dirs()
    private_key, public_key = generate_key_pair()
    pwd_bytes = password.encode() if password else None

    PRIVATE_KEY_PATH.write_bytes(serialize_private_key(private_key, pwd_bytes))
    PUBLIC_KEY_PATH.write_bytes(serialize_public_key(public_key))

    # Права на приватний ключ: тільки власник
    os.chmod(PRIVATE_KEY_PATH, 0o600)
    return public_key


def load_own_private_key(password: str | None = None) -> RSAPrivateKey:
    pwd_bytes = password.encode() if password else None
    try:
        return load_private_key(PRIVATE_KEY_PATH.read_bytes(), pwd_bytes)
    except Exception:
        raise ValueError("Неправильний пароль або пошкоджений ключ.")


def load_own_public_key() -> RSAPublicKey:
    return load_public_key(PUBLIC_KEY_PATH.read_bytes())


def get_own_public_key_pem() -> str:
    """Повертає публічний ключ у PEM для копіювання та передачі."""
    return PUBLIC_KEY_PATH.read_text()


# --------------------------------------------------------------------------- #
#  Контакти                                                                    #
# --------------------------------------------------------------------------- #

def save_contact(name: str, public_key_pem: str):
    """Зберігає публічний ключ контакту."""
    ensure_dirs()
    path = CONTACTS_DIR / f"{name}.pem"
    path.write_text(public_key_pem.strip())


def load_contact_key(name: str) -> RSAPublicKey:
    path = CONTACTS_DIR / f"{name}.pem"
    if not path.exists():
        raise FileNotFoundError(f"Контакт «{name}» не знайдено.")
    return load_public_key(path.read_bytes())


def list_contacts() -> list[str]:
    ensure_dirs()
    return sorted(p.stem for p in CONTACTS_DIR.glob("*.pem"))


def get_contact_pem(name: str) -> str:
    """Повертає публічний ключ контакту у PEM-форматі."""
    path = CONTACTS_DIR / f"{name}.pem"
    if not path.exists():
        raise FileNotFoundError(f"Контакт «{name}» не знайдено.")
    return path.read_text()

def delete_contact(name: str):
    path = CONTACTS_DIR / f"{name}.pem"
    if path.exists():
        path.unlink()


def import_contact_from_file(name: str, file_path: str):
    pem_data = Path(file_path).read_text()
    # Перевірка що це справді валідний ключ
    load_public_key(pem_data.encode())
    save_contact(name, pem_data)
