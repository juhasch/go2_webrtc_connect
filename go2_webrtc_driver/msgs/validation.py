"""
WebRTC Data Channel Validation Module

This module provides validation functionality for WebRTC data channels, implementing
the authentication and encryption protocols required for secure communication with
Unitree Go2 robots.

The validation process includes:
- Key exchange and validation
- MD5-based encryption with prefixed keys
- Base64 encoding for secure transmission
- Response handling for validation success/failure

Example:
    >>> from go2_webrtc_driver.msgs.validation import WebRTCDataChannelValidation
    >>> 
    >>> # Initialize validation handler
    >>> validator = WebRTCDataChannelValidation(channel, pub_sub)
    >>> 
    >>> # Set validation callback
    >>> validator.set_on_validate_callback(lambda: print("Validation successful"))
    >>> 
    >>> # Handle validation response
    >>> await validator.handle_response({"data": "Validation Ok."})
"""

import logging
import base64
from typing import Callable, List, Optional, Dict, Any
from ..constants import DATA_CHANNEL_TYPE


class WebRTCDataChannelValidation:
    """
    WebRTC data channel validation handler.
    
    This class manages the validation process for WebRTC data channels, including
    key exchange, encryption, and response handling. It implements the security
    protocol required for authenticated communication with Unitree Go2 robots.
    
    Attributes:
        channel: The WebRTC data channel instance
        publish: Publisher function for sending messages
        on_validate_callbacks: List of callbacks to execute on successful validation
        key: The validation key received from the server
    
    Example:
        >>> validator = WebRTCDataChannelValidation(channel, pub_sub)
        >>> validator.set_on_validate_callback(on_validation_success)
        >>> await validator.handle_response(response_message)
    """
    
    def __init__(self, channel, pub_sub):
        """
        Initialize the WebRTC data channel validation handler.
        
        Args:
            channel: The WebRTC data channel instance
            pub_sub: The publish-subscribe system for message handling
        
        Example:
            >>> validator = WebRTCDataChannelValidation(channel, pub_sub)
        """
        self.channel = channel
        self.publish = pub_sub.publish
        self.on_validate_callbacks: List[Callable] = []
        self.key: str = ""

    def set_on_validate_callback(self, callback: Optional[Callable]) -> None:
        """
        Register a callback to be called upon successful validation.
        
        Args:
            callback: Function to call when validation succeeds. Must be callable.
        
        Example:
            >>> def on_success():
            ...     print("Channel validated successfully")
            >>> validator.set_on_validate_callback(on_success)
        """
        if callback and callable(callback):
            self.on_validate_callbacks.append(callback)
    
    async def handle_response(self, message: Dict[str, Any]) -> None:
        """
        Handle validation response from the server.
        
        Processes validation responses and either completes the validation process
        or initiates key exchange if additional validation is required.
        
        Args:
            message: Response message containing validation data
        
        Example:
            >>> # Successful validation
            >>> await validator.handle_response({"data": "Validation Ok."})
            >>> 
            >>> # Key exchange required
            >>> await validator.handle_response({"data": "validation_key_123"})
        """
        if message.get("data") == "Validation Ok.":
            logging.info("Validation succeed")
            for callback in self.on_validate_callbacks:
                callback()
        else:
            self.channel._setReadyState("open")
            self.key = message.get("data")
            await self.publish(
                "",
                self.encrypt_key(self.key),
                DATA_CHANNEL_TYPE["VALIDATION"],
            )

    async def handle_err_response(self, message: Dict[str, Any]) -> None:
        """
        Handle error response requiring validation.
        
        Processes error messages that indicate validation is needed and initiates
        the key exchange process.
        
        Args:
            message: Error message containing validation requirements
        
        Example:
            >>> await validator.handle_err_response({"info": "Validation Needed."})
        """
        if message.get("info") == "Validation Needed.":
            await self.publish(
                "",
                self.encrypt_key(self.key),
                DATA_CHANNEL_TYPE["VALIDATION"],
            )
        
    @staticmethod
    def hex_to_base64(hex_str: str) -> str:
        """
        Convert hexadecimal string to Base64 encoded string.
        
        Args:
            hex_str: Hexadecimal string to convert
            
        Returns:
            Base64 encoded string
        
        Example:
            >>> result = WebRTCDataChannelValidation.hex_to_base64("48656c6c6f")
            >>> print(result)  # "SGVsbG8="
        """
        # Convert hex string to bytes
        bytes_array = bytes.fromhex(hex_str)
        # Encode the bytes to Base64 and return as a string
        return base64.b64encode(bytes_array).decode("utf-8")
    
    @staticmethod
    def encrypt_by_md5(input_str: str) -> str:
        """
        Encrypt a string using MD5 hash algorithm.
        
        Args:
            input_str: String to encrypt
            
        Returns:
            MD5 hash as hexadecimal string
        
        Example:
            >>> result = WebRTCDataChannelValidation.encrypt_by_md5("test")
            >>> print(len(result))  # 32 (MD5 hash length)
        """
        import hashlib
        # Create an MD5 hash object
        hash_obj = hashlib.md5()
        # Update the hash object with the bytes of the input string
        hash_obj.update(input_str.encode("utf-8"))
        # Return the hex digest of the hash
        return hash_obj.hexdigest()

    @staticmethod
    def encrypt_key(key: str) -> str:
        """
        Encrypt a validation key using the Unitree Go2 protocol.
        
        This method implements the specific encryption protocol required for
        Unitree Go2 authentication:
        1. Prefix the key with "UnitreeGo2_"
        2. Generate MD5 hash of the prefixed key
        3. Convert the hash to Base64 encoding
        
        Args:
            key: The validation key to encrypt
            
        Returns:
            Base64 encoded encrypted key
        
        Example:
            >>> encrypted = WebRTCDataChannelValidation.encrypt_key("abc123")
            >>> print(type(encrypted))  # <class 'str'>
        """
        # Append the prefix to the key
        prefixed_key = f"UnitreeGo2_{key}"
        # Encrypt the key using MD5 and convert to hex string
        encrypted = WebRTCDataChannelValidation.encrypt_by_md5(prefixed_key)
        # Convert the hex string to Base64
        return WebRTCDataChannelValidation.hex_to_base64(encrypted)
