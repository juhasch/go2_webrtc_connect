"""
Error Handling and Message Processing for Unitree Go2 Robot

This module provides comprehensive error handling functionality for the Unitree Go2 robot,
including error code translation, message formatting, and user-friendly error display.
It processes error messages from the robot and converts them to human-readable format.

The error handling system supports:
- Error code to hexadecimal conversion
- Error source and code lookup from predefined message dictionaries
- Timestamp formatting for error events
- Formatted error message display
- Fallback handling for unknown error codes

Key Features:
- Automatic error code translation using predefined message dictionary
- Human-readable timestamp formatting
- Color-coded error message display with emojis
- Graceful fallback for unknown error codes
- Support for multiple error sources and categories

Error Structure:
- Error messages contain timestamp, error source, and error code
- Error sources categorize the type of error (100-600 series)
- Error codes provide specific error information within each source
- Messages are formatted for clear user understanding

Usage Example:
    ```python
    from go2_webrtc_driver.msgs.error_handler import handle_error
    
    # Handle error message from robot
    error_message = {
        "data": [
            [1640995200, 100, 255]  # timestamp, source, code
        ]
    }
    handle_error(error_message)
    
    # Convert error code to hex
    hex_code = integer_to_hex_string(255)  # Returns "FF"
    
    # Get error text
    error_text = get_error_code_text(100, "FF")
    ```

Error Categories:
- 100 series: System errors
- 200 series: Communication errors
- 300 series: Motion control errors
- 400 series: Sensor errors
- 500 series: Power/battery errors
- 600 series: User/configuration errors

Author: Unitree Robotics
Version: 1.0
"""

from typing import Dict, List, Union, Tuple, Any
from ..constants import app_error_messages
import time


def integer_to_hex_string(error_code: int) -> str:
    """
    Convert an integer error code to a hexadecimal string
    
    This function converts an integer error code to its hexadecimal representation
    without the '0x' prefix, formatted in uppercase letters. It's used to convert
    error codes for lookup in the error message dictionary.
    
    Args:
        error_code (int): The error code as an integer (0-65535 typical range)
        
    Returns:
        str: The error code as a hexadecimal string, without the '0x' prefix, in uppercase
        
    Raises:
        ValueError: If the input is not an integer
        
    Example:
        ```python
        # Convert integer error code to hex
        hex_code = integer_to_hex_string(255)  # Returns "FF"
        hex_code = integer_to_hex_string(16)   # Returns "10"
        hex_code = integer_to_hex_string(0)    # Returns "0"
        ```
        
    Note:
        The returned string is in uppercase format and does not include the '0x' prefix.
        This format is used for error code lookup in the app_error_messages dictionary.
    """
    if not isinstance(error_code, int):
        raise ValueError("Input must be an integer.")

    # Convert the integer to a hex string and remove the '0x' prefix
    hex_string = hex(error_code)[2:].upper()

    return hex_string


def get_error_code_text(error_source: int, error_code: str) -> str:
    """
    Retrieve the error message text based on error source and code
    
    This function looks up a human-readable error message from the predefined
    error message dictionary using the error source and error code. If no
    specific message is found, it returns a fallback format.
    
    Args:
        error_source (int): The error source code (e.g., 100, 200, 300)
            - 100: System errors
            - 200: Communication errors
            - 300: Motion control errors
            - 400: Sensor errors
            - 500: Power/battery errors
            - 600: User/configuration errors
        error_code (str): The specific error code in hexadecimal string form (e.g., "01", "FF")
        
    Returns:
        str: The corresponding error message, or fallback format "source-code" if not found
        
    Example:
        ```python
        # Get error message for known error
        message = get_error_code_text(100, "01")  # Returns specific message
        
        # Get fallback for unknown error
        message = get_error_code_text(999, "ZZ")  # Returns "999-ZZ"
        ```
        
    Note:
        The error code should be in hexadecimal format (uppercase) without '0x' prefix.
        Use integer_to_hex_string() to convert integer codes to the correct format.
    """
    # Generate the key for looking up the error message
    key = f"app_error_code_{error_source}_{error_code}"
    
    # Check if the key exists in the error_code_dict
    if key in app_error_messages:
        return app_error_messages[key]
    else:
        # Fallback: return the combination of error_source and error_code
        return f"{error_source}-{error_code}"


def get_error_source_text(error_source: int) -> str:
    """
    Retrieve the error source description based on error source code
    
    This function looks up a human-readable description for the error source
    from the predefined error message dictionary. Error sources categorize
    the type of error that occurred.
    
    Args:
        error_source (int): The error source code (e.g., 100, 200, 300, 400, 500, 600)
            Each source represents a different category of errors:
            - 100: System-level errors
            - 200: Communication-related errors
            - 300: Motion control errors
            - 400: Sensor-related errors
            - 500: Power and battery errors
            - 600: User and configuration errors
        
    Returns:
        str: The corresponding error source description, or the source code as string if not found
        
    Example:
        ```python
        # Get error source description
        source_text = get_error_source_text(100)  # Returns "System Error"
        source_text = get_error_source_text(200)  # Returns "Communication Error"
        
        # Get fallback for unknown source
        source_text = get_error_source_text(999)  # Returns "999"
        ```
        
    Note:
        This function provides context about the general category of error,
        while get_error_code_text() provides specific error details.
    """
    # Generate the key for looking up the error source message
    key = f"app_error_source_{error_source}"
    
    # Check if the key exists in the error_code_dict
    if key in app_error_messages:
        return app_error_messages[key]
    else:
        # Fallback: return the error source as string
        return f"{error_source}"


def handle_error(message: Dict[str, Any]) -> None:
    """
    Process and display error messages from the Unitree Go2 robot
    
    This function processes error messages received from the robot and displays
    them in a user-friendly format with emojis, timestamps, and descriptive text.
    It handles multiple errors in a single message and formats each one clearly.
    
    Args:
        message (Dict[str, Any]): The error message dictionary containing:
            - data (List[List[Union[int, float]]]): List of error entries
                Each entry contains: [timestamp, error_source, error_code_int]
                - timestamp: Unix timestamp of the error
                - error_source: Error category code (100-600)
                - error_code_int: Specific error code as integer
    
    Example:
        ```python
        # Handle single error
        error_message = {
            "data": [
                [1640995200, 100, 255]  # timestamp, source, code
            ]
        }
        handle_error(error_message)
        
        # Handle multiple errors
        error_message = {
            "data": [
                [1640995200, 100, 255],
                [1640995201, 200, 16],
                [1640995202, 300, 5]
            ]
        }
        handle_error(error_message)
        ```
    
    Output Format:
        The function prints formatted error messages like:
        ```
        🚨 Error Received from Go2:
        🕒 Time:          2021-12-31 16:00:00
        🔢 Error Source:  System Error
        ❗ Error Code:    Motor Overheating
        ```
    
    Note:
        - Timestamps are converted from Unix time to human-readable format
        - Error codes are converted from integer to hexadecimal for lookup
        - Multiple errors are displayed sequentially
        - Unknown error codes fall back to "source-code" format
        - Output uses emojis for visual clarity
    """
    data = message["data"]

    for error in data:
        timestamp, error_source, error_code_int = error
        
        # Convert the timestamp to human-readable format
        readable_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))

        # Get human-readable error source description
        error_source_text = get_error_source_text(error_source)
        
        # Convert the error code to a hexadecimal string
        error_code_hex = integer_to_hex_string(error_code_int)
        
        # Get the human-readable error message
        error_code_text = get_error_code_text(error_source, error_code_hex)

        # Display formatted error message
        print(f"\n🚨 Error Received from Go2:\n"
              f"🕒 Time:          {readable_time}\n"
              f"🔢 Error Source:  {error_source_text}\n"
              f"❗ Error Code:    {error_code_text}\n")
