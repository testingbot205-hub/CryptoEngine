"""
================================================================================
crypto_engine.py — Криптографічне ядро SecureMsg
================================================================================

АРХІТЕКТУРА ТА КРИПТОГРАФІЧНІ РІШЕННЯ
--------------------------------------

1. ГІБРИДНА СХЕМА ШИФРУВАННЯ
   ┌─────────────────────────────────────────────────────────────────────┐
   │  Проблема: RSA шифрує лише обмежену кількість байтів (~245 для      │
   │  RSA-2048 з OAEP). Великі файли неможливо зашифрувати напряму RSA.  │
   │                                                                     │
   │  Рішення: Гібридна схема (hybrid encryption):                       │
   │    • RSA-OAEP → шифрує одноразовий AES-ключ сесії                  │
   │    • AES-256-GCM → шифрує самі дані                                │
   │                                                                     │
   │  Це стандартна практика в TLS, PGP, Signal та інших протоколах.    │
   └─────────────────────────────────────────────────────────────────────┘

2. ЧОМУ САМЕ AES-256-GCM, А НЕ CBC?
   ┌─────────────────────────────────────────────────────────────────────┐
   │  CBC (Cipher Block Chaining):                                       │
   │    ✓ Шифрує дані                                                    │
   │    ✗ НЕ автентифікує цілісність — зловмисник може підмінити       │
   │      блоки шифротексту без виявлення                                │
   │    ✗ Потребує окремого HMAC для MAC (Encrypt-then-MAC)            │
   │    ✗ Уразливий до padding oracle attacks                            │
   │                                                                     │
   │  GCM (Galois/Counter Mode):                                         │
   │    ✓ Шифрує дані (Counter mode)                                     │
   │    ✓ Автоматично автентифікує цілісність (Galois MAC)             │
   │    ✓ Однопрохідний — швидший за CBC+HMAC                          │
   │    ✓ Паралелізується на GPU/AVX                                    │
   │    ✓ Стандарт NIST SP 800-38D                                     │
   │                                                                     │
   │  У GCM будь-яка зміна шифротексту, nonce або AAD виявляється      │
   │  при дешифруванні як AuthenticationError.                          │
   └─────────────────────────────────────────────────────────────────────┘

3. ФОРМАТ ПАКЕТУ .smsg (Secure Message)
   ┌─────────────────────────────────────────────────────────────────────┐
   │  [4 bytes]   довжина зашифрованого AES-ключа (big-endian uint32)    │
   │  [N bytes]   зашифрований AES-ключ (RSA-OAEP)                       │
   │  [12 bytes]  nonce (IV) для AES-GCM                                 │
   │  [остаток]   ciphertext + 16-байтовий GCM authentication tag        │
   │                                                                     │
   │  Big-endian (network byte order) — стандарт для бінарних протоколів │
   │  struct.pack(">I", ...) — ">" = big-endian, "I" = unsigned int    │
   └─────────────────────────────────────────────────────────────────────┘

4. RSA-OAEP (Optimal Asymmetric Encryption Padding)
   ┌─────────────────────────────────────────────────────────────────────┐
   │  OAEP — це padding scheme, що перетворює детерміністичний RSA       │
   │  на probabilistic (ймовірнісний) шифр.                             │
   │                                                                     │
   │  Без OAEP: RSA(m) = m^e mod n — детерміністичний, вразливий до      │
   │  атаки на відкритий текст (known-plaintext attacks).                │
   │                                                                     │
   │  З OAEP: кожне шифрування дає різний шифротекст навіть для          │
   │  однакового відкритого тексту (semantic security).                  │
   │                                                                     │
   │  Параметри:                                                         │
   │    • MGF1 з SHA-256 — маскуюча функція                              │
   │    • Hash = SHA-256 — хеш-функція для padding                       │
   │    • label = None — додаткові асоційовані дані (AAD)                │
   │                                                                     │
   │  Максимальний розмір plaintext для RSA-2048 + OAEP(SHA-256):        │
   │    2048/8 - 2*32 - 2 = 190 байт (для OAEPv2)                       │
   │    Але cryptography library використовує рекомендований розмір.     │
   └─────────────────────────────────────────────────────────────────────┘

5. БЕЗПЕКА КЛЮЧІВ
   ┌─────────────────────────────────────────────────────────────────────┐
   │  • AES-ключ сесії: os.urandom(32) — CSPRNG (Cryptographically       │
   │    Secure Pseudo-Random Number Generator), використовує            │
   │    /dev/urandom на Linux, CryptGenRandom на Windows                 │
   │                                                                     │
   │  • Nonce: os.urandom(12) — 96 біт, рекомендований розмір для GCM    │
   │    (NIST SP 800-38D §5.2.1.1). Довші nonce обрізаються.             │
   │                                                                     │
   │  • RSA-2048: мінімальний розмір для безпеки до 2030 року           │
   │    (NIST SP 800-57 Part 1 Rev. 5).                                 │
   │    65537 = стандартне public exponent (F4), оптимізоване           │
   │    для Montgomery multiplication.                                   │
   └─────────────────────────────────────────────────────────────────────┘
"""

import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import struct


# ============================================================================ #
#  ГЕНЕРАЦІЯ КЛЮЧІВ RSA-2048                                                   #
# ============================================================================ #

def generate_key_pair() -> tuple[RSAPrivateKey, RSAPublicKey]:
    """
    Генерує пару асиметричних ключів RSA-2048.

    ПАРАМЕТРИ:
    -----------
    • public_exponent = 65537 (F4)
      Це стандартне значення, рекомендоване NIST та IETF (RFC 8017).
      Менші значення (наприклад, 3) теоретично швидші, але вразливі
      до атаки Вінера при малих приватних експонентах.
      65537 = 2^16 + 1 — має лише два "1" у двійковому запису,
      що робить модульне піднесення до степеня ефективним
      (Square-and-Multiply: 16 squarings + 1 multiplication).

    • key_size = 2048 біт
      Мінімальний розмір, рекомендований NIST для використання
      до 2030 року (NIST SP 800-57 Part 1 Rev. 5).
      Для довгострокової безпеки (>2030) рекомендується 3072 біт.

    ПОВЕРТАЄ:
    ----------
    tuple: (RSAPrivateKey, RSAPublicKey) — приватний та публічний ключі
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,   # F4 — стандартний публічний експонент
        key_size=2048,           # Розмір модуля в бітах
    )
    # public_key() — математично похідний від private_key,
    # але зберігається окремо для зручності
    return private_key, private_key.public_key()


def serialize_private_key(private_key: RSAPrivateKey, password: bytes | None = None) -> bytes:
    """
    Серіалізує приватний ключ у формат PEM (Privacy Enhanced Mail).

    ФОРМАТ PEM:
    -----------
    PEM — це base64-кодований DER (Distinguished Encoding Rules),
    обгорнутий в ASCII-маркери:

        -----BEGIN ENCRYPTED PRIVATE KEY-----
        MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...
        ...
        -----END ENCRYPTED PRIVATE KEY-----

    PKCS#8 (PrivateFormat.PKCS8) — сучасний стандарт зберігання
    приватних ключів. На відміну від традиційного PKCS#1 ("RSA PRIVATE KEY"),
    PKCS#8 підтримує будь-який алгоритм (RSA, ECC, Ed25519 тощо).

    ШИФРУВАННЯ ПАРОЛЕМ (опціонально):
    ---------------------------------
    • BestAvailableEncryption — використовує найсильніший алгоритм,
    який підтримує бібліотека (зазвичай AES-256-CBC з PBKDF2).
    • NoEncryption — ключ зберігається у відкритому вигляді.
      Це ризиковано, але зручно для автоматизованих процесів.

    ПАРАМЕТРИ:
    -----------
    private_key: RSAPrivateKey — приватний ключ для серіалізації
    password: bytes | None — пароль для шифрування PEM (None = без шифрування)

    ПОВЕРТАЄ:
    ----------
    bytes: PEM-кодований приватний ключ
    """
    encryption = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,        # PEM = base64 + ASCII headers
        format=serialization.PrivateFormat.PKCS8,       # Сучасний формат (алгоритм-незалежний)
        encryption_algorithm=encryption,              # Шифрування або відкритий текст
    )


def serialize_public_key(public_key: RSAPublicKey) -> bytes:
    """
    Серіалізує публічний ключ у формат PEM.

    ФОРМАТ:
    -------
    SubjectPublicKeyInfo (SPKI) — стандарт X.509 для публічних ключів.
    Містить алгоритм, параметри та сам ключ:

        -----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
        ...
        -----END PUBLIC KEY-----

    Цей формат використовується для обміну ключами між користувачами.
    Безпечно передавати по відкритих каналах — це ТІЛЬКИ публічний ключ.

    ПАРАМЕТРИ:
    -----------
    public_key: RSAPublicKey — публічний ключ для серіалізації

    ПОВЕРТАЄ:
    ----------
    bytes: PEM-кодований публічний ключ
    """
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def load_private_key(pem_data: bytes, password: bytes | None = None) -> RSAPrivateKey:
    """
    Завантажує приватний ключ із PEM-даних.

    ВАЛІДАЦІЯ:
    ----------
    • Перевіряє коректність PEM-структури
    • Перевіряє пароль (якщо ключ зашифрований)
    • Перевіряє математичну цілісність ключової пари (p*q = n)

    ПАРАМЕТРИ:
    -----------
    pem_data: bytes — PEM-кодований приватний ключ
    password: bytes | None — пароль для дешифрування (None = відкритий ключ)

    ПОВЕРТАЄ:
    ----------
    RSAPrivateKey — завантажений приватний ключ

    ВИКЛИКАЄ:
    ----------
    ValueError — якщо пароль неправильний або PEM пошкоджений
    """
    return serialization.load_pem_private_key(pem_data, password=password)


def load_public_key(pem_data: bytes) -> RSAPublicKey:
    """
    Завантажує публічний ключ із PEM-даних.

    ВАЛІДАЦІЯ:
    ----------
    • Перевіряє коректність PEM-структури
    • Перевіряє, що це дійсно публічний ключ (не приватний)
    • Перевіряє математичну цілісність (n = p*q, e*d ≡ 1 mod φ(n))

    ПАРАМЕТРИ:
    -----------
    pem_data: bytes — PEM-кодований публічний ключ

    ПОВЕРТАЄ:
    ----------
    RSAPublicKey — завантажений публічний ключ

    ВИКЛИКАЄ:
    ----------
    ValueError — якщо PEM пошкоджений або це не публічний ключ
    """
    return serialization.load_pem_public_key(pem_data)


# ============================================================================ #
#  ШИФРУВАННЯ (Гібридна схема RSA + AES-GCM)                                  #
# ============================================================================ #

def encrypt(plaintext: bytes, recipient_public_key: RSAPublicKey) -> bytes:
    """
    Шифрує довільні байти для отримувача за гібридною схемою.

    АЛГОРИТМ (покроково):
    ---------------------

    КРОК 1: Генерація одноразового AES-ключа сесії
        aes_key = os.urandom(32)  # 256 біт

        os.urandom() використовує ОС-рівневий CSPRNG:
        • Linux: getrandom() syscall або /dev/urandom
        • Windows: CryptGenRandom / BCryptGenRandom
        • macOS: arc4random()

        Це НЕ псевдовипадковий генератор Python (random.random()),
        а криптографічно безпечний — передбачити наступне значення
        неможливо навіть знаючи всі попередні.

    КРОК 2: Генерація nonce для AES-GCM
        nonce = os.urandom(12)  # 96 біт

        96 біт — рекомендований розмір для GCM (NIST SP 800-38D).
        Довші nonce (наприклад, 128 біт) обрізаються до 96 біт
        внутрішньо бібліотекою. Коротші nonce зменшують простір
        для безпечного використання (birthday paradox).

    КРОК 3: Шифрування AES-ключа через RSA-OAEP
        encrypted_aes_key = recipient_public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),  # Маскуюча функція
                algorithm=hashes.SHA256(),                     # Хеш для padding
                label=None,                                    # Додаткові дані
            ),
        )

        OAEP padding додає випадковість: один і той самий AES-ключ
        зашифровується RSA по-різному кожного разу (semantic security).

    КРОК 4: Шифрування даних AES-256-GCM
        aesgcm = AESGCM(aes_key)
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)

        AES-GCM працює в два етапи одночасно:
        • CTR mode — шифрує дані (Counter mode, потоковий шифр)
        • GHASH — обчислює тег автентифікації (Galois MAC)

        ciphertext_with_tag містить:
        [дані] + [16-байтовий GCM tag]

        Tag гарантує, що жоден біт даних не був змінений.
        Зміна навіть одного біта викликає AuthenticationError
        при дешифруванні.

    КРОК 5: Упаковка пакету .smsg
        key_len = len(encrypted_aes_key)          # Зазвичай 256 байт для RSA-2048
        header = struct.pack(">I", key_len)       # 4 байти big-endian
        return header + encrypted_aes_key + nonce + ciphertext_with_tag

        Big-endian (network byte order) — стандарт для бінарних протоколів,
        незалежний від архітектури процесора (x86 = little-endian,
        ARM = bi-endian, network = big-endian).

    ПАРАМЕТРИ:
    -----------
    plaintext: bytes — відкриті дані для шифрування (довільний розмір)
    recipient_public_key: RSAPublicKey — публічний ключ отримувача

    ПОВЕРТАЄ:
    ----------
    bytes: зашифрований пакет у форматі .smsg
    """
    # Крок 1: одноразовий AES-ключ (256 біт = 32 байти)
    aes_key = os.urandom(32)

    # Крок 2: nonce для GCM (96 біт = 12 байтів)
    nonce = os.urandom(12)

    # Крок 3: захист AES-ключа через RSA-OAEP
    encrypted_aes_key = recipient_public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # Крок 4: шифрування даних AES-GCM
    aesgcm = AESGCM(aes_key)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)

    # Крок 5: упаковка пакету
    key_len = len(encrypted_aes_key)
    header = struct.pack(">I", key_len)   # 4 байти big-endian unsigned int
    return header + encrypted_aes_key + nonce + ciphertext_with_tag


def decrypt(package: bytes, private_key: RSAPrivateKey) -> bytes:
    """
    Розшифровує пакет .smsg приватним ключем отримувача.

    АЛГОРИТМ (покроково):
    ---------------------

    КРОК 1: Розбір заголовка
        key_len = struct.unpack(">I", package[:4])[0]

        Перевірка: якщо пакет < 4 байт — це не .smsg файл.

    КРОК 2: Виділення компонентів
        encrypted_aes_key = package[4 : 4 + key_len]
        nonce = package[4 + key_len : 4 + key_len + 12]
        ciphertext_with_tag = package[4 + key_len + 12:]

        Перевірка: якщо пакет замалий — пошкоджений або підроблений.

    КРОК 3: Розшифрування AES-ключа RSA-OAEP
        aes_key = private_key.decrypt(
            encrypted_aes_key,
            padding.OAEP(...),
        )

        Якщо приватний ключ не відповідає публічному (не та пара),
        RSA-операція дасть сміття, і GCM-автентифікація
        виявить помилку на наступному кроці.

    КРОК 4: Розшифрування та автентифікація AES-GCM
        aesgcm = AESGCM(aes_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)

        AESGCM.decrypt() автоматично:
        • Розшифровує дані (CTR mode)
        • Перевіряє GCM tag (GHASH)
        • Підіймає InvalidTag при будь-якій підробці

    ПАРАМЕТРИ:
    -----------
    package: bytes — зашифрований пакет .smsg
    private_key: RSAPrivateKey — приватний ключ отримувача

    ПОВЕРТАЄ:
    ----------
    bytes: відкриті дані

    ВИКЛИКАЄ:
    ----------
    ValueError — при пошкодженому пакеті, неправильному ключі
                 або підроблених даних (authentication failure)
    """
    # Крок 1: Розбір заголовка (4 байти big-endian)
    if len(package) < 4:
        raise ValueError("Пошкоджений пакет: недостатньо даних.")

    key_len = struct.unpack(">I", package[:4])[0]
    offset = 4

    # Крок 2: Перевірка розміру пакету
    if len(package) < offset + key_len + 12:
        raise ValueError("Пошкоджений пакет: неправильна структура.")

    encrypted_aes_key = package[offset: offset + key_len]
    offset += key_len
    nonce = package[offset: offset + 12]
    offset += 12
    ciphertext_with_tag = package[offset:]

    # Крок 3: Розшифрування AES-ключа RSA-OAEP
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
        # RSA decryption failed — неправильний приватний ключ
        raise ValueError("Неправильний ключ або пошкоджений пакет.")

    # Крок 4: Розшифрування AES-GCM (з автентифікацією цілісності)
    try:
        aesgcm = AESGCM(aes_key)
        return aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    except Exception:
        # GCM tag verification failed — дані підроблені або пошкоджені
        raise ValueError("Помилка автентифікації: файл пошкоджено або підроблено.")


# ============================================================================ #
#  ЗРУЧНІ ОБГОРТКИ ДЛЯ ТЕКСТУ ТА ФАЙЛІВ                                       #
# ============================================================================ #

def encrypt_text(text: str, recipient_public_key: RSAPublicKey) -> bytes:
    """
    Шифрує текстовий рядок у формат .smsg.

    Кодування: UTF-8 — стандартне кодування Unicode, сумісне
    з усіма сучасними системами. Кожен символ займає
    1-4 байти (ASCII = 1 байт, кирилиця = 2 байти).

    ПАРАМЕТРИ:
    -----------
    text: str — текстове повідомлення для шифрування
    recipient_public_key: RSAPublicKey — публічний ключ отримувача

    ПОВЕРТАЄ:
    ----------
    bytes: зашифрований бінарний пакет .smsg
    """
    return encrypt(text.encode("utf-8"), recipient_public_key)


def decrypt_text(package: bytes, private_key: RSAPrivateKey) -> str:
    """
    Розшифровує пакет і повертає текстовий рядок.

    Декодування: UTF-8 з обробкою помилок (strict mode).
    Якщо дані були пошкоджені (але GCM tag пройшов — малоймовірно),
    UnicodeDecodeError вкаже на проблему.

    ПАРАМЕТРИ:
    -----------
    package: bytes — зашифрований пакет .smsg
    private_key: RSAPrivateKey — приватний ключ отримувача

    ПОВЕРТАЄ:
    ----------
    str: розшифрований текст
    """
    return decrypt(package, private_key).decode("utf-8")


def encrypt_file(file_path: str, recipient_public_key: RSAPublicKey) -> bytes:
    """
    Читає файл і повертає зашифрований пакет .smsg.

    ОСОБЛИВІСТЬ: Оригінальне ім'я файлу зберігається у перших
    байтах відкритого тексту, щоб при дешифруванні відновити
    оригінальне ім'я.

    ФОРМАТ ВІДКРИТОГО ТЕКСТУ:
    --------------------------
    [2 bytes]  довжина імені файлу (big-endian uint16, max 65535)
    [N bytes]  ім'я файлу у кодуванні UTF-8
    [остаток]  вміст файлу (довільні байти)

    2 байти для довжини імені достатньо, оскільки:
    • Максимальна довжина імені файлу в NTFS = 255 символів
    • У UTF-8 це максимум 255 * 4 = 1020 байт << 65535

    ПАРАМЕТРИ:
    -----------
    file_path: str — шлях до файлу для шифрування
    recipient_public_key: RSAPublicKey — публічний ключ отримувача

    ПОВЕРТАЄ:
    ----------
    bytes: зашифрований пакет .smsg
    """
    # Виділення імені файлу з шляху
    filename = os.path.basename(file_path)

    # Кодування імені у UTF-8
    filename_bytes = filename.encode("utf-8")

    # Читання вмісту файлу у двійковому режимі
    with open(file_path, "rb") as f:
        file_content = f.read()

    # Формування структури: [довжина: 2 байти] + [ім'я] + [вміст]
    name_len = struct.pack(">H", len(filename_bytes))  # uint16 big-endian
    plaintext = name_len + filename_bytes + file_content

    return encrypt(plaintext, recipient_public_key)


def decrypt_file(package: bytes, private_key: RSAPrivateKey) -> tuple[str, bytes]:
    """
    Розшифровує файловий пакет і відновлює оригінальне ім'я файлу.

    АЛГОРИТМ:
    ---------
    1. Розшифрування основного пакету (RSA-OAEP + AES-GCM)
    2. Розбір структури: [довжина імені: 2 байти] + [ім'я] + [вміст]
    3. Повернення (оригінальне_ім'я_файлу, вміст_файлу)

    ПАРАМЕТРИ:
    -----------
    package: bytes — зашифрований пакет .smsg
    private_key: RSAPrivateKey — приватний ключ отримувача

    ПОВЕРТАЄ:
    ----------
    tuple[str, bytes]: (оригінальне_ім'я_файлу, вміст_файлу)
    """
    # Крок 1: Розшифрування пакету
    plaintext = decrypt(package, private_key)

    # Крок 2: Розбір структури
    name_len = struct.unpack(">H", plaintext[:2])[0]           # 2 байти big-endian
    filename = plaintext[2: 2 + name_len].decode("utf-8")      # Ім'я файлу
    file_content = plaintext[2 + name_len:]                        # Вміст файлу

    return filename, file_content
