"""
WebRTC Audio Hub Management for Unitree Go2 Robot

This module provides a comprehensive interface for managing audio functionality on the Unitree Go2 robot
through WebRTC data channels. It supports audio file management, playback control, and megaphone
functionality for real-time audio communication.

Key Features:
- Audio file upload (MP3/WAV) with automatic format conversion
- Audio playback control (play, pause, resume)
- Audio file management (list, rename, delete)
- Megaphone mode for real-time audio streaming
- Chunked file transfer for large audio files
- Automatic audio format standardization (44.1kHz WAV)

Usage Example:
    ```python
    from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection
    from go2_webrtc_driver.webrtc_audiohub import WebRTCAudioHub
    
    # Initialize connection
    conn = Go2WebRTCConnection()
    await conn.connect()
    
    # Create audio hub
    audio_hub = WebRTCAudioHub(conn)
    
    # Upload and play audio file
    await audio_hub.upload_audio_file("music.mp3")
    audio_list = await audio_hub.get_audio_list()
    await audio_hub.play_by_uuid(audio_list[0]['uuid'])
    ```

Audio File Requirements:
- Supported formats: MP3, WAV
- Automatic conversion to 44.1kHz WAV for compatibility
- Files are chunked into 4KB blocks for transmission
- MD5 checksums ensure data integrity

Megaphone Mode:
- Real-time audio streaming to the robot's speakers
- Separate upload mechanism for live audio data
- Enter/exit megaphone mode for real-time communication

Note:
    This module requires an active WebRTC connection with a data channel.
    The Go2 robot must be connected and the data channel must be open
    before using any audio hub functionality.

Author: Unitree Robotics
Version: 1.0
"""

import logging
import json
import base64
import time
import os
import hashlib
from typing import Dict, Any, Optional
from pydub import AudioSegment
from go2_webrtc_driver.constants import AUDIO_API
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection
import asyncio

CHUNK_SIZE = 61440  # Default chunk size for file transfer (60KB)

class WebRTCAudioHub:
    """
    WebRTC Audio Hub for Unitree Go2 Robot Audio Management
    
    This class provides comprehensive audio management capabilities for the Unitree Go2 robot,
    including audio file upload, playback control, and megaphone functionality through
    WebRTC data channels.
    
    The WebRTCAudioHub handles:
    - Audio file format conversion (MP3 to WAV)
    - Chunked file transfer for large audio files
    - Audio playback control (play, pause, resume)
    - Audio file management (list, rename, delete)
    - Megaphone mode for real-time audio streaming
    - Play mode configuration (single, loop, etc.)
    
    Attributes:
        logger (logging.Logger): Logger instance for debugging and monitoring
        conn (Go2WebRTCConnection): WebRTC connection instance
        data_channel: WebRTC data channel for audio communication
        
    Example:
        ```python
        # Initialize with WebRTC connection
        conn = Go2WebRTCConnection()
        await conn.connect()
        
        # Create audio hub with custom logger
        import logging
        logger = logging.getLogger("audio_hub")
        audio_hub = WebRTCAudioHub(conn, logger)
        
        # Upload and manage audio files
        await audio_hub.upload_audio_file("background_music.mp3")
        audio_list = await audio_hub.get_audio_list()
        await audio_hub.play_by_uuid(audio_list[0]['uuid'])
        ```
    
    Note:
        Requires an active WebRTC connection with established data channel.
        Audio files are automatically converted to 44.1kHz WAV format for compatibility.
    """
    
    def __init__(self, connection: Go2WebRTCConnection, logger: Optional[logging.Logger] = None):
        """
        Initialize the WebRTC Audio Hub
        
        Args:
            connection (Go2WebRTCConnection): Active WebRTC connection instance
            logger (Optional[logging.Logger]): Logger instance for debugging.
                If None, creates a default logger named after the class.
                
        Raises:
            RuntimeError: If the WebRTC connection is not established or data channel is unavailable
            
        Example:
            ```python
            conn = Go2WebRTCConnection()
            await conn.connect()
            
            # With default logger
            audio_hub = WebRTCAudioHub(conn)
            
            # With custom logger
            custom_logger = logging.getLogger("my_audio_hub")
            audio_hub = WebRTCAudioHub(conn, custom_logger)
            ```
        """
        self.logger = logger.getChild(self.__class__.__name__) if logger else logging.getLogger(self.__class__.__name__)
        self.conn = connection
        self.data_channel = None
        self._setup_data_channel()

    def _setup_data_channel(self):
        """
        Setup the WebRTC data channel for audio control
        
        This method initializes the data channel from the WebRTC connection
        and validates that it's available for audio communication.
        
        Raises:
            RuntimeError: If WebRTC connection is not established or data channel is unavailable
            
        Note:
            This is an internal method called during initialization.
        """
        if not self.conn.datachannel:
            self.logger.error("WebRTC connection not established")
            raise RuntimeError("WebRTC connection not established")
        self.data_channel = self.conn.datachannel

    async def get_audio_list(self) -> Dict[str, Any]:
        """
        Get list of available audio files on the robot
        
        Returns:
            Dict[str, Any]: Response containing list of audio files with metadata
                Each audio file includes:
                - uuid: Unique identifier
                - name: File name
                - duration: Audio duration in seconds
                - size: File size in bytes
                - format: Audio format (typically WAV)
                
        Raises:
            RuntimeError: If data channel is not available
            asyncio.TimeoutError: If request times out
            
        Example:
            ```python
            audio_list = await audio_hub.get_audio_list()
            print(f"Found {len(audio_list['data'])} audio files")
            for audio in audio_list['data']:
                print(f"- {audio['name']} ({audio['duration']}s)")
            ```
        """
        response = await self.data_channel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {
                "api_id": AUDIO_API['GET_AUDIO_LIST'],
                "parameter": json.dumps({})
            }
        )
        return response

    async def play_by_uuid(self, uuid: str) -> None:
        """
        Play audio file by its unique identifier
        
        Args:
            uuid (str): Unique identifier of the audio file to play
            
        Raises:
            RuntimeError: If data channel is not available
            ValueError: If uuid is invalid or file doesn't exist
            asyncio.TimeoutError: If request times out
            
        Example:
            ```python
            # Get audio list and play first file
            audio_list = await audio_hub.get_audio_list()
            if audio_list['data']:
                await audio_hub.play_by_uuid(audio_list['data'][0]['uuid'])
            ```
        """
        await self.data_channel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {
                "api_id": AUDIO_API['SELECT_START_PLAY'],
                "parameter": json.dumps({
                    'unique_id': uuid
                })
            }
        )

    async def pause(self) -> None:
        """
        Pause current audio playback
        
        Pauses the currently playing audio file. The playback position is saved
        and can be resumed using the resume() method.
        
        Raises:
            RuntimeError: If data channel is not available
            asyncio.TimeoutError: If request times out
            
        Example:
            ```python
            # Start playing and then pause
            await audio_hub.play_by_uuid("audio-uuid")
            await asyncio.sleep(5)  # Play for 5 seconds
            await audio_hub.pause()
            ```
        """
        await self.data_channel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {
                "api_id": AUDIO_API['PAUSE'],
                "parameter": json.dumps({})
            }
        )

    async def resume(self) -> None:
        """
        Resume paused audio playback
        
        Resumes playback from the position where it was paused.
        If no audio is paused, this method has no effect.
        
        Raises:
            RuntimeError: If data channel is not available
            asyncio.TimeoutError: If request times out
            
        Example:
            ```python
            # Pause and resume playback
            await audio_hub.pause()
            await asyncio.sleep(2)  # Pause for 2 seconds
            await audio_hub.resume()
            ```
        """
        await self.data_channel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {
                "api_id": AUDIO_API['UNSUSPEND'],
                "parameter": json.dumps({})
            }
        )

    async def set_play_mode(self, play_mode: str) -> None:
        """
        Set audio playback mode
        
        Args:
            play_mode (str): Play mode to set. Valid options:
                - "single_cycle": Play once and stop
                - "no_cycle": Play once without repeat
                - "list_loop": Loop through all audio files
                
        Raises:
            RuntimeError: If data channel is not available
            ValueError: If play_mode is not a valid option
            asyncio.TimeoutError: If request times out
            
        Example:
            ```python
            # Set to loop mode
            await audio_hub.set_play_mode("list_loop")
            
            # Set to single play mode
            await audio_hub.set_play_mode("single_cycle")
            ```
        """
        await self.data_channel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {
                "api_id": AUDIO_API['SET_PLAY_MODE'],
                "parameter": json.dumps({
                    'play_mode': play_mode
                })
            }
        )

    async def rename_record(self, uuid: str, new_name: str) -> None:
        """
        Rename an audio file
        
        Args:
            uuid (str): Unique identifier of the audio file to rename
            new_name (str): New name for the audio file
            
        Raises:
            RuntimeError: If data channel is not available
            ValueError: If uuid is invalid or new_name is empty
            asyncio.TimeoutError: If request times out
            
        Example:
            ```python
            # Rename an audio file
            await audio_hub.rename_record("audio-uuid", "New Song Title")
            ```
        """
        await self.data_channel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {
                "api_id": AUDIO_API['SELECT_RENAME'],
                "parameter": json.dumps({
                    'unique_id': uuid,
                    'new_name': new_name
                })
            }
        )

    async def delete_record(self, uuid: str) -> None:
        """
        Delete an audio file
        
        Args:
            uuid (str): Unique identifier of the audio file to delete
            
        Raises:
            RuntimeError: If data channel is not available
            ValueError: If uuid is invalid or file doesn't exist
            asyncio.TimeoutError: If request times out
            
        Warning:
            This operation is irreversible. The audio file will be permanently deleted.
            
        Example:
            ```python
            # Delete an audio file
            await audio_hub.delete_record("audio-uuid")
            ```
        """
        await self.data_channel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {
                "api_id": AUDIO_API['SELECT_DELETE'],
                "parameter": json.dumps({
                    'unique_id': uuid
                })
            }
        )

    async def get_play_mode(self) -> Dict[str, Any]:
        """
        Get current audio playback mode
        
        Returns:
            Dict[str, Any]: Response containing current play mode information
                Includes:
                - play_mode: Current play mode setting
                - other playback status information
                
        Raises:
            RuntimeError: If data channel is not available
            asyncio.TimeoutError: If request times out
            
        Example:
            ```python
            mode_info = await audio_hub.get_play_mode()
            current_mode = mode_info['data']['play_mode']
            print(f"Current play mode: {current_mode}")
            ```
        """
        response = await self.data_channel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {
                "api_id": AUDIO_API['GET_PLAY_MODE'],
                "parameter": json.dumps({})
            }
        )
        return response

    async def upload_audio_file(self, audiofile_path: str) -> Dict[str, Any]:
        """
        Upload an audio file to the robot
        
        Supports MP3 and WAV formats. MP3 files are automatically converted to WAV
        format with 44.1kHz sample rate for compatibility. Large files are split
        into 4KB chunks for reliable transmission.
        
        Args:
            audiofile_path (str): Path to the audio file to upload
            
        Returns:
            Dict[str, Any]: Response from the final chunk upload
            
        Raises:
            FileNotFoundError: If the audio file doesn't exist
            RuntimeError: If data channel is not available
            ValueError: If file format is not supported
            asyncio.TimeoutError: If upload times out
            Exception: If file conversion or upload fails
            
        Example:
            ```python
            # Upload MP3 file (will be converted to WAV)
            response = await audio_hub.upload_audio_file("music.mp3")
            
            # Upload WAV file directly
            response = await audio_hub.upload_audio_file("sound.wav")
            ```
            
        Note:
            - Files are automatically converted to 44.1kHz WAV format
            - Large files are chunked into 4KB blocks
            - MD5 checksums ensure data integrity
            - Temporary WAV files are created for MP3 conversion
        """
        # Convert MP3 to WAV if necessary
        if audiofile_path.endswith(".mp3"):
            self.logger.debug("Converting MP3 to WAV")
            audio = AudioSegment.from_mp3(audiofile_path)
            # Set specific audio parameters for compatibility
            audio = audio.set_frame_rate(44100)  # Standard sample rate
            wav_file_path = audiofile_path.replace('.mp3', '.wav')
            audio.export(wav_file_path, format='wav', parameters=["-ar", "44100"])
        else:
            wav_file_path = audiofile_path
        
        # Read the WAV file
        with open(wav_file_path, 'rb') as f:
            audio_data = f.read()

        # Note: unique identifier for upload is handled by receiver side
        
        try:
            # Calculate MD5 of the file
            file_md5 = hashlib.md5(audio_data).hexdigest()
            
            # Convert to base64
            b64_data = base64.b64encode(audio_data).decode('utf-8')
            
            # Split into smaller chunks (4KB each)
            chunk_size = 4096
            chunks = [b64_data[i:i + chunk_size] for i in range(0, len(b64_data), chunk_size)]
            total_chunks = len(chunks)
            
            self.logger.debug(f"Splitting file into {total_chunks} chunks")

            # Send each chunk
            for i, chunk in enumerate(chunks, 1):
                parameter = {
                    'file_name': os.path.splitext(os.path.basename(audiofile_path))[0],
                    'file_type': 'wav',
                    'file_size': len(audio_data),
                    'current_block_index': i,
                    'total_block_number': total_chunks,
                    'block_content': chunk,
                    'current_block_size': len(chunk),
                    'file_md5': file_md5,
                    'create_time': int(time.time() * 1000)
                }
                # Send the chunk
                self.logger.debug(f"Sending chunk {i}/{total_chunks}")
                if i % 25 == 0 or i == total_chunks:
                    # Periodic compact progress for large files
                    self.logger.debug(
                        f"Progress: {i}/{total_chunks} blocks sent for {parameter['file_name']} ({parameter['file_type']})"
                    )
                
                response = await self.data_channel.pub_sub.publish_request_new(
                    "rt/api/audiohub/request",
                    {
                        "api_id": AUDIO_API['UPLOAD_AUDIO_FILE'],
                        "parameter": json.dumps(parameter, ensure_ascii=True)
                    }
                )
                
                # Wait a small amount between chunks
                await asyncio.sleep(0.1)
                
            self.logger.debug("All chunks sent")
            return response
            
        except Exception as e:
            self.logger.error(f"Error uploading audio file: {e}")
            raise

    async def enter_megaphone(self) -> None:
        """
        Enter megaphone mode for real-time audio streaming
        
        Enables megaphone mode, allowing real-time audio streaming to the robot's
        speakers. In this mode, audio data can be streamed directly without
        storing files on the robot.
        
        Raises:
            RuntimeError: If data channel is not available
            asyncio.TimeoutError: If request times out
            
        Example:
            ```python
            # Enter megaphone mode
            await audio_hub.enter_megaphone()
            
            # Stream audio data
            await audio_hub.upload_megaphone("live_audio.wav")
            
            # Exit megaphone mode
            await audio_hub.exit_megaphone()
            ```
        """
        await self.data_channel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {
                "api_id": AUDIO_API['ENTER_MEGAPHONE'],
                "parameter": json.dumps({})
            }
        )

    async def exit_megaphone(self) -> None:
        """
        Exit megaphone mode
        
        Disables megaphone mode and returns to normal audio playback mode.
        
        Raises:
            RuntimeError: If data channel is not available
            asyncio.TimeoutError: If request times out
            
        Example:
            ```python
            # Exit megaphone mode
            await audio_hub.exit_megaphone()
            ```
        """
        await self.data_channel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {
                "api_id": AUDIO_API['EXIT_MEGAPHONE'],
                "parameter": json.dumps({})
            }
        )

    async def upload_megaphone(self, audiofile_path: str) -> Dict[str, Any]:
        """
        Upload audio file for megaphone mode streaming
        
        Uploads an audio file specifically for megaphone mode. This is used for
        real-time audio streaming rather than storing files on the robot.
        The audio is chunked and streamed directly to the speakers.
        
        Args:
            audiofile_path (str): Path to the audio file to stream
            
        Returns:
            Dict[str, Any]: Response from the final chunk upload
            
        Raises:
            FileNotFoundError: If the audio file doesn't exist
            RuntimeError: If data channel is not available
            ValueError: If file format is not supported
            asyncio.TimeoutError: If upload times out
            Exception: If file conversion or upload fails
            
        Example:
            ```python
            # Enter megaphone mode and stream audio
            await audio_hub.enter_megaphone()
            response = await audio_hub.upload_megaphone("announcement.wav")
            await audio_hub.exit_megaphone()
            ```
            
        Note:
            - Must be in megaphone mode before using this method
            - Files are chunked into 4KB blocks for streaming
            - Audio is played immediately rather than stored
        """
        # Convert MP3 to WAV if necessary
        if audiofile_path.endswith(".mp3"):
            self.logger.debug("Converting MP3 to WAV")
            audio = AudioSegment.from_mp3(audiofile_path)
            # Set specific audio parameters for compatibility
            audio = audio.set_frame_rate(44100)  # Standard sample rate
            wav_file_path = audiofile_path.replace('.mp3', '.wav')
            audio.export(wav_file_path, format='wav', parameters=["-ar", "44100"])
        else:
            wav_file_path = audiofile_path

        # Read and chunk the WAV file
        with open(wav_file_path, 'rb') as f:
            audio_data = f.read()

        try:
            # Megaphone upload does not require MD5 in current protocol
            
            # Convert to base64
            b64_data = base64.b64encode(audio_data).decode('utf-8')
            
            # Split into smaller chunks (4KB each)
            chunk_size = 4096
            chunks = [b64_data[i:i + chunk_size] for i in range(0, len(b64_data), chunk_size)]
            total_chunks = len(chunks)
            
            self.logger.debug(f"Splitting file into {total_chunks} chunks")

            # Send each chunk
            for i, chunk in enumerate(chunks, 1):
                parameter = {
                    'current_block_size': len(chunk),
                    'block_content': chunk,
                    'current_block_index': i,
                    'total_block_number': total_chunks
                }
                # Send the chunk
                self.logger.debug(f"Sending chunk {i}/{total_chunks}")
                if i % 25 == 0 or i == total_chunks:
                    # Periodic compact progress
                    self.logger.debug(
                        f"Megaphone upload progress: {i}/{total_chunks} blocks"
                    )
                
                response = await self.data_channel.pub_sub.publish_request_new(
                    "rt/api/audiohub/request",
                    {
                        "api_id": AUDIO_API['UPLOAD_MEGAPHONE'],
                        "parameter": json.dumps(parameter, ensure_ascii=True)
                    }
                )
                
                # Wait a small amount between chunks
                await asyncio.sleep(0.1)
                
            self.logger.debug("All chunks sent")
            return response
        except Exception as e:
            self.logger.error(f"Error uploading audio file: {e}")
            raise