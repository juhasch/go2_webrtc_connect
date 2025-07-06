"""
Unitree Authentication and Communication Module
==============================================

This module handles authentication and communication with Unitree's remote servers
and local Go2 robots. It provides functions for remote API communication, local
HTTP communication, and SDP (Session Description Protocol) exchange for WebRTC
connection establishment.

Key Features:
- Remote API authentication with Unitree's cloud services
- Local HTTP communication with Go2 robots
- SDP exchange for WebRTC connection establishment
- Automatic fallback between connection methods
- Encryption and decryption for secure communication

Communication Methods:
- Remote: Via Unitree's global API servers with authentication
- Local Old Method: Direct HTTP communication on port 8081
- Local New Method: Encrypted communication on port 9991

Security:
- All communications are encrypted using AES and RSA
- Authentication tokens are used for remote connections
- Local connections use public key exchange for security
"""

import hashlib
import time
import requests
import urllib.parse
import base64
import logging
import json
import sys
from typing import Optional, Dict, Any, Union
from Crypto.PublicKey import RSA

from .encryption import aes_encrypt, generate_aes_key, rsa_encrypt, aes_decrypt, rsa_load_public_key


def _calc_local_path_ending(data1: str) -> str:
    """
    Calculate local path ending based on data string for new connection method.
    
    This function processes the last 10 characters of the provided data string
    to generate a path ending used in the new local connection protocol.
    
    Args:
        data1: Input data string to process
        
    Returns:
        str: Generated path ending string
        
    Example:
        >>> ending = _calc_local_path_ending("sample_data_string")
        >>> isinstance(ending, str)
        True
    """
    # Character mapping array
    str_arr = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

    # Extract the last 10 characters of data1
    last_10_chars = data1[-10:]

    # Split into chunks of size 2
    chunked = [last_10_chars[i:i + 2] for i in range(0, len(last_10_chars), 2)]

    # Process chunks and map to indices
    array_list = []
    for chunk in chunked:
        if len(chunk) > 1:
            second_char = chunk[1]
            try:
                index = str_arr.index(second_char)
                array_list.append(index)
            except ValueError:
                logging.warning(f"Character {second_char} not found in mapping array")

    # Convert to string without separators
    return ''.join(map(str, array_list))


def make_remote_request(
    path: str, 
    body: Dict[str, Any], 
    token: str, 
    method: str = "GET"
) -> Dict[str, Any]:
    """
    Make authenticated requests to Unitree's remote API servers.
    
    This function handles all communication with Unitree's cloud services,
    including proper authentication, headers, and request signing.
    
    Args:
        path: API endpoint path relative to base URL
        body: Request body data as dictionary
        token: Authentication token for the request
        method: HTTP method ("GET" or "POST")
        
    Returns:
        Dict containing the JSON response from the server
        
    Raises:
        requests.exceptions.RequestException: If the request fails
        
    Example:
        >>> response = make_remote_request(
        ...     "login/email", 
        ...     {"email": "user@example.com", "password": "hash"}, 
        ...     "", 
        ...     "POST"
        ... )
        >>> response.get("code") == 100  # Success code
        True
    """
    # API configuration constants
    APP_SIGN_SECRET = "XyvkwK45hp5PHfA8"
    UM_CHANNEL_KEY = "UMENG_CHANNEL"
    BASE_URL = "https://global-robot-api.unitree.com/"
    
    # Generate request timestamps and security tokens
    app_timestamp = str(int(round(time.time() * 1000)))
    app_nonce = hashlib.md5(app_timestamp.encode()).hexdigest()
    
    # Create request signature
    sign_str = f"{APP_SIGN_SECRET}{app_timestamp}{app_nonce}"
    app_sign = hashlib.md5(sign_str.encode()).hexdigest()
    
    # Calculate timezone offset
    timezone_offset = time.localtime().tm_gmtoff // 3600
    minutes_offset = abs(time.localtime().tm_gmtoff % 3600 // 60)
    sign = "+" if timezone_offset >= 0 else "-"
    app_timezone = f"GMT{sign}{abs(timezone_offset):02d}:{minutes_offset:02d}"
    
    # Prepare request headers with authentication and device information
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "DeviceId": "Samsung/GalaxyS20/SM-G981B/s20/10/29",
        "AppTimezone": app_timezone,
        "DevicePlatform": "Android",
        "DeviceModel": "SM-G981B",
        "SystemVersion": "29",
        "AppVersion": "1.8.0",
        "AppLocale": "en_US",
        "AppTimestamp": app_timestamp,
        "AppNonce": app_nonce,
        "AppSign": app_sign,
        "Channel": UM_CHANNEL_KEY,
        "Token": token,
        "AppName": "Go2",
        "Host": "global-robot-api.unitree.com",
        "User-Agent": "Mozilla/5.0 (Linux; Android 15; SM-S931B Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/127.0.6533.103 Mobile Safari/537.36"
    }
    
    # Construct full URL
    url = BASE_URL + path
    
    # Execute request based on method
    if method.upper() == "GET":
        params = urllib.parse.urlencode(body)
        response = requests.get(url, params=params, headers=headers)
    else:
        encoded_body = urllib.parse.urlencode(body)
        response = requests.post(url, data=encoded_body, headers=headers)

    return response.json()


def make_local_request(
    path: str, 
    body: Optional[Union[str, Dict[str, Any]]] = None, 
    headers: Optional[Dict[str, str]] = None
) -> Optional[requests.Response]:
    """
    Make HTTP requests to local Go2 robot.
    
    This function handles direct HTTP communication with the robot on the
    local network, typically used for SDP exchange and configuration.
    
    Args:
        path: Full URL for the request
        body: Request body (string or dictionary)
        headers: HTTP headers for the request
        
    Returns:
        requests.Response object if successful, None otherwise
        
    Example:
        >>> response = make_local_request(
        ...     "http://192.168.12.1:8081/offer",
        ...     sdp_data,
        ...     {"Content-Type": "application/json"}
        ... )
        >>> response is not None
        True
    """
    try:
        response = requests.post(url=path, data=body, headers=headers)
        response.raise_for_status()
        
        if response.status_code == 200:
            return response
        else:
            logging.warning(f"Unexpected status code: {response.status_code}")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Local request failed: {e}")
        return None


def send_sdp_to_remote_peer(
    serial: str, 
    sdp: str, 
    access_token: str, 
    public_key: RSA.RsaKey
) -> Optional[str]:
    """
    Send SDP offer to remote Go2 robot via Unitree's servers.
    
    This function handles the SDP exchange for remote WebRTC connections
    through Unitree's cloud infrastructure. The SDP data is encrypted
    before transmission for security.
    
    Args:
        serial: Robot serial number
        sdp: SDP offer data as JSON string
        access_token: Valid authentication token
        public_key: RSA public key for encryption
        
    Returns:
        Decrypted SDP answer from the robot, or None if failed
        
    Raises:
        ValueError: If the response indicates an error
        SystemExit: If the device is not online
        
    Example:
        >>> answer = send_sdp_to_remote_peer(
        ...     "B42D2000XXXXXXXX",
        ...     sdp_offer_json,
        ...     auth_token,
        ...     public_key
        ... )
        >>> answer is not None
        True
    """
    logging.info("Sending SDP to Go2 via remote servers...")
    
    # Generate AES key for encryption
    aes_key = generate_aes_key()
    
    # Prepare encrypted request body
    path = "webrtc/connect"
    body = {
        "sn": serial,
        "sk": rsa_encrypt(aes_key, public_key),
        "data": aes_encrypt(sdp, aes_key),
        "timeout": 5
    }
    
    # Send request to Unitree's servers
    response = make_remote_request(path, body, token=access_token, method="POST")
    
    # Process response
    if response.get("code") == 100:
        logging.info("Received SDP answer from Go2!")
        return aes_decrypt(response['data'], aes_key)
    elif response.get("code") == 1000:
        logging.error("Device not online")
        print("Device not online")
        sys.exit(1)
    else:
        error_msg = f"Failed to receive SDP answer: {response}"
        logging.error(error_msg)
        raise ValueError(error_msg)


def send_sdp_to_local_peer(ip: str, sdp: str) -> Optional[str]:
    """
    Send SDP offer to local Go2 robot with automatic fallback.
    
    This function attempts to send SDP data to a local robot using two
    different methods, automatically falling back if the first method fails.
    
    Args:
        ip: Robot IP address
        sdp: SDP offer data as JSON string
        
    Returns:
        SDP answer from the robot, or None if both methods fail
        
    Example:
        >>> answer = send_sdp_to_local_peer("192.168.12.1", sdp_offer)
        >>> answer is not None
        True
    """
    # Try the old method first (port 8081)
    try:
        logging.info("Attempting SDP exchange using legacy method...")
        response = send_sdp_to_local_peer_old_method(ip, sdp)
        if response:
            logging.info("SDP exchange successful using legacy method")
            return response
        else:
            logging.warning("Legacy method failed, trying new method...")
    except Exception as e:
        logging.error(f"Legacy method error: {e}")
        logging.info("Falling back to new method...")

    # Try the new method (port 9991)
    try:
        response = send_sdp_to_local_peer_new_method(ip, sdp)
        if response:
            logging.info("SDP exchange successful using new method")
            return response
        else:
            logging.error("New method also failed")
            return None
    except Exception as e:
        logging.error(f"New method error: {e}")
        return None


def send_sdp_to_local_peer_old_method(ip: str, sdp: str) -> Optional[str]:
    """
    Send SDP offer using the legacy local communication method.
    
    This method uses direct HTTP POST to the robot's legacy API endpoint
    on port 8081. This is the original communication method.
    
    Args:
        ip: Robot IP address
        sdp: SDP offer data as JSON string
        
    Returns:
        SDP answer from the robot, or None if failed
        
    Raises:
        ValueError: If the response is invalid
        requests.exceptions.RequestException: If the request fails
    """
    try:
        url = f"http://{ip}:8081/offer"
        headers = {'Content-Type': 'application/json'}
        
        response = make_local_request(url, body=sdp, headers=headers)
        
        if response and response.status_code == 200:
            logging.debug(f"Received SDP answer: {response.text}")
            return response.text
        else:
            error_msg = f"Failed to receive SDP answer: {response.status_code if response else 'No response'}"
            raise ValueError(error_msg)

    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending SDP via legacy method: {e}")
        return None


def send_sdp_to_local_peer_new_method(ip: str, sdp: str) -> Optional[str]:
    """
    Send SDP offer using the new encrypted local communication method.
    
    This method uses a two-step process:
    1. Get the robot's public key from the /con_notify endpoint
    2. Send encrypted SDP data to the /con_ing_* endpoint
    
    Args:
        ip: Robot IP address
        sdp: SDP offer data as JSON string
        
    Returns:
        Decrypted SDP answer from the robot, or None if failed
        
    Raises:
        requests.exceptions.RequestException: If network requests fail
        json.JSONDecodeError: If JSON parsing fails
        base64.binascii.Error: If base64 decoding fails
    """
    try:
        # Step 1: Get public key information
        notify_url = f"http://{ip}:9991/con_notify"
        response = make_local_request(notify_url, body=None, headers=None)
        
        if not response:
            raise ValueError("Failed to receive public key response")

        # Decode the base64 response
        decoded_response = base64.b64decode(response.text).decode('utf-8')
        logging.debug(f"Received con_notify response: {decoded_response}")

        # Parse JSON and extract public key
        decoded_json = json.loads(decoded_response)
        data1 = decoded_json.get('data1')
        
        if not data1:
            raise ValueError("No public key data found in response")

        # Extract public key and calculate path ending
        public_key_pem = data1[10:len(data1)-10]
        path_ending = _calc_local_path_ending(data1)

        # Step 2: Encrypt and send SDP data
        aes_key = generate_aes_key()
        public_key = rsa_load_public_key(public_key_pem)

        # Prepare encrypted request body
        body = {
            "data1": aes_encrypt(sdp, aes_key),
            "data2": rsa_encrypt(aes_key, public_key),
        }

        # Send encrypted SDP data
        ing_url = f"http://{ip}:9991/con_ing_{path_ending}"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        response = make_local_request(ing_url, body=json.dumps(body), headers=headers)

        if response:
            # Decrypt and return the response
            decrypted_response = aes_decrypt(response.text, aes_key)
            logging.debug(f"Received con_ing_{path_ending} response: {decrypted_response}")
            return decrypted_response
        else:
            raise ValueError("Failed to receive encrypted SDP response")

    except (requests.exceptions.RequestException, json.JSONDecodeError, base64.binascii.Error) as e:
        logging.error(f"Error in new method SDP exchange: {e}")
        return None


