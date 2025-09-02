"""
WebRTC Data Channel Management
=============================

This module provides comprehensive data channel management for the Go2 WebRTC connection.
It handles all non-media communication between the client and robot, including control
commands, sensor data, status updates, and LiDAR information.

Key Features:
- Publish/Subscribe messaging system for robot communication
- Automatic connection validation and heartbeat management
- Binary data processing for sensor information (LiDAR, etc.)
- Error handling and status reporting
- Configurable data decoders for different sensor types

Data Channel Protocol:
- JSON messages for control and status
- Binary messages for sensor data (LiDAR, images, etc.)
- Automatic message routing based on message type
- Future-based request/response pattern

Usage:
    The data channel is automatically created and managed by the main WebRTC
    connection. It provides methods for subscribing to robot topics, sending
    commands, and processing incoming sensor data.

Example:
    >>> # Subscribe to robot low-level state
    >>> await datachannel.pub_sub.subscribe("rt/lf/lowstate")
    >>> 
    >>> # Send sport mode command
    >>> await datachannel.pub_sub.publish("rt/api/sport/request", command_data)
"""

import asyncio
import json
import logging
import struct
import sys
from typing import Dict, Any, Optional, Callable, Union

from .msgs.pub_sub import WebRTCDataChannelPubSub
from .lidar.lidar_decoder_unified import UnifiedLidarDecoder
from .msgs.heartbeat import WebRTCDataChannelHeartBeat
from .msgs.validation import WebRTCDataChannelValidation
from .msgs.rtc_inner_req import WebRTCDataChannelRTCInnerReq
from .util import print_status
from .msgs.error_handler import handle_error
from .constants import DATA_CHANNEL_TYPE


class WebRTCDataChannel:
    """
    Manages WebRTC data channel for robot communication and control.
    
    This class handles all non-media communication with the Go2 robot, including
    control commands, sensor data processing, and status management. It provides
    a publish/subscribe system for robot topics and handles binary data decoding.
    
    Attributes:
        channel: WebRTC data channel instance
        data_channel_opened: Boolean indicating if the channel is ready for use
        conn: Parent WebRTC connection instance
        pub_sub: Publish/subscribe message handler
        heartbeat: Heartbeat manager for connection monitoring
        validation: Connection validation handler
        rtc_inner_req: Internal RTC request handler
        decoder: Data decoder for binary messages (LiDAR, etc.)
    """
    
    def __init__(self, conn, pc) -> None:
        """
        Initialize the WebRTC data channel.
        
        Sets up the data channel with all necessary message handlers, validation,
        heartbeat monitoring, and data processing capabilities.
        
        Args:
            conn: Parent WebRTC connection instance
            pc: RTCPeerConnection instance for WebRTC communication
        """
        # Create and configure the data channel
        self.channel = pc.createDataChannel("data")
        self.data_channel_opened = False
        self.conn = conn

        # Initialize core messaging components
        self.pub_sub = WebRTCDataChannelPubSub(self.channel)
        self.heartbeat = WebRTCDataChannelHeartBeat(self.channel, self.pub_sub)
        self.validation = WebRTCDataChannelValidation(self.channel, self.pub_sub)
        self.rtc_inner_req = WebRTCDataChannelRTCInnerReq(self.conn, self.channel, self.pub_sub)

        # Set up default decoder for binary data
        self.set_decoder(decoder_type='libvoxel')

        # Configure validation success callback
        def on_validate() -> None:
            """Handle successful channel validation."""
            self.data_channel_opened = True
            self.heartbeat.start_heartbeat()
            self.rtc_inner_req.network_status.start_network_status_fetch()
            print_status("Data Channel Verification", "✅ OK")

        self.validation.set_on_validate_callback(on_validate)

        # Configure network status callback
        def on_network_status(mode: str) -> None:
            """Handle network status updates."""
            logging.debug(f"Go2 connection mode: {mode}")

        self.rtc_inner_req.network_status.set_on_network_status_callback(on_network_status)

        # Set up data channel event handlers
        self._setup_event_handlers()
        
        logging.debug("WebRTC data channel initialized successfully")

    def _setup_event_handlers(self) -> None:
        """Configure event handlers for the data channel."""
        
        @self.channel.on("open")
        def on_open() -> None:
            """Handle data channel opening."""
            logging.debug("Data channel opened")

        @self.channel.on("close")
        def on_close() -> None:
            """Handle data channel closing."""
            logging.debug("Data channel closed")
            self.data_channel_opened = False
            self.heartbeat.stop_heartbeat()
            self.rtc_inner_req.network_status.stop_network_status_fetch()
            
        @self.channel.on("message")
        async def on_message(message: Union[str, bytes]) -> None:
            """
            Handle incoming data channel messages.
            
            Args:
                message: Raw message data (string or bytes)
            """
            logging.debug("Received message on data channel")
            try:
                # Validate message content
                if not message:
                    return

                # Parse message based on type
                if isinstance(message, str):
                    parsed_data = json.loads(message)
                elif isinstance(message, bytes):
                    parsed_data = self.deal_array_buffer(message)
                else:
                    logging.warning(f"Received unknown message type: {type(message)}")
                    return
                
                # Process message through pub/sub system
                self.pub_sub.run_resolve(parsed_data)

                # Handle message routing
                await self.handle_response(parsed_data)
        
            except json.JSONDecodeError as e:
                logging.error(f"Failed to decode JSON message: {e}")
            except Exception as e:
                logging.error(f"Error processing WebRTC data: {e}")

    async def handle_response(self, msg: Dict[str, Any]) -> None:
        """
        Route incoming messages to appropriate handlers.
        
        This method examines the message type and forwards it to the
        appropriate handler for processing.
        
        Args:
            msg: Parsed message dictionary containing type and data
        """
        msg_type = msg.get("type")
        
        if not msg_type:
            logging.warning("Received message without type field")
            return

        # Route message to appropriate handler
        if msg_type == DATA_CHANNEL_TYPE["VALIDATION"]:
            await self.validation.handle_response(msg)
        elif msg_type == DATA_CHANNEL_TYPE["RTC_INNER_REQ"]:
            self.rtc_inner_req.handle_response(msg)
        elif msg_type == DATA_CHANNEL_TYPE["HEARTBEAT"]:
            self.heartbeat.handle_response(msg)
        elif msg_type in {DATA_CHANNEL_TYPE["ERRORS"], DATA_CHANNEL_TYPE["ADD_ERROR"], DATA_CHANNEL_TYPE["RM_ERROR"]}:
            handle_error(msg)
        elif msg_type == DATA_CHANNEL_TYPE["ERR"]:
            await self.validation.handle_err_response(msg)
        else:
            logging.debug(f"Unhandled message type: {msg_type}")

    async def wait_datachannel_open(self, timeout: int = 5) -> None:
        """
        Wait for the data channel to open with a timeout.
        
        This method blocks until the data channel is ready for use or
        the timeout is reached.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Raises:
            asyncio.TimeoutError: If the channel doesn't open within the timeout
            SystemExit: If the timeout is reached (for backward compatibility)
        """
        try:
            await asyncio.wait_for(self._wait_for_open(), timeout)
            logging.debug("Data channel opened successfully")
        except asyncio.TimeoutError:
            logging.error(f"Data channel did not open within {timeout} seconds")
            print("Data channel did not open in time")
            sys.exit(1)

    async def _wait_for_open(self) -> None:
        """
        Internal method to wait for the data channel to be ready.
        
        This method polls the channel state until it becomes available.
        """
        while not self.data_channel_opened:
            await asyncio.sleep(0.1)

    def deal_array_buffer(self, buffer: bytes) -> Dict[str, Any]:
        """
        Process binary array buffer messages.
        
        This method handles binary data messages, which can contain either
        normal sensor data or specialized LiDAR data based on the header.
        
        Args:
            buffer: Raw binary message data
            
        Returns:
            Dict containing parsed JSON data with decoded binary content
        """
        if len(buffer) < 4:
            logging.warning("Received buffer too small for header")
            return {}
            
        # Read message header to determine processing type
        header_1, header_2 = struct.unpack_from('<HH', buffer, 0)
        
        if header_1 == 2 and header_2 == 0:
            # LiDAR data format
            return self.deal_array_buffer_for_lidar(buffer[4:])
        else:
            # Normal sensor data format
            return self.deal_array_buffer_for_normal(buffer)

    def deal_array_buffer_for_normal(self, buffer: bytes) -> Dict[str, Any]:
        """
        Process normal binary sensor data.
        
        Args:
            buffer: Binary buffer containing JSON header and sensor data
            
        Returns:
            Dict containing parsed message with decoded sensor data
        """
        if len(buffer) < 4:
            logging.warning("Normal buffer too small")
            return {}
            
        # Extract header length and data
        header_length, = struct.unpack_from('<H', buffer, 0)
        
        if len(buffer) < 4 + header_length:
            logging.warning("Buffer smaller than expected header length")
            return {}
            
        json_data = buffer[4:4 + header_length]
        binary_data = buffer[4 + header_length:]

        try:
            decoded_json = json.loads(json_data.decode('utf-8'))
            decoded_data = self.decoder.decode(binary_data, decoded_json['data'])
            decoded_json['data']['data'] = decoded_data
            return decoded_json
        except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
            logging.error(f"Error processing normal buffer: {e}")
            return {}

    def deal_array_buffer_for_lidar(self, buffer: bytes) -> Dict[str, Any]:
        """
        Process LiDAR binary data messages.
        
        Args:
            buffer: Binary buffer containing JSON header and LiDAR data
            
        Returns:
            Dict containing parsed message with decoded LiDAR data
        """
        if len(buffer) < 8:
            logging.warning("LiDAR buffer too small")
            return {}
            
        # Extract header length and data (LiDAR uses 32-bit header length)
        header_length, = struct.unpack_from('<I', buffer, 0)
        
        if len(buffer) < 8 + header_length:
            logging.warning("LiDAR buffer smaller than expected header length")
            return {}
            
        json_data = buffer[8:8 + header_length]
        binary_data = buffer[8 + header_length:]

        try:
            decoded_json = json.loads(json_data.decode('utf-8'))
            decoded_data = self.decoder.decode(binary_data, decoded_json['data'])
            decoded_json['data']['data'] = decoded_data
            return decoded_json
        except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
            logging.error(f"Error processing LiDAR buffer: {e}")
            return {}

    async def disableTrafficSaving(self, switch: bool) -> bool:
        """
        Enable or disable traffic saving mode.
        
        Traffic saving mode reduces bandwidth usage by limiting data transmission.
        This should typically be disabled when subscribing to high-bandwidth
        topics like LiDAR data.
        
        Args:
            switch: True to disable traffic saving, False to enable it
            
        Returns:
            bool: True if the command was successful, False otherwise
        """
        data = {
            "req_type": "disable_traffic_saving",
            "instruction": "on" if switch else "off"
        }
        
        try:
            response = await self.pub_sub.publish(
                "",
                data,
                DATA_CHANNEL_TYPE["RTC_INNER_REQ"],
            )
            
            if response.get('info', {}).get('execution') == "ok":
                logging.debug(f"Traffic saving: {'disabled' if switch else 'enabled'}")
                return True
            else:
                logging.error(f"Failed to change traffic saving mode: {response}")
                return False
        except Exception as e:
            logging.error(f"Error changing traffic saving mode: {e}")
            return False

    def switchVideoChannel(self, switch: bool) -> None:
        """
        Enable or disable the video channel.
        
        Args:
            switch: True to enable video, False to disable
        """
        self.pub_sub.publish_without_callback(
            "",
            "on" if switch else "off",
            DATA_CHANNEL_TYPE["VID"],
        )
        logging.debug(f"Video channel: {'on' if switch else 'off'}")

    def switchAudioChannel(self, switch: bool) -> None:
        """
        Enable or disable the audio channel.
        
        Args:
            switch: True to enable audio, False to disable
        """
        self.pub_sub.publish_without_callback(
            "",
            "on" if switch else "off",
            DATA_CHANNEL_TYPE["AUD"],
        )
        logging.debug(f"Audio channel: {'on' if switch else 'off'}")
    
    def set_decoder(self, decoder_type: str) -> None:
        """
        Set the decoder type for processing binary data.
        
        The decoder is responsible for converting binary sensor data into
        usable formats. Different decoders are optimized for different
        types of sensor data.
        
        Args:
            decoder_type: Type of decoder to use ("libvoxel" or "native")
            
        Raises:
            ValueError: If decoder_type is not supported
            
        Example:
            >>> datachannel.set_decoder("libvoxel")  # Use WebAssembly decoder
            >>> datachannel.set_decoder("native")    # Use native Python decoder
        """
        if decoder_type not in ["libvoxel", "native"]:
            raise ValueError("Invalid decoder type. Choose 'libvoxel' or 'native'.")

        # Create decoder instance
        self.decoder = UnifiedLidarDecoder(decoder_type=decoder_type)
        logging.debug(f"Data decoder changed to: {decoder_type}")
    
    def is_open(self) -> bool:
        """
        Check if the data channel is open and ready for use.
        
        Returns:
            bool: True if the channel is open, False otherwise
        """
        return self.data_channel_opened
    
    def get_decoder_type(self) -> str:
        """
        Get the current decoder type.
        
        Returns:
            str: Name of the current decoder
        """
        return self.decoder.get_decoder_name() if hasattr(self.decoder, 'get_decoder_name') else "unknown"
    
    
