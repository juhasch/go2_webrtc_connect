"""
Encryption and Decryption Utilities
===================================

This module provides cryptographic functions for secure communication with the Unitree Go2 robot.
It implements both AES (Advanced Encryption Standard) and RSA (Rivest-Shamir-Adleman) encryption
algorithms for different security requirements.

AES Functions:
- Symmetric encryption/decryption using ECB mode with PKCS5 padding
- Key generation using UUID-based random strings
- Used for encrypting large data payloads

RSA Functions:
- Asymmetric encryption using public keys
- PKCS1 v1.5 padding scheme
- Used for encrypting AES keys and small sensitive data

Security Notes:
- AES keys are 256-bit (32 bytes) for strong encryption
- RSA encryption handles chunking for large data automatically
- All encrypted data is Base64 encoded for safe transmission
"""

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import base64
import uuid
import binascii


# AES Encryption Functions
# ======================

def _generate_uuid() -> str:
    """
    Generate a UUID and return it as a 32-character hexadecimal string.
    
    This function is used internally to create cryptographically secure random keys
    for AES encryption. The UUID is converted to a hex string to ensure it's exactly
    32 characters long (256 bits).
    
    Returns:
        str: A 32-character hexadecimal string suitable for use as an AES-256 key
        
    Example:
        >>> key = _generate_uuid()
        >>> len(key)
        32
        >>> isinstance(key, str)
        True
    """
    uuid_32 = uuid.uuid4().bytes  
    uuid_32_hex_string = binascii.hexlify(uuid_32).decode('utf-8')
    return uuid_32_hex_string


def pad(data: str) -> bytes:
    """
    Pad data to be a multiple of 16 bytes (AES block size) using PKCS5 padding.
    
    PKCS5 padding adds bytes to the end of the data, where each added byte has a value
    equal to the number of bytes added. This ensures the data length is a multiple
    of the AES block size (16 bytes).
    
    Args:
        data (str): The plaintext data to be padded
        
    Returns:
        bytes: The padded data as bytes, ready for AES encryption
        
    Example:
        >>> padded = pad("Hello World")
        >>> len(padded) % 16
        0
    """
    block_size = AES.block_size
    padding = block_size - len(data) % block_size
    padded_data = data + chr(padding) * padding
    return padded_data.encode('utf-8')


def unpad(data: bytes) -> str:
    """
    Remove PKCS5 padding from decrypted data.
    
    This function removes the padding bytes added by the pad() function,
    restoring the original plaintext data.
    
    Args:
        data (bytes): The padded data bytes from AES decryption
        
    Returns:
        str: The original unpadded plaintext data
        
    Example:
        >>> original = "Hello World"
        >>> padded = pad(original)
        >>> unpadded = unpad(padded)
        >>> unpadded == original
        True
    """
    padding = data[-1]
    return data[:-padding].decode('utf-8')


def aes_encrypt(data: str, key: str) -> str:
    """
    Encrypt data using AES-256 in ECB mode with PKCS5 padding.
    
    This function encrypts the given plaintext data using AES-256 encryption.
    The encrypted data is Base64 encoded for safe transmission over text-based
    protocols.
    
    Args:
        data (str): The plaintext data to encrypt
        key (str): The 32-character AES-256 key
        
    Returns:
        str: Base64-encoded encrypted data
        
    Raises:
        ValueError: If the key is not exactly 32 characters long
        
    Example:
        >>> key = generate_aes_key()
        >>> encrypted = aes_encrypt("Hello World", key)
        >>> len(encrypted) > 0
        True
    """
    # Ensure key is 32 bytes for AES-256
    if len(key) != 32:
        raise ValueError("AES key must be exactly 32 characters long")
    
    key_bytes = key.encode('utf-8')

    # Pad the data to ensure it is a multiple of block size
    padded_data = pad(data)

    # Create AES cipher in ECB mode
    cipher = AES.new(key_bytes, AES.MODE_ECB)

    # Encrypt data
    encrypted_data = cipher.encrypt(padded_data)

    # Encode encrypted data to Base64
    encoded_encrypted_data = base64.b64encode(encrypted_data).decode('utf-8')

    return encoded_encrypted_data


def aes_decrypt(encrypted_data: str, key: str) -> str:
    """
    Decrypt data using AES-256 in ECB mode with PKCS5 padding.
    
    This function decrypts Base64-encoded encrypted data using the provided
    AES-256 key, removing padding to restore the original plaintext.
    
    Args:
        encrypted_data (str): Base64-encoded encrypted data
        key (str): The 32-character AES-256 key used for encryption
        
    Returns:
        str: The decrypted plaintext data
        
    Raises:
        ValueError: If the key is not exactly 32 characters long
        base64.binascii.Error: If the encrypted data is not valid Base64
        
    Example:
        >>> key = generate_aes_key()
        >>> original = "Hello World"
        >>> encrypted = aes_encrypt(original, key)
        >>> decrypted = aes_decrypt(encrypted, key)
        >>> decrypted == original
        True
    """
    # Ensure key is 32 bytes for AES-256
    if len(key) != 32:
        raise ValueError("AES key must be exactly 32 characters long")
    
    key_bytes = key.encode('utf-8')

    # Decode Base64 encrypted data
    encrypted_data_bytes = base64.b64decode(encrypted_data)

    # Create AES cipher in ECB mode
    cipher = AES.new(key_bytes, AES.MODE_ECB)

    # Decrypt data
    decrypted_padded_data = cipher.decrypt(encrypted_data_bytes)

    # Unpad the decrypted data
    decrypted_data = unpad(decrypted_padded_data)

    return decrypted_data


def generate_aes_key() -> str:
    """
    Generate a cryptographically secure AES-256 key.
    
    This function creates a new random 32-character key suitable for AES-256
    encryption. Each call returns a unique key.
    
    Returns:
        str: A 32-character hexadecimal string for use as an AES-256 key
        
    Example:
        >>> key1 = generate_aes_key()
        >>> key2 = generate_aes_key()
        >>> len(key1) == 32
        True
        >>> key1 != key2
        True
    """
    return _generate_uuid()


# RSA Encryption Functions
# =======================

def rsa_load_public_key(pem_data: str) -> RSA.RsaKey:
    """
    Load an RSA public key from a Base64-encoded PEM string.
    
    This function decodes a Base64-encoded RSA public key and returns
    an RSA key object that can be used for encryption operations.
    
    Args:
        pem_data (str): Base64-encoded RSA public key data
        
    Returns:
        RSA.RsaKey: An RSA key object for encryption operations
        
    Raises:
        ValueError: If the PEM data is invalid or not a valid RSA key
        base64.binascii.Error: If the PEM data is not valid Base64
        
    Example:
        >>> # Assuming valid_pem_data is a Base64-encoded RSA public key
        >>> public_key = rsa_load_public_key(valid_pem_data)
        >>> isinstance(public_key, RSA.RsaKey)
        True
    """
    key_bytes = base64.b64decode(pem_data)
    return RSA.import_key(key_bytes)


def rsa_encrypt(data: str, public_key: RSA.RsaKey) -> str:
    """
    Encrypt data using RSA with PKCS1 v1.5 padding.
    
    This function encrypts data using RSA public key cryptography. It automatically
    handles chunking for data larger than the key size allows. The encrypted data
    is Base64 encoded for safe transmission.
    
    Args:
        data (str): The plaintext data to encrypt
        public_key (RSA.RsaKey): The RSA public key for encryption
        
    Returns:
        str: Base64-encoded encrypted data
        
    Raises:
        ValueError: If the public key is invalid or data cannot be encrypted
        
    Example:
        >>> # Assuming valid_public_key is an RSA public key
        >>> encrypted = rsa_encrypt("Hello World", valid_public_key)
        >>> len(encrypted) > 0
        True
        
    Note:
        The maximum chunk size for RSA encryption is (key_size_in_bytes - 11)
        due to PKCS1 v1.5 padding requirements.
    """
    cipher = PKCS1_v1_5.new(public_key)

    # Maximum chunk size for encryption with RSA/ECB/PKCS1Padding is key size - 11 bytes
    max_chunk_size = public_key.size_in_bytes() - 11
    data_bytes = data.encode('utf-8')

    encrypted_bytes = bytearray()
    for i in range(0, len(data_bytes), max_chunk_size):
        chunk = data_bytes[i:i + max_chunk_size]
        encrypted_chunk = cipher.encrypt(chunk)
        encrypted_bytes.extend(encrypted_chunk)

    # Base64 encode the final encrypted data
    encoded_encrypted_data = base64.b64encode(encrypted_bytes).decode('utf-8')
    return encoded_encrypted_data
