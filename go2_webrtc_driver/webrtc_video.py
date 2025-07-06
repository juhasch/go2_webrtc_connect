"""
WebRTC Video Channel Management
==============================

This module provides video channel management for the Go2 WebRTC connection.
It handles unidirectional video streaming (recvonly) from the robot to the client,
including frame processing and callback management.

Key Features:
- Receive-only video streaming from robot cameras
- Multiple callback registration for video frame processing
- Integration with WebRTC data channel for video control
- Error handling and logging for video operations

Video Configuration:
- Direction: recvonly (robot to client)
- Format: Video frames (typically H.264)
- Resolution: Depends on robot camera configuration
- Frame Rate: Configured by WebRTC negotiation

Usage:
    The video channel is automatically created and managed by the main
    WebRTC connection. Users can register callbacks to process incoming
    video frames for display, recording, or analysis.

Example:
    >>> async def video_callback(track):
    ...     # Process video track
    ...     frame = await track.recv()
    ...     print(f"Received video frame: {frame.width}x{frame.height}")
    >>> 
    >>> # Register callback with video channel
    >>> connection.video.add_track_callback(video_callback)
"""

import logging
from typing import List, Callable, Any, Awaitable
from .webrtc_datachannel import WebRTCDataChannel
from aiortc import RTCPeerConnection


class WebRTCVideoChannel:
    """
    Manages WebRTC video channel for unidirectional video streaming.
    
    This class handles the video transceiver setup, track processing, and
    callback management for video data received from the Go2 robot cameras.
    
    Attributes:
        pc: RTCPeerConnection instance for WebRTC communication
        datachannel: WebRTC data channel for video control commands
        track_callbacks: List of registered video track callbacks
    """
    
    def __init__(self, pc: RTCPeerConnection, datachannel: WebRTCDataChannel) -> None:
        """
        Initialize the WebRTC video channel.
        
        Sets up the video transceiver for receive-only communication and
        initializes the callback system for video track processing.
        
        Args:
            pc (RTCPeerConnection): WebRTC peer connection instance
            datachannel (WebRTCDataChannel): Data channel for sending control commands
        """
        self.pc = pc
        self.datachannel = datachannel
        
        # Configure video transceiver for receive-only communication
        self.pc.addTransceiver("video", direction="recvonly")
        
        # Initialize callback system for video track processing
        self.track_callbacks: List[Callable[[Any], Awaitable[None]]] = []
        
        logging.info("WebRTC video channel initialized with recvonly direction")
    
    def switchVideoChannel(self, switch: bool) -> None:
        """
        Enable or disable the video channel.
        
        This method sends a control command through the data channel to
        enable or disable video streaming from the robot.
        
        Args:
            switch (bool): True to enable video, False to disable
        
        Example:
            >>> # Enable video streaming
            >>> video_channel.switchVideoChannel(True)
            >>> 
            >>> # Disable video streaming
            >>> video_channel.switchVideoChannel(False)
        
        Note:
            This affects the robot's video transmission to the client.
            The WebRTC connection remains active, but no video data
            will be sent when disabled.
        """
        self.datachannel.switchVideoChannel(switch)
        logging.info(f"Video channel {'enabled' if switch else 'disabled'}")
    
    def add_track_callback(self, callback: Callable[[Any], Awaitable[None]]) -> None:
        """
        Register a callback function to process incoming video tracks.
        
        Callbacks are called asynchronously when a video track is received,
        allowing for custom video processing, display, or recording.
        
        Args:
            callback: Async function that takes a video track as parameter
                     Must be callable and accept a single track argument
        
        Example:
            >>> async def my_video_processor(track):
            ...     # Process video track
            ...     frame = await track.recv()
            ...     print(f"Video frame: {frame.width}x{frame.height}")
            >>> 
            >>> video_channel.add_track_callback(my_video_processor)
        
        Note:
            Callbacks should handle video track processing efficiently
            to avoid blocking the video stream. Consider using async
            processing for heavy operations.
        """
        if callable(callback):
            self.track_callbacks.append(callback)
            logging.info(f"Video callback registered: {callback.__name__}")
        else:
            logging.warning(f"Cannot register non-callable object as callback: {callback}")
    
    async def track_handler(self, track) -> None:
        """
        Process incoming video tracks from the robot.
        
        This method is called when a video track is received from the robot.
        It logs the track receipt and triggers all registered callbacks for
        custom video processing.
        
        Args:
            track: Video track object containing video stream data
            
        Note:
            This method is typically called by the WebRTC connection's
            track handler. Users should register callbacks instead of
            calling this method directly.
        """
        logging.info("Receiving video track")
        
        # Process track through all registered callbacks
        for callback in self.track_callbacks:
            try:
                await callback(track)
            except Exception as e:
                logging.error(f"Error in video track callback {callback.__name__}: {e}")
    
    def get_callback_count(self) -> int:
        """
        Get the number of registered video callbacks.
        
        Returns:
            int: Number of currently registered video track callbacks
        
        Example:
            >>> count = video_channel.get_callback_count()
            >>> print(f"Active video callbacks: {count}")
        """
        return len(self.track_callbacks)
    
    def clear_callbacks(self) -> None:
        """
        Remove all registered video callbacks.
        
        This method clears all video track callbacks, effectively
        stopping custom video processing.
        
        Example:
            >>> video_channel.clear_callbacks()
            >>> print("All video callbacks cleared")
        """
        callback_count = len(self.track_callbacks)
        self.track_callbacks.clear()
        logging.info(f"Cleared {callback_count} video callbacks")
    
    def is_enabled(self) -> bool:
        """
        Check if video streaming is currently enabled.
        
        Returns:
            bool: True if video channel is enabled, False otherwise
        
        Note:
            This method checks the local state. The actual video streaming
            state is controlled by the robot and may differ from this value.
        """
        # This would require tracking the current state
        # For now, we'll return True as a placeholder
        return True  # TODO: Implement actual state tracking
    