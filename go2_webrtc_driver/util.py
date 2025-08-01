"""
Utility Functions for Go2 WebRTC Driver
=======================================

This module provides utility functions for the Go2 WebRTC driver, including
authentication, key management, and helper functions for data processing.

Key Features:
- Token-based authentication with Unitree's backend
- RSA public key fetching and management
- TURN server configuration retrieval
- Data extraction utilities
- Status display formatting

Authentication Flow:
1. User credentials are hashed using MD5
2. Authentication token is retrieved from Unitree's API
3. Public key is fetched for encryption
4. TURN server info is obtained for remote connections

Security:
- All network communications use HTTPS
- Passwords are MD5 hashed before transmission
- AES keys are encrypted with RSA before transmission
- Error handling prevents credential leakage
"""

import hashlib
import json
import logging
import random
import requests
import time
import sys
from typing import Optional, Dict, Any, Union
from Crypto.PublicKey import RSA
from .unitree_auth import make_remote_request
from .encryption import rsa_encrypt, rsa_load_public_key, aes_decrypt, generate_aes_key


def _generate_md5(string: str) -> str:
    """
    Generate MD5 hash of a string.
    
    This function creates an MD5 hash of the input string, commonly used
    for password hashing in the authentication process.
    
    Args:
        string (str): The input string to hash
        
    Returns:
        str: The MD5 hash as a hexadecimal string
        
    Example:
        >>> hash_val = _generate_md5("password123")
        >>> len(hash_val)
        32
        >>> isinstance(hash_val, str)
        True
        
    Note:
        MD5 is used for compatibility with Unitree's authentication system.
        For security-critical applications, consider using stronger hashing
        algorithms like SHA-256 or bcrypt.
    """
    md5_hash = hashlib.md5(string.encode())
    return md5_hash.hexdigest()


def generate_uuid() -> str:
    """
    Generate a UUID-like string using a custom format.
    
    This function generates a UUID-like identifier string following the pattern
    "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx" where x is any hexadecimal digit
    and y is one of 8, 9, A, or B.
    
    Returns:
        str: A UUID-like string in the standard format
        
    Example:
        >>> uuid_str = generate_uuid()
        >>> len(uuid_str)
        36
        >>> uuid_str.count('-')
        4
        >>> uuid_str[14]  # Should be '4'
        '4'
    """
    def replace_char(char: str) -> str:
        """Helper function to replace x and y characters with appropriate values."""
        rand = random.randint(0, 15)
        if char == "x":
            return format(rand, 'x')
        elif char == "y":
            return format((rand & 0x3) | 0x8, 'x')
        return char

    uuid_template = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
    return ''.join(replace_char(char) if char in 'xy' else char for char in uuid_template)


def get_nested_field(message: Dict[str, Any], *fields: str) -> Optional[Any]:
    """
    Extract a nested field from a dictionary structure.
    
    This function safely traverses a nested dictionary structure to extract
    a specific field value. It returns None if any level in the path doesn't exist.
    
    Args:
        message (Dict[str, Any]): The dictionary to traverse
        *fields (str): Variable number of field names representing the path
        
    Returns:
        Optional[Any]: The value at the specified path, or None if not found
        
    Example:
        >>> data = {"user": {"profile": {"name": "John"}}}
        >>> get_nested_field(data, "user", "profile", "name")
        'John'
        >>> get_nested_field(data, "user", "settings", "theme")
        None
        >>> get_nested_field(data, "nonexistent")
        None
    """
    current_level = message
    for field in fields:
        if isinstance(current_level, dict) and field in current_level:
            current_level = current_level[field]
        else:
            return None
    return current_level


def fetch_token(email: str, password: str) -> Optional[str]:
    """
    Obtain a fresh authentication token from Unitree's backend server.
    
    This function authenticates with Unitree's remote API using email and password
    credentials. The password is MD5-hashed before transmission for security.
    
    Args:
        email (str): User's email address for authentication
        password (str): User's password (will be MD5-hashed)
        
    Returns:
        Optional[str]: The access token if authentication succeeds, None otherwise
        
    Raises:
        requests.exceptions.RequestException: If network request fails
        KeyError: If the response format is unexpected
        
    Example:
        >>> token = fetch_token("user@example.com", "password123")
        >>> if token:
        ...     print("Authentication successful")
        ... else:
        ...     print("Authentication failed")
        
    API Response Format:
        {
            "code": 100,  # Success code
            "data": {
                "accessToken": "your-jwt-token-here",
                "refreshToken": "refresh-token",
                "expiresIn": 3600
            }
        }
    """
    logging.info("Obtaining authentication token...")
    
    path = "login/email"
    body = {
        'email': email,
        'password': _generate_md5(password)
    }
    
    try:
        response = make_remote_request(path, body, token="", method="POST")
        
        if response.get("code") == 100:
            data = response.get("data", {})
            access_token = data.get("accessToken")
            
            if access_token:
                logging.info("Authentication token obtained successfully")
                return access_token
            else:
                logging.error("Access token not found in response")
                return None
        else:
            error_message = response.get("message", "Unknown error")
            logging.error(f"Authentication failed: {error_message}")
            return None
            
    except Exception as e:
        logging.error(f"Error during authentication: {e}")
        return None


def fetch_public_key() -> Optional[RSA.RsaKey]:
    """
    Obtain the RSA public key from Unitree's backend server.
    
    This function retrieves the public key used for encrypting sensitive data
    before transmission to Unitree's servers. The key is returned as an RSA
    key object ready for encryption operations.
    
    Returns:
        Optional[RSA.RsaKey]: The RSA public key object, or None if retrieval fails
        
    Raises:
        requests.exceptions.ConnectionError: If no internet connection is available
        requests.exceptions.RequestException: If the request fails
        ValueError: If the public key data is invalid
        
    Example:
        >>> public_key = fetch_public_key()
        >>> if public_key:
        ...     print(f"Key size: {public_key.size_in_bits()} bits")
        ... else:
        ...     print("Failed to fetch public key")
        
    API Response Format:
        {
            "code": 100,
            "data": "base64-encoded-public-key-pem-data"
        }
    """
    logging.info("Obtaining RSA public key...")
    path = "system/pubKey"
    
    try:
        response = make_remote_request(path, {}, token="", method="GET")

        if response.get("code") == 100:
            public_key_pem = response.get("data")
            
            if public_key_pem:
                try:
                    public_key = rsa_load_public_key(public_key_pem)
                    logging.info("RSA public key loaded successfully")
                    return public_key
                except Exception as e:
                    logging.error(f"Failed to load public key: {e}")
                    return None
            else:
                logging.error("Public key data not found in response")
                return None
        else:
            error_message = response.get("message", "Unknown error")
            logging.error(f"Failed to fetch public key: {error_message}")
            return None

    except requests.exceptions.ConnectionError as e:
        logging.warning("No internet connection available. Unable to fetch public key.")
        logging.debug(f"Connection error details: {e}")
        return None
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed while fetching public key: {e}")
        return None
        
    except Exception as e:
        logging.error(f"Unexpected error while fetching public key: {e}")
        return None


def fetch_turn_server_info(serial: str, access_token: str, public_key: RSA.RsaKey) -> Optional[Dict[str, Any]]:
    """
    Obtain TURN server configuration for remote WebRTC connections.
    
    This function retrieves TURN (Traversal Using Relays around NAT) server
    information required for establishing WebRTC connections through firewalls
    and NAT devices. The request is encrypted using the provided public key.
    
    Args:
        serial (str): The robot's serial number
        access_token (str): Valid authentication token
        public_key (RSA.RsaKey): RSA public key for encryption
        
    Returns:
        Optional[Dict[str, Any]]: TURN server configuration dictionary, or None if fails
        
    Raises:
        requests.exceptions.RequestException: If network request fails
        ValueError: If encryption fails or response is invalid
        
    Example:
        >>> turn_info = fetch_turn_server_info("B42D2000XXXXXXXX", token, public_key)
        >>> if turn_info:
        ...     print(f"TURN server: {turn_info.get('realm')}")
        ...     print(f"Username: {turn_info.get('user')}")
        
    Response Format:
        {
            "realm": "turn:turn.server.com:3478",
            "user": "username",
            "passwd": "password",
            "ttl": 3600
        }
    """
    logging.info("Obtaining TURN server configuration...")
    
    try:
        # Generate AES key for encrypting the serial number
        aes_key = generate_aes_key()
        
        path = "webrtc/account"
        body = {
            "sn": serial,
            "sk": rsa_encrypt(aes_key, public_key)
        }
        
        response = make_remote_request(path, body, token=access_token, method="POST")
        
        if response.get("code") == 100:
            encrypted_data = response.get("data")
            
            if encrypted_data:
                try:
                    # Decrypt the TURN server information
                    decrypted_data = aes_decrypt(encrypted_data, aes_key)
                    turn_info = json.loads(decrypted_data)
                    
                    logging.info("TURN server information obtained successfully")
                    return turn_info
                    
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse TURN server data: {e}")
                    return None
                except Exception as e:
                    logging.error(f"Failed to decrypt TURN server data: {e}")
                    return None
            else:
                logging.error("TURN server data not found in response")
                return None
        else:
            error_message = response.get("message", "Unknown error")
            logging.error(f"Failed to fetch TURN server info: {error_message}")
            return None
            
    except Exception as e:
        logging.error(f"Error obtaining TURN server info: {e}")
        return None


def print_status(status_type: str, status_message: str) -> None:
    """
    Print formatted status messages with timestamps.
    
    This function provides consistent status message formatting throughout
    the application, including timestamps and aligned output for better
    readability during connection and operation monitoring.
    
    Args:
        status_type (str): The type/category of the status message
        status_message (str): The actual status message content
        
    Example:
        >>> print_status("WebRTC Connection", "🟢 Connected")
        🕒 WebRTC Connection      : 🟢 Connected      (14:30:25)
        
        >>> print_status("Data Channel", "🟡 Connecting")
        🕒 Data Channel          : 🟡 Connecting     (14:30:26)
    """
    current_time = time.strftime("%H:%M:%S")
    print(f"🕒 {status_type:<25}: {status_message:<15} ({current_time})")


