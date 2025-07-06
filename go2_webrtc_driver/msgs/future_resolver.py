"""
Future Resolver for Asynchronous Message Handling in Unitree Go2 Robot Communication

This module provides the FutureResolver class, which manages asynchronous message handling
for WebRTC communication with the Unitree Go2 robot. It implements a future-based pattern
for request-response communication, handles message chunking for large data transfers,
and manages pending callbacks for asynchronous operations.

The FutureResolver handles:
- Asynchronous request-response message patterns
- Message chunking and reassembly for large data transfers
- Future-based callback management
- Unique message identification and routing
- File transfer with chunked data support
- Automatic cleanup of completed operations

Key Features:
- Future-based asynchronous operation management
- Automatic message chunking and reassembly
- Support for both regular messages and file transfers
- Robust error handling for malformed chunks
- Memory-efficient handling of large data transfers
- Automatic cleanup of pending operations

Message Flow:
1. Client sends request and registers future with save_resolve()
2. Server responds with one or more message chunks
3. FutureResolver processes chunks and reassembles data
4. Complete message resolves the future and triggers callback
5. Pending operation is cleaned up automatically

Usage Example:
    ```python
    from go2_webrtc_driver.msgs.future_resolver import FutureResolver
    import asyncio
    
    # Initialize resolver
    resolver = FutureResolver()
    
    # Create future for async operation
    future = asyncio.create_future()
    
    # Register future for message resolution
    resolver.save_resolve("REQUEST", "rt/api/sport", future, "12345")
    
    # Process incoming response message
    response_message = {
        "type": "RESPONSE",
        "topic": "rt/api/sport",
        "data": {"header": {"identity": {"id": "12345"}}, "result": "success"}
    }
    resolver.run_resolve_for_topic(response_message)
    
    # Future is automatically resolved with the message
    result = await future
    ```

Chunking Support:
- Handles large messages split into multiple chunks
- Automatic reassembly of chunked data
- Support for both binary and text data
- Robust error handling for missing or malformed chunks
- Memory-efficient processing of large transfers

Author: Unitree Robotics
Version: 1.0
"""

import logging
from typing import Dict, List, Any, Optional, Union, Callable
import asyncio
from ..constants import DATA_CHANNEL_TYPE
from ..util import get_nested_field


class FutureResolver:
    """
    Future Resolver for Asynchronous Message Handling
    
    This class manages asynchronous message handling for WebRTC communication with
    the Unitree Go2 robot. It implements a future-based pattern for request-response
    communication and handles message chunking for large data transfers.
    
    The resolver maintains:
    - Pending response tracking for async operations
    - Callback management for future resolution
    - Chunk storage for reassembling large messages
    - Automatic cleanup of completed operations
    
    Key Responsibilities:
    - Register futures for pending async operations
    - Process incoming messages and resolve appropriate futures
    - Handle message chunking and reassembly
    - Manage file transfer operations
    - Clean up completed operations
    
    Attributes:
        pending_responses (Dict): Storage for pending response tracking (currently unused)
        pending_callbacks (Dict[str, List]): Mapping of message keys to pending futures
        chunk_data_storage (Dict[str, List]): Storage for assembling chunked messages
    
    Example:
        ```python
        # Initialize resolver
        resolver = FutureResolver()
        
        # Register a future for async operation
        future = asyncio.create_future()
        resolver.save_resolve("REQUEST", "rt/api/sport", future, "msg123")
        
        # Process response message
        resolver.run_resolve_for_topic(response_message)
        
        # Future is automatically resolved
        result = await future
        ```
    """
    
    def __init__(self) -> None:
        """
        Initialize the Future Resolver
        
        Sets up the internal data structures for managing pending operations,
        callbacks, and chunked data storage.
        
        Example:
            ```python
            resolver = FutureResolver()
            print("Future resolver initialized")
            ```
        """
        self.pending_responses = {}      # Storage for pending response tracking
        self.pending_callbacks = {}     # Mapping of message keys to pending futures
        self.chunk_data_storage = {}    # Storage for assembling chunked messages

    def save_resolve(self, message_type: str, topic: str, future: asyncio.Future, 
                    identifier: Optional[str]) -> None:
        """
        Register a future for message resolution
        
        This method associates a future with a specific message type, topic, and identifier
        so that when a matching response is received, the future can be resolved.
        Multiple futures can be registered for the same message key.
        
        Args:
            message_type (str): Type of message (e.g., "REQUEST", "MSG")
            topic (str): Message topic (e.g., "rt/api/sport")
            future (asyncio.Future): Future to resolve when response arrives
            identifier (Optional[str]): Unique message identifier
            
        Example:
            ```python
            # Register future for API request
            future = asyncio.create_future()
            resolver.save_resolve("REQUEST", "rt/api/sport", future, "12345")
            
            # Register multiple futures for same message
            future2 = asyncio.create_future()
            resolver.save_resolve("REQUEST", "rt/api/sport", future2, "12345")
            ```
            
        Note:
            Multiple futures can be registered for the same message key.
            All registered futures will be resolved when the response arrives.
        """
        key = self.generate_message_key(message_type, topic, identifier)
        if key in self.pending_callbacks:
            self.pending_callbacks[key].append(future)
        else:
            self.pending_callbacks[key] = [future]

    def run_resolve_for_topic(self, message: Dict[str, Any]) -> None:
        """
        Process incoming messages and resolve matching futures
        
        This method processes incoming messages, handles chunked data reassembly,
        and resolves any pending futures that match the message. It supports both
        regular messages and special file transfer messages.
        
        Args:
            message (Dict[str, Any]): Incoming message containing:
                - type: Message type
                - topic: Message topic  
                - data: Message payload
                - info: Additional message information (for special message types)
                
        Example:
            ```python
            # Process a simple response
            response = {
                "type": "RESPONSE",
                "topic": "rt/api/sport",
                "data": {"header": {"identity": {"id": "12345"}}, "result": "success"}
            }
            resolver.run_resolve_for_topic(response)
            
            # Process chunked message
            chunked_response = {
                "type": "RESPONSE", 
                "topic": "rt/api/data",
                "data": {
                    "header": {"identity": {"id": "67890"}},
                    "content_info": {
                        "enable_chunking": True,
                        "chunk_index": 1,
                        "total_chunk_num": 3
                    },
                    "data": b"chunk1_data"
                }
            }
            resolver.run_resolve_for_topic(chunked_response)
            ```
            
        Message Processing:
        1. Extracts message type and identifier
        2. Handles special file transfer messages
        3. Processes chunked messages if applicable
        4. Resolves matching futures with complete message
        5. Cleans up completed operations
        
        Note:
            - Messages without type are ignored
            - File transfer messages are handled separately
            - Chunked messages are reassembled before future resolution
            - All matching futures are resolved simultaneously
        """
        if not message.get("type"):
            return

        # Handle special file transfer messages
        if (message["type"] == DATA_CHANNEL_TYPE["RTC_INNER_REQ"] and 
            get_nested_field(message, "info", "req_type") == "request_static_file"):
            self.run_resolve_for_topic_for_file(message)
            return

        # Generate message key for lookup
        key = self.generate_message_key(
            message["type"],
            message.get("topic", ""),
            get_nested_field(message, "data", "uuid") or
            get_nested_field(message, "data", "header", "identity", "id") or
            get_nested_field(message, "info", "uuid") or
            get_nested_field(message, "info", "req_uuid")
        )

        # Handle chunked messages
        content_info = get_nested_field(message, "data", "content_info")
        if content_info and content_info.get("enable_chunking"):
            chunk_index = content_info.get("chunk_index")
            total_chunks = content_info.get("total_chunk_num")

            # Validate chunk information
            if total_chunks is None or total_chunks == 0:
                raise ValueError("Total number of chunks cannot be zero")
            if chunk_index is None:
                raise ValueError("Chunk index is missing")

            data_chunk = message["data"].get("data")
            
            # Store intermediate chunks
            if chunk_index < total_chunks:
                if key in self.chunk_data_storage:
                    self.chunk_data_storage[key].append(data_chunk)
                else:
                    self.chunk_data_storage[key] = [data_chunk]
                return
            else:
                # Final chunk - assemble complete message
                self.chunk_data_storage[key].append(data_chunk)
                message["data"]["data"] = self.merge_array_buffers(self.chunk_data_storage[key])
                del self.chunk_data_storage[key]

        # Resolve pending futures with the complete message
        if key in self.pending_callbacks:
            for future in self.pending_callbacks[key]:
                if future:
                    future.set_result(message)
            del self.pending_callbacks[key]

    def merge_array_buffers(self, buffers: List[Union[bytes, bytearray]]) -> bytes:
        """
        Merge multiple data buffers into a single byte array
        
        This method concatenates multiple data chunks into a single continuous
        byte array. It's used to reassemble chunked messages into their original form.
        
        Args:
            buffers (List[Union[bytes, bytearray]]): List of data buffers to merge
            
        Returns:
            bytes: Merged data as a single byte array
            
        Example:
            ```python
            # Merge multiple chunks
            chunks = [b"chunk1", b"chunk2", b"chunk3"]
            merged = resolver.merge_array_buffers(chunks)
            print(merged)  # b"chunk1chunk2chunk3"
            
            # Merge mixed types
            chunks = [bytearray(b"data1"), b"data2", bytearray(b"data3")]
            merged = resolver.merge_array_buffers(chunks)
            ```
            
        Note:
            The method handles both bytes and bytearray objects efficiently
            by calculating total length first to avoid repeated reallocations.
        """
        total_length = sum(len(buf) for buf in buffers)
        merged_buffer = bytearray(total_length)

        current_position = 0
        for buffer in buffers:
            merged_buffer[current_position:current_position + len(buffer)] = buffer
            current_position += len(buffer)

        return bytes(merged_buffer)

    def run_resolve_for_topic_for_file(self, message: Dict[str, Any]) -> None:
        """
        Process file transfer messages with chunking support
        
        This method handles special file transfer messages that use a different
        chunking format from regular messages. It assembles file chunks and
        resolves futures when complete files are received.
        
        Args:
            message (Dict[str, Any]): File transfer message containing:
                - type: Message type (typically RTC_INNER_REQ)
                - topic: Message topic
                - info: File transfer information including chunking details
                - data: Message payload
                
        Example:
            ```python
            # Process file transfer message
            file_message = {
                "type": "RTC_INNER_REQ",
                "topic": "rt/file",
                "info": {
                    "req_type": "request_static_file",
                    "uuid": "file123",
                    "file": {
                        "enable_chunking": True,
                        "chunk_index": 2,
                        "total_chunk_num": 3,
                        "data": "base64_encoded_chunk_data"
                    }
                }
            }
            resolver.run_resolve_for_topic_for_file(file_message)
            ```
            
        File Transfer Process:
        1. Extracts file information and chunk details
        2. Validates chunk index and total count
        3. Stores chunks until all are received
        4. Assembles complete file data
        5. Resolves futures with complete file message
        6. Cleans up chunk storage
        
        Note:
            - Handles both string and binary file data
            - String data is encoded to UTF-8 before storage
            - Final chunk triggers future resolution
            - Automatic cleanup of completed transfers
        """
        # Generate message key for lookup
        key = self.generate_message_key(
            message["type"], 
            message.get("topic", ""), 
            get_nested_field(message, "data", "uuid") or
            get_nested_field(message, "data", "header", "identity", "id") or
            get_nested_field(message, "info", "uuid") or
            get_nested_field(message, "info", "req_uuid")
        )

        # Process file chunking information
        file_info = get_nested_field(message, "info", "file")
        if file_info and file_info.get("enable_chunking"):
            chunk_index = file_info.get("chunk_index")
            total_chunks = file_info.get("total_chunk_num")

            # Validate chunk information
            if total_chunks is None or total_chunks == 0:
                raise ValueError("Total number of chunks cannot be zero")
            if chunk_index is None:
                raise ValueError("Chunk index is missing")

            # Extract and process chunk data
            data_chunk = file_info.get("data")

            # Initialize chunk storage for this key
            if key not in self.chunk_data_storage:
                self.chunk_data_storage[key] = []

            # Store chunk data (encode strings to bytes)
            chunk_bytes = data_chunk.encode('utf-8') if isinstance(data_chunk, str) else data_chunk
            self.chunk_data_storage[key].append(chunk_bytes)

            # Check if this is the final chunk
            if chunk_index == total_chunks:
                # Assemble complete file data
                message["info"]["file"]["data"] = b''.join(self.chunk_data_storage[key])
                del self.chunk_data_storage[key]

        # Resolve pending futures with the complete message
        if key in self.pending_callbacks:
            for future in self.pending_callbacks[key]:
                if future:
                    future.set_result(message)
            del self.pending_callbacks[key]

    def generate_message_key(self, message_type: str, topic: str, 
                           identifier: Optional[str]) -> str:
        """
        Generate a unique key for message identification
        
        This method creates a unique key for message tracking based on the message
        type, topic, and identifier. The key is used to associate futures with
        their corresponding response messages.
        
        Args:
            message_type (str): Type of message (e.g., "REQUEST", "RESPONSE")
            topic (str): Message topic (e.g., "rt/api/sport")
            identifier (Optional[str]): Unique message identifier (e.g., request ID)
            
        Returns:
            str: Unique message key for tracking
            
        Example:
            ```python
            # Generate key with identifier
            key = resolver.generate_message_key("REQUEST", "rt/api/sport", "12345")
            print(key)  # "12345"
            
            # Generate key without identifier (fallback)
            key = resolver.generate_message_key("MSG", "rt/lowstate", None)
            print(key)  # "MSG $ rt/lowstate"
            ```
            
        Key Generation:
        - If identifier is provided, it's used as the key
        - If no identifier, creates key from message_type and topic
        - Ensures unique tracking for each operation
        
        Note:
            The identifier takes precedence over the topic-based key.
            This allows for more specific message tracking when IDs are available.
        """
        return identifier or f"{message_type} $ {topic}"


