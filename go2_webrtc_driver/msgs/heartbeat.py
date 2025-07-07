"""
WebRTC Data Channel Heartbeat Management for Unitree Go2 Robot

Provides heartbeat functionality for maintaining active WebRTC connections
with the Unitree Go2 robot. Sends periodic heartbeat messages to detect
connection health and prevent timeouts.

Features:
- Sends heartbeat messages every 2 seconds
- Monitors connection health through response tracking
- Automatic connection keep-alive functionality
- Graceful start/stop of heartbeat operations

Usage:
    heartbeat = WebRTCDataChannelHeartBeat(data_channel, pub_sub)
    heartbeat.start_heartbeat()
    # ... 
    heartbeat.stop_heartbeat()
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable
from ..constants import DATA_CHANNEL_TYPE


class WebRTCDataChannelHeartBeat:
    """
    Manages periodic heartbeat messages for WebRTC data channels.
    
    Sends heartbeat messages every 2 seconds to maintain active connections
    and monitor connection health with the Unitree Go2 robot.
    
    Args:
        channel: WebRTC data channel for communication
        pub_sub: Publish-subscribe system for message handling
    """
    
    def __init__(self, channel, pub_sub) -> None:
        """Initialize the heartbeat manager."""
        self.channel = channel
        self.heartbeat_timer = None
        self.heartbeat_response = None
        self.response_count = 0
        self.last_response_time = None
        self.new_response_flag = False
        self.publish = pub_sub.publish_without_callback

    def _format_date(self, timestamp: float) -> str:
        """Format Unix timestamp to human-readable date string (YYYY-MM-DD HH:MM:SS)."""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

    def start_heartbeat(self) -> None:
        """Start sending periodic heartbeat messages every 2 seconds."""
        self.heartbeat_timer = asyncio.get_event_loop().call_later(2, self.send_heartbeat)

    def stop_heartbeat(self) -> None:
        """Stop the heartbeat transmission and cancel any pending timers."""
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
            self.heartbeat_timer = None

    def send_heartbeat(self) -> None:
        """Send a heartbeat message and schedule the next one."""
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
        Handle received heartbeat response messages.
        
        Args:
            message: Heartbeat response message from the robot
        """
        current_time = time.time()
        self.heartbeat_response = current_time
        self.last_response_time = current_time
        self.response_count += 1
        self.new_response_flag = True
        
        logging.debug(f"Heartbeat response #{self.response_count} received at {self._format_date(current_time)}")

    def get_response_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about heartbeat responses.
        
        Returns:
            Dictionary containing response statistics and timing info
        """
        current_time = time.time()
        info = {
            'total_responses': self.response_count,
            'last_response_time': self.last_response_time,
            'has_new_response': self.new_response_flag,
            'time_since_last_response': None,
            'response_age_seconds': None
        }
        
        if self.last_response_time:
            info['time_since_last_response'] = current_time - self.last_response_time
            info['response_age_seconds'] = current_time - self.last_response_time
            
        return info
    
    def check_and_reset_new_response_flag(self) -> bool:
        """
        Check if there's a new response since last check and reset the flag.
        
        Returns:
            True if there was a new response since last check, False otherwise
        """
        if self.new_response_flag:
            self.new_response_flag = False
            return True
        return False
    
