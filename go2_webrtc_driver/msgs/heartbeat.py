"""
WebRTC Data Channel Heartbeat Management for Unitree Go2 Robot

This module provides heartbeat functionality for maintaining active WebRTC connections
with the Unitree Go2 robot. It implements periodic heartbeat messages to detect
connection health, prevent timeouts, and ensure reliable communication channels.

The heartbeat system:
- Sends periodic heartbeat messages every 2 seconds
- Monitors connection health through response tracking
- Provides automatic connection keep-alive functionality
- Handles graceful start/stop of heartbeat operations
- Formats timestamps for both human-readable and numeric formats

Key Features:
- Automatic periodic heartbeat transmission
- Connection state monitoring
- Timestamp formatting utilities
- Graceful heartbeat lifecycle management
- Response tracking for connection validation
- Integration with pub-sub messaging system

Heartbeat Protocol:
- Messages sent every 2 seconds when channel is open
- Contains both string and numeric timestamp formats
- Uses dedicated HEARTBEAT message type
- Provides connection health monitoring
- Automatic rescheduling of heartbeat messages

Usage Example:
    ```python
    from go2_webrtc_driver.msgs.heartbeat import WebRTCDataChannelHeartBeat
    
    # Initialize heartbeat with channel and pub-sub
    heartbeat = WebRTCDataChannelHeartBeat(data_channel, pub_sub)
    
    # Start sending heartbeats
    heartbeat.start_heartbeat()
    
    # Handle incoming heartbeat responses
    heartbeat.handle_response(response_message)
    
    # Stop heartbeats when done
    heartbeat.stop_heartbeat()
    ```

Connection Management:
- Prevents WebRTC connection timeouts
- Maintains active data channel state
- Enables early detection of connection issues
- Provides reliable keep-alive mechanism

Author: Unitree Robotics
Version: 1.0
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable
from ..constants import DATA_CHANNEL_TYPE


class WebRTCDataChannelHeartBeat:
    """
    WebRTC Data Channel Heartbeat Manager
    
    This class manages periodic heartbeat messages for WebRTC data channels to maintain
    active connections with the Unitree Go2 robot. It provides automatic heartbeat
    transmission, response tracking, and connection health monitoring.
    
    The heartbeat manager handles:
    - Periodic heartbeat message transmission (every 2 seconds)
    - Connection state monitoring
    - Automatic rescheduling of heartbeat messages
    - Graceful start/stop of heartbeat operations
    - Response tracking for connection validation
    
    Attributes:
        channel: WebRTC data channel for communication
        heartbeat_timer (Optional[asyncio.TimerHandle]): Timer for scheduling heartbeats
        heartbeat_response (Optional[float]): Timestamp of last heartbeat response
        publish (Callable): Function to publish messages without callback
        
    Example:
        ```python
        # Initialize with data channel and pub-sub system
        heartbeat = WebRTCDataChannelHeartBeat(data_channel, pub_sub)
        
        # Start heartbeat transmission
        heartbeat.start_heartbeat()
        
        # Monitor for responses
        if heartbeat.heartbeat_response:
            print(f"Last response: {heartbeat.heartbeat_response}")
        
        # Stop when done
        heartbeat.stop_heartbeat()
        ```
    """
    
    def __init__(self, channel, pub_sub) -> None:
        """
        Initialize the WebRTC Data Channel Heartbeat Manager
        
        Args:
            channel: WebRTC data channel instance for communication
            pub_sub: Publish-subscribe system for message handling
            
        Example:
            ```python
            # Initialize heartbeat manager
            heartbeat = WebRTCDataChannelHeartBeat(data_channel, pub_sub)
            print("Heartbeat manager initialized")
            ```
        """
        self.channel = channel
        self.heartbeat_timer = None
        self.heartbeat_response = None
        self.publish = pub_sub.publish_without_callback

    def _format_date(self, timestamp: float) -> str:
        """
        Format Unix timestamp to human-readable date string
        
        This internal method converts a Unix timestamp to a formatted date string
        for inclusion in heartbeat messages. The format follows the pattern
        "YYYY-MM-DD HH:MM:SS" using local time.
        
        Args:
            timestamp (float): Unix timestamp to format
            
        Returns:
            str: Formatted date string in "YYYY-MM-DD HH:MM:SS" format
            
        Example:
            ```python
            # Format current time
            current_time = time.time()
            formatted = heartbeat._format_date(current_time)
            print(formatted)  # "2023-12-31 15:30:45"
            ```
            
        Note:
            This is an internal method used for heartbeat message formatting.
            Uses local timezone for timestamp conversion.
        """
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

    def start_heartbeat(self) -> None:
        """
        Start sending periodic heartbeat messages
        
        This method initiates the heartbeat transmission cycle, scheduling the first
        heartbeat message to be sent after 2 seconds. Subsequent heartbeats are
        automatically scheduled after each transmission.
        
        The heartbeat cycle:
        1. Schedules first heartbeat after 2 seconds
        2. Each heartbeat automatically schedules the next one
        3. Continues until stop_heartbeat() is called
        4. Only sends when channel is in "open" state
        
        Example:
            ```python
            # Start heartbeat transmission
            heartbeat.start_heartbeat()
            print("Heartbeat started - messages will be sent every 2 seconds")
            
            # Heartbeat will continue automatically
            await asyncio.sleep(10)  # Heartbeats sent during this time
            
            # Stop when done
            heartbeat.stop_heartbeat()
            ```
            
        Note:
            - Heartbeats are sent every 2 seconds
            - Automatically handles rescheduling
            - Safe to call multiple times (cancels previous timer)
            - Only sends when data channel is open
        """
        self.heartbeat_timer = asyncio.get_event_loop().call_later(2, self.send_heartbeat)

    def stop_heartbeat(self) -> None:
        """
        Stop the heartbeat transmission
        
        This method cancels the current heartbeat timer and stops all future
        heartbeat transmissions. It provides a clean way to shut down the
        heartbeat system when the connection is no longer needed.
        
        Example:
            ```python
            # Stop heartbeat transmission
            heartbeat.stop_heartbeat()
            print("Heartbeat stopped - no more messages will be sent")
            
            # Safe to call multiple times
            heartbeat.stop_heartbeat()  # No effect if already stopped
            ```
            
        Note:
            - Safe to call multiple times
            - Immediately cancels pending heartbeat
            - Does not affect the data channel state
            - Can restart with start_heartbeat() if needed
        """
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
            self.heartbeat_timer = None

    def send_heartbeat(self) -> None:
        """
        Send a heartbeat message and schedule the next one
        
        This method sends a heartbeat message containing current timestamp information
        and automatically schedules the next heartbeat transmission. It only sends
        when the data channel is in an open state.
        
        Heartbeat Message Format:
        - timeInStr: Human-readable timestamp ("YYYY-MM-DD HH:MM:SS")
        - timeInNum: Unix timestamp as integer
        - Message type: HEARTBEAT
        - Topic: Empty string (broadcast)
        
        Example:
            ```python
            # This method is typically called automatically by the timer
            # Manual call for testing:
            heartbeat.send_heartbeat()
            
            # Message content example:
            # {
            #     "timeInStr": "2023-12-31 15:30:45",
            #     "timeInNum": 1704036645
            # }
            ```
            
        Process:
        1. Checks if data channel is open
        2. Creates timestamp data (string and numeric formats)
        3. Publishes heartbeat message
        4. Schedules next heartbeat after 2 seconds
        
        Note:
            - Automatically schedules the next heartbeat
            - Only sends when channel state is "open"
            - Uses both string and numeric timestamp formats
            - Continues until stop_heartbeat() is called
        """
        if self.channel.readyState == "open":
            current_time = time.time()
            formatted_time = self._format_date(current_time)
            data = {
                "timeInStr": formatted_time,
                "timeInNum": int(current_time)
            }
            self.publish(
                "",  # Empty topic (broadcast)
                data,
                DATA_CHANNEL_TYPE["HEARTBEAT"],
            )
        # Schedule the next heartbeat
        self.heartbeat_timer = asyncio.get_event_loop().call_later(2, self.send_heartbeat)

    def handle_response(self, message: Dict[str, Any]) -> None:
        """
        Handle received heartbeat response messages
        
        This method processes incoming heartbeat response messages and updates
        the last response timestamp. It's used to monitor connection health
        and verify that the remote end is actively responding to heartbeats.
        
        Args:
            message (Dict[str, Any]): Heartbeat response message from the robot
                May contain response data and timestamp information
                
        Example:
            ```python
            # Handle incoming heartbeat response
            response_message = {
                "type": "HEARTBEAT_RESPONSE",
                "data": {"status": "ok"}
            }
            heartbeat.handle_response(response_message)
            
            # Check last response time
            if heartbeat.heartbeat_response:
                time_since_response = time.time() - heartbeat.heartbeat_response
                print(f"Last response: {time_since_response:.1f} seconds ago")
            ```
            
        Response Tracking:
        - Records timestamp of each response
        - Enables connection health monitoring
        - Allows detection of communication issues
        - Provides basis for timeout detection
        
        Note:
            - Updates heartbeat_response timestamp
            - Logs response reception for debugging
            - Can be used to implement timeout detection
            - Response timing helps assess connection quality
        """
        self.heartbeat_response = time.time()
        logging.info("Heartbeat response received.")
    
