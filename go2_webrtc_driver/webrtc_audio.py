"""
WebRTC Audio Channel Management
==============================

This module provides audio channel management for the Go2 WebRTC connection.
It handles bidirectional audio communication (sendrecv) between the client and
the robot, including frame processing and callback management.

Key Features:
- Bidirectional audio streaming (send and receive)
- Multiple callback registration for audio frame processing
- Integration with WebRTC data channel for audio control
- Error handling and logging for audio operations

Audio Configuration:
- Direction: sendrecv (bidirectional)
- Format: PCM audio frames
- Sample Rate: Configured by WebRTC negotiation
- Channels: Typically mono or stereo

Usage:
    The audio channel is automatically created and managed by the main
    WebRTC connection. Users can register callbacks to process incoming
    audio frames or implement custom audio handling.

Example:
    >>> async def audio_callback(frame):
    ...     # Process audio frame
    ...     print(f"Received audio frame: {frame.samples}")
    >>> 
    >>> # Register callback with audio channel
    >>> connection.audio.add_track_callback(audio_callback)
"""

from aiortc import AudioStreamTrack, RTCRtpSender
import logging
import sounddevice as sd
import numpy as np
import wave
from typing import List, Callable, Any, Awaitable


class WebRTCAudioChannel:
    """
    Manages WebRTC audio channel for bidirectional audio communication.
    
    This class handles the audio transceiver setup, frame processing, and
    callback management for audio data received from the Go2 robot.
    
    Attributes:
        pc: RTCPeerConnection instance for WebRTC communication
        datachannel: WebRTC data channel for audio control commands
        track_callbacks: List of registered audio frame callbacks
    """
    
    def __init__(self, pc, datachannel) -> None:
        """
        Initialize the WebRTC audio channel.
        
        Sets up the audio transceiver for bidirectional communication and
        initializes the callback system for audio frame processing.
        
        Args:
            pc: RTCPeerConnection instance for WebRTC communication
            datachannel: WebRTC data channel for sending control commands
        """
        self.pc = pc
        self.datachannel = datachannel
        
        # Configure audio transceiver for bidirectional communication
        self.pc.addTransceiver("audio", direction="sendrecv")
        
        # Initialize callback system for audio frame processing
        self.track_callbacks: List[Callable[[Any], Awaitable[None]]] = []
        
        logging.info("WebRTC audio channel initialized with sendrecv direction")
        
    async def frame_handler(self, frame) -> None:
        """
        Process incoming audio frames from the robot.
        
        This method is called for each received audio frame. It logs the
        frame receipt and triggers all registered callbacks for custom
        audio processing.
        
        Args:
            frame: Audio frame object containing sample data and metadata
            
        Note:
            This method is typically called by the WebRTC connection's
            track handler. Users should register callbacks instead of
            calling this method directly.
        """
        logging.debug("Receiving audio frame")

        # Process frame through all registered callbacks
        for callback in self.track_callbacks:
            try:
                await callback(frame)
            except Exception as e:
                logging.error(f"Error in audio frame callback {callback.__name__}: {e}")
    
    def add_track_callback(self, callback: Callable[[Any], Awaitable[None]]) -> None:
        """
        Register a callback function to process incoming audio frames.
        
        Callbacks are called asynchronously for each received audio frame,
        allowing for custom audio processing, recording, or analysis.
        
        Args:
            callback: Async function that takes an audio frame as parameter
                     Must be callable and accept a single frame argument
        
        Example:
            >>> async def my_audio_processor(frame):
            ...     # Process audio frame
            ...     samples = frame.to_ndarray()
            ...     print(f"Received {len(samples)} audio samples")
            >>> 
            >>> audio_channel.add_track_callback(my_audio_processor)
        
        Note:
            Callbacks should be lightweight and non-blocking to avoid
            affecting audio stream performance. Heavy processing should
            be offloaded to separate threads or processes.
        """
        if callable(callback):
            self.track_callbacks.append(callback)
            logging.info(f"Audio callback registered: {callback.__name__}")
        else:
            logging.warning(f"Cannot register non-callable object as callback: {callback}")

    def switchAudioChannel(self, switch: bool) -> None:
        """
        Enable or disable the audio channel.
        
        This method sends a control command through the data channel to
        enable or disable audio streaming from the robot.
        
        Args:
            switch (bool): True to enable audio, False to disable
        
        Example:
            >>> # Enable audio streaming
            >>> audio_channel.switchAudioChannel(True)
            >>> 
            >>> # Disable audio streaming
            >>> audio_channel.switchAudioChannel(False)
        
        Note:
            This affects the robot's audio transmission to the client.
            The WebRTC connection remains active, but no audio data
            will be sent when disabled.
        """
        self.datachannel.switchAudioChannel(switch)
        logging.info(f"Audio channel {'enabled' if switch else 'disabled'}")
    
    def get_callback_count(self) -> int:
        """
        Get the number of registered audio callbacks.
        
        Returns:
            int: Number of currently registered audio frame callbacks
        
        Example:
            >>> count = audio_channel.get_callback_count()
            >>> print(f"Active audio callbacks: {count}")
        """
        return len(self.track_callbacks)
    
    def clear_callbacks(self) -> None:
        """
        Remove all registered audio callbacks.
        
        This method clears all audio frame callbacks, effectively
        stopping custom audio processing.
        
        Example:
            >>> audio_channel.clear_callbacks()
            >>> print("All audio callbacks cleared")
        """
        callback_count = len(self.track_callbacks)
        self.track_callbacks.clear()
        logging.info(f"Cleared {callback_count} audio callbacks")
    
        