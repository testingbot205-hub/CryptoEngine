"""
crypto_engine.py — Криптографічне ядро SecureMsg
=================================================
Реалізує гібридну схему: RSA-2048 (OAEP) для захисту ключів сесії
та AES-256-GCM для шифрування даних з автентифікацією цілісності.

Чому GCM, а не CBC:
  - CBC шифрує, але не автентифікує — підробку файлу можна не помітити.
  - GCM = шифрування + MAC в одному проході. Будь-яка зміна шифротексту
    або заголовка виявляється при дешифруванні (AuthenticationError).

Формат зашифрованого пакету (.smsg):
  [4 bytes]  довжина зашифрованого AES-ключа
  [N bytes]  зашифрований AES-ключ (RSA-OAEP)
  [12 bytes] nonce (AES-GCM)
  [остаток]  шифротекст + 16-байтовий GCM-тег
"""

import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import struct


# --------------------------------------------------------------------------- #
#  Генерація ключів                                                            #
# --------------------------------------------------------------------------- #

def generate_key_pair() -> tuple[RSAPrivateKey, RSAPublicKey]:
    """Генерує пару RSA-2048. Повертає (private_key, public_key)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key, private_key.public_key()


def serialize_private_key(private_key: RSAPrivateKey, password: bytes | None = None) -> bytes:
    """Серіалізує приватний ключ у PEM. Опційно захищає паролем."""
    encryption = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )


def serialize_public_key(public_key: RSAPublicKey) -> bytes:
    """Серіалізує публічний ключ у PEM для передачі колезі або клієнту."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def load_private_key(pem_data: bytes, password: bytes | None = None) -> RSAPrivateKey:
    """Завантажує приватний ключ із PEM."""
    return serialization.load_pem_private_key(pem_data, password=password)


def load_public_key(pem_data: bytes) -> RSAPublicKey:
    """Завантажує публічний ключ із PEM."""
    return serialization.load_pem_public_key(pem_data)


# --------------------------------------------------------------------------- #
#  Шифрування                                                                  #
# --------------------------------------------------------------------------- #

def encrypt(plaintext: bytes, recipient_public_key: RSAPublicKey) -> bytes:
    """
    Шифрує довільні байти для отримувача.

    Алгоритм:
      1. Генерується випадковий 256-бітний AES-ключ сесії.
      2. AES-ключ шифрується RSA-OAEP публічним ключем отримувача.
      3. Відкритий текст шифрується AES-256-GCM з випадковим 96-бітним nonce.
      4. Пакується у бінарний формат .smsg.
    """
    # Крок 1: одноразовий AES-ключ
    aes_key = os.urandom(32)   # 256 біт
    nonce = os.urandom(12)     # 96 біт — рекомендований розмір для GCM

    # Крок 2: захист AES-ключа через RSA-OAEP
    encrypted_aes_key = recipient_public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # Крок 3: шифрування даних AES-GCM
    aesgcm = AESGCM(aes_key)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)

    # Крок 4: упаковка пакету
    key_len = len(encrypted_aes_key)
    header = struct.pack(">I", key_len)   # 4 байти big-endian
    return header + encrypted_aes_key + nonce + ciphertext_with_tag


def decrypt(package: bytes, private_key: RSAPrivateKey) -> bytes:
    """
    Розшифровує пакет .smsg приватним ключем отримувача.
    Підіймає ValueError при неправильному ключі або пошкодженому файлі.
    """
    # Розбір заголовка
    if len(package) < 4:
        raise ValueError("Пошкоджений пакет: недостатньо даних.")

    key_len = struct.unpack(">I", package[:4])[0]
    offset = 4

    if len(package) < offset + key_len + 12:
        raise ValueError("Пошкоджений пакет: неправильна структура.")

    encrypted_aes_key = package[offset: offset + key_len]
    offset += key_len
    nonce = package[offset: offset + 12]
    offset += 12
    ciphertext_with_tag = package[offset:]

    # Розшифрування AES-ключа RSA-OAEP
    try:
        aes_key = private_key.decrypt(
            encrypted_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except Exception:
        raise ValueError("Неправильний ключ або пошкоджений пакет.")

    # Розшифрування AES-GCM (автоматично перевіряє цілісність)
    try:
        aesgcm = AESGCM(aes_key)
        return aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    except Exception:
        raise ValueError("Помилка автентифікації: файл пошкоджено або підроблено.")


# --------------------------------------------------------------------------- #
#  Зручні обгортки для тексту і файлів                                        #
# --------------------------------------------------------------------------- #

def encrypt_text(text: str, recipient_public_key: RSAPublicKey) -> bytes:
    """Шифрує текстовий рядок. Повертає бінарний пакет .smsg."""
    return encrypt(text.encode("utf-8"), recipient_public_key)


def decrypt_text(package: bytes, private_key: RSAPrivateKey) -> str:
    """Розшифровує пакет і повертає текстовий рядок."""
    return decrypt(package, private_key).decode("utf-8")


def encrypt_file(file_path: str, recipient_public_key: RSAPublicKey) -> bytes:
    """
    Читає файл і повертає зашифрований пакет.
    Оригінальне ім'я файлу зберігається у перших байтах відкритого тексту.

    Формат відкритого тексту перед шифруванням:
      [2 bytes]  довжина імені файлу (UTF-8)
      [N bytes]  ім'я файлу
      [остаток]  вміст файлу
    """
    filename = os.path.basename(file_path)
    filename_bytes = filename.encode("utf-8")
    with open(file_path, "rb") as f:
        file_content = f.read()

    name_len = struct.pack(">H", len(filename_bytes))
    plaintext = name_len + filename_bytes + file_content
    return encrypt(plaintext, recipient_public_key)


def decrypt_file(package: bytes, private_key: RSAPrivateKey) -> tuple[str, bytes]:
    """
    Розшифровує файловий пакет.
    Повертає (оригінальне_ім'я_файлу, вміст).
    """
    plaintext = decrypt(package, private_key)
    name_len = struct.unpack(">H", plaintext[:2])[0]
    filename = plaintext[2: 2 + name_len].decode("utf-8")
    file_content = plaintext[2 + name_len:]
    return filename, file_content
