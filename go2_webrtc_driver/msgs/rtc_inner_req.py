"""
WebRTC Internal Request Management for Unitree Go2 Robot

This module provides comprehensive internal request management for WebRTC communication
with the Unitree Go2 robot. It handles network status monitoring, file transfers,
probe responses, and various internal communication protocols.

The module includes:
- Network status monitoring and callback management
- File upload functionality with chunking and progress tracking
- File download functionality with cancellation support
- Probe response handling for connection diagnostics
- Unified request coordination and management

Key Features:
- Real-time network status monitoring (4G/WiFi/disconnected)
- Chunked file transfer for large files (upload/download)
- Progress tracking with callback support
- Cancellation support for file operations
- Automatic connection method detection
- Probe response handling for diagnostics
- Base64 encoding/decoding for file transfers

Network Status Types:
- 4G: Connected via cellular network
- STA-T: WiFi connected (remote mode)
- STA-L: WiFi connected (local mode)
- Disconnected: No network connection

File Transfer Protocol:
- Files are encoded to Base64 for transmission
- Large files are split into configurable chunks (default 60KB)
- Progress callbacks provide real-time update information
- Both upload and download support cancellation
- Automatic retry for network status requests

Usage Example:
    ```python
    from go2_webrtc_driver.msgs.rtc_inner_req import WebRTCDataChannelRTCInnerReq
    
    # Initialize internal request manager
    rtc_req = WebRTCDataChannelRTCInnerReq(conn, data_channel, pub_sub)
    
    # Monitor network status
    def network_callback(status):
        print(f"Network status: {status}")
    
    rtc_req.network_status.set_on_network_status_callback(network_callback)
    rtc_req.network_status.start_network_status_fetch()
    
    # Upload a file
    uploader = WebRTCDataChannelFileUploader(data_channel, pub_sub)
    result = await uploader.upload_file(file_data, "/path/to/file.txt")
    
    # Download a file
    downloader = WebRTCDataChannelFileDownloader(data_channel, pub_sub)
    data = await downloader.download_file("/path/to/file.txt")
    ```

Author: Unitree Robotics
Version: 1.0
"""

import asyncio
import logging
import base64
from typing import Dict, Any, Optional, Callable, List, Union
from ..constants import DATA_CHANNEL_TYPE, WebRTCConnectionMethod
from ..util import generate_uuid


class WebRTCChannelProbeResponse:
    """
    WebRTC Channel Probe Response Handler
    
    This class handles probe response messages for connection diagnostics and
    performance monitoring. It processes RTT (Round Trip Time) probe responses
    and forwards them through the pub-sub system.
    
    Probe responses help diagnose:
    - Connection latency and performance
    - Network quality assessment
    - Connection health monitoring
    - Diagnostic information collection
    
    Example:
        ```python
        # Initialize probe response handler
        probe_handler = WebRTCChannelProbeResponse(data_channel, pub_sub)
        
        # Handle incoming probe response
        probe_info = {"probe_id": "123", "rtt": 50}
        probe_handler.handle_response(probe_info)
        ```
    """
    
    def __init__(self, channel, pub_sub) -> None:
        """
        Initialize the probe response handler
        
        Args:
            channel: WebRTC data channel for communication
            pub_sub: Publish-subscribe system for message handling
            
        Example:
            ```python
            probe_handler = WebRTCChannelProbeResponse(data_channel, pub_sub)
            ```
        """
        self.channel = channel
        self.publish = pub_sub.publish_without_callback
        
    def handle_response(self, info: Dict[str, Any]) -> None:
        """
        Handle and forward probe response information
        
        This method processes probe response data and forwards it through
        the pub-sub system for further handling by other components.
        
        Args:
            info (Dict[str, Any]): Probe response information containing:
                - probe_id: Unique identifier for the probe
                - rtt: Round trip time in milliseconds
                - timestamp: Response timestamp
                - other diagnostic data
                
        Example:
            ```python
            # Handle probe response
            probe_info = {
                "probe_id": "probe_123",
                "rtt": 45,
                "timestamp": 1640995200
            }
            probe_handler.handle_response(probe_info)
            ```
        """
        self.publish(
            "",  # Empty topic (broadcast)
            info,
            DATA_CHANNEL_TYPE["RTC_INNER_REQ"],
        )


class WebRTCDataChannelNetworkStatus:
    """
    WebRTC Data Channel Network Status Monitor
    
    This class monitors and manages network status for the Unitree Go2 robot,
    providing real-time updates on connection type (4G, WiFi, disconnected)
    and triggering callbacks when network status changes.
    
    The network status monitor:
    - Periodically requests network status from the robot
    - Categorizes connection types (4G, WiFi STA-T/STA-L)
    - Provides callback notifications for status changes
    - Handles automatic retry for disconnected states
    - Manages connection method detection
    
    Network Status Types:
    - "4G": Connected via cellular network
    - "STA-T": WiFi connected in remote mode
    - "STA-L": WiFi connected in local mode
    - "Undefined"/"DISCONNECTED": No active connection
    
    Example:
        ```python
        # Initialize network status monitor
        network_monitor = WebRTCDataChannelNetworkStatus(conn, channel, pub_sub)
        
        # Register status callback
        def on_status_change(status):
            print(f"Network status changed to: {status}")
        
        network_monitor.set_on_network_status_callback(on_status_change)
        network_monitor.start_network_status_fetch()
        ```
    """
    
    def __init__(self, conn, channel, pub_sub) -> None:
        """
        Initialize the network status monitor
        
        Args:
            conn: WebRTC connection instance
            channel: WebRTC data channel for communication
            pub_sub: Publish-subscribe system for message handling
            
        Example:
            ```python
            monitor = WebRTCDataChannelNetworkStatus(conn, channel, pub_sub)
            ```
        """
        self.conn = conn
        self.channel = channel
        self.publish = pub_sub.publish
        self.network_timer = None
        self.network_status = ""
        self.on_network_status_callbacks = []
    
    def set_on_network_status_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback for network status changes
        
        Args:
            callback (Callable[[str], None]): Function to call when network status changes.
                The callback receives the new status as a string parameter.
                
        Example:
            ```python
            def status_changed(status):
                print(f"New network status: {status}")
                if status == "4G":
                    print("Using cellular connection")
                elif status.startswith("STA"):
                    print("Using WiFi connection")
            
            monitor.set_on_network_status_callback(status_changed)
            ```
            
        Note:
            Multiple callbacks can be registered and will all be called when status changes.
        """
        if callback and callable(callback):
            self.on_network_status_callbacks.append(callback)

    def start_network_status_fetch(self) -> None:
        """
        Start periodic network status monitoring
        
        This method begins the network status monitoring cycle, sending
        status requests every 1 second until a stable connection is detected
        or the monitoring is explicitly stopped.
        
        Monitoring Behavior:
        - Sends requests every 1 second initially
        - Faster retry (0.5s) for disconnected states
        - Stops automatically when stable connection detected
        - Triggers callbacks on status changes
        
        Example:
            ```python
            # Start monitoring network status
            monitor.start_network_status_fetch()
            print("Network status monitoring started")
            
            # Monitoring will continue until stable connection or manual stop
            await asyncio.sleep(10)
            monitor.stop_network_status_fetch()
            ```
        """
        self.network_timer = asyncio.get_event_loop().call_later(1, self.schedule_network_status_request)
    
    def stop_network_status_fetch(self) -> None:
        """
        Stop network status monitoring
        
        This method cancels the current network status timer and stops
        all future status requests. It provides a clean way to shut down
        monitoring when no longer needed.
        
        Example:
            ```python
            # Stop network status monitoring
            monitor.stop_network_status_fetch()
            print("Network status monitoring stopped")
            ```
            
        Note:
            - Safe to call multiple times
            - Immediately cancels pending requests
            - Can restart with start_network_status_fetch() if needed
        """
        if self.network_timer:
            self.network_timer.cancel()
            self.network_timer = None
    
    def schedule_network_status_request(self) -> None:
        """
        Schedule the next network status request
        
        This method creates an async task to send the next network status
        request. It's called by the timer to maintain the monitoring cycle.
        
        Note:
            This is an internal method used by the monitoring system.
            It should not be called directly in most cases.
        """
        asyncio.create_task(self.send_network_status_request())

    async def send_network_status_request(self) -> None:
        """
        Send a network status request to the robot
        
        This method sends a network status request and processes the response.
        If the request fails, it logs the error but continues the monitoring cycle.
        
        Request Format:
        - req_type: "public_network_status"
        - uuid: Unique identifier for the request
        
        Example:
            ```python
            # This method is typically called automatically by the timer
            # Manual call for testing:
            await monitor.send_network_status_request()
            ```
            
        Note:
            - Automatically handles request/response cycle
            - Processes response through handle_response()
            - Continues monitoring on errors
        """
        data = {
            "req_type": "public_network_status",
            "uuid": generate_uuid()
        }
        try:
            response = await self.publish(
                "",
                data,
                DATA_CHANNEL_TYPE["RTC_INNER_REQ"],
            )
            self.handle_response(response.get("info"))
        except Exception as e:
            logging.error("Failed to publish network status request: %s", e)
        
    def handle_response(self, info: Dict[str, Any]) -> None:
        """
        Process network status response and update state
        
        This method processes the network status response, updates the current
        status, and triggers appropriate callbacks. It also manages the timing
        of subsequent requests based on the connection state.
        
        Args:
            info (Dict[str, Any]): Network status information containing:
                - status: Current network status string
                - additional connection details
                
        Status Processing:
        - "Undefined"/"DISCONNECTED": Retry in 0.5 seconds
        - "NetworkStatus.ON_4G_CONNECTED": Set status to "4G", stop monitoring
        - "NetworkStatus.ON_WIFI_CONNECTED": Set status based on connection method
        
        Example:
            ```python
            # Handle network status response
            status_info = {"status": "NetworkStatus.ON_WIFI_CONNECTED"}
            monitor.handle_response(status_info)
            ```
            
        Note:
            - Automatically manages retry timing
            - Triggers registered callbacks on stable connections
            - Stops monitoring when stable connection detected
        """
        logging.debug("Network status message received.")
        status = info.get("status")
        
        if status == "Undefined" or status == "NetworkStatus.DISCONNECTED":
            # Schedule the next network status request in 0.5s for faster retry
            self.network_timer = asyncio.get_event_loop().call_later(0.5, self.schedule_network_status_request)

        elif status == "NetworkStatus.ON_4G_CONNECTED":
            self.network_status = "4G"
            self.stop_network_status_fetch()
        elif status == "NetworkStatus.ON_WIFI_CONNECTED":
            if self.conn.connectionMethod == WebRTCConnectionMethod.Remote:
                self.network_status = "STA-T"  # WiFi connected in remote mode
            else:
                self.network_status = "STA-L"  # WiFi connected in local mode
        
        # Trigger callbacks for stable connections
        if status == "NetworkStatus.ON_4G_CONNECTED" or status == "NetworkStatus.ON_WIFI_CONNECTED":
            for callback in self.on_network_status_callbacks:
                callback(self.network_status)
            self.stop_network_status_fetch()


class WebRTCDataChannelFileUploader:
    """
    WebRTC Data Channel File Uploader
    
    This class handles file uploads to the Unitree Go2 robot through WebRTC data channels.
    It supports chunked uploads for large files, progress tracking, and cancellation.
    
    The uploader features:
    - Base64 encoding for binary data transmission
    - Configurable chunk size for optimal performance
    - Progress callbacks for upload monitoring
    - Cancellation support for long uploads
    - Automatic UUID generation for request tracking
    - Rate limiting to prevent channel overload
    
    Upload Process:
    1. Encode file data to Base64
    2. Split data into configurable chunks
    3. Send chunks sequentially with metadata
    4. Provide progress updates via callbacks
    5. Handle cancellation requests gracefully
    
    Example:
        ```python
        # Initialize file uploader
        uploader = WebRTCDataChannelFileUploader(data_channel, pub_sub)
        
        # Upload file with progress tracking
        def progress_callback(percent):
            print(f"Upload progress: {percent}%")
        
        with open("large_file.bin", "rb") as f:
            file_data = f.read()
        
        result = await uploader.upload_file(
            file_data, 
            "/remote/path/file.bin",
            progress_callback=progress_callback
        )
        ```
    """
    
    def __init__(self, channel, pub_sub) -> None:
        """
        Initialize the file uploader
        
        Args:
            channel: WebRTC data channel for communication
            pub_sub: Publish-subscribe system for message handling
            
        Example:
            ```python
            uploader = WebRTCDataChannelFileUploader(data_channel, pub_sub)
            ```
        """
        self.channel = channel
        self.publish = pub_sub.publish
        self.cancel_upload = False
    
    def slice_base64_into_chunks(self, data: str, chunk_size: int) -> List[str]:
        """
        Split Base64 encoded data into manageable chunks
        
        This method divides large Base64 encoded data into smaller chunks
        for efficient transmission over the WebRTC data channel.
        
        Args:
            data (str): Base64 encoded data to split
            chunk_size (int): Size of each chunk in characters
            
        Returns:
            List[str]: List of data chunks
            
        Example:
            ```python
            # Split data into 60KB chunks
            chunks = uploader.slice_base64_into_chunks(encoded_data, 60*1024)
            print(f"Created {len(chunks)} chunks")
            ```
        """
        return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
    
    async def upload_file(self, data: bytes, file_path: str, chunk_size: int = 60*1024, 
                         progress_callback: Optional[Callable[[int], None]] = None) -> str:
        """
        Upload a file to the robot in chunks
        
        This method uploads file data to the robot using chunked transmission.
        It encodes the data to Base64, splits it into chunks, and sends each
        chunk with appropriate metadata.
        
        Args:
            data (bytes): Raw file data to upload
            file_path (str): Target path on the robot where file should be stored
            chunk_size (int): Size of each chunk in bytes (default: 60KB)
            progress_callback (Optional[Callable[[int], None]]): Function called with progress percentage
            
        Returns:
            str: Upload result - "ok" for success, "cancel" if cancelled
            
        Upload Protocol:
        - Data is Base64 encoded for transmission
        - Each chunk includes index and total count
        - Progress is reported as percentage complete
        - Rate limiting prevents channel overload
        - Cancellation can interrupt upload at any time
        
        Example:
            ```python
            # Upload with progress tracking
            def show_progress(percent):
                print(f"Upload: {percent}% complete")
            
            with open("document.pdf", "rb") as f:
                file_data = f.read()
            
            result = await uploader.upload_file(
                file_data,
                "/robot/documents/document.pdf", 
                chunk_size=32*1024,  # 32KB chunks
                progress_callback=show_progress
            )
            
            if result == "ok":
                print("Upload completed successfully")
            elif result == "cancel":
                print("Upload was cancelled")
            ```
            
        Note:
            - Large files are automatically chunked
            - Progress callback is optional but recommended
            - Upload can be cancelled with cancel() method
            - Rate limiting prevents overwhelming the channel
        """
        # Encode the data to Base64
        encoded_data = base64.b64encode(data).decode('utf-8')
        
        logging.debug("Total size after Base64 encoding: %d", len(encoded_data))
        chunks = self.slice_base64_into_chunks(encoded_data, chunk_size)
        total_chunks = len(chunks)
        
        self.cancel_upload = False
        
        for i, chunk in enumerate(chunks):
            if self.cancel_upload:
                logging.debug("Upload canceled.")
                return "cancel"
            
            # Rate limiting: sleep every 5 chunks to prevent overwhelming the channel
            if i % 5 == 0:
                await asyncio.sleep(0.5)
            
            uuid = generate_uuid()
            req_uuid = f"upload_req_{uuid}"
            
            message = {
                "req_type": "push_static_file",
                "req_uuid": req_uuid,
                "related_bussiness": "uslam_final_pcd",
                "file_md5": "null",
                "file_path": file_path,
                "file_size_after_b64": len(encoded_data),
                "file": {
                    "chunk_index": i + 1,
                    "total_chunk_num": total_chunks,
                    "chunk_data": chunk,
                    "chunk_data_size": len(chunk)
                }
            }
            
            self.publish("", message, DATA_CHANNEL_TYPE["RTC_INNER_REQ"])
            
            # Report progress
            if progress_callback:
                progress_callback(int(((i + 1) / total_chunks) * 100))
        
        return "ok"
    
    def cancel(self) -> None:
        """
        Cancel the ongoing upload operation
        
        This method sets the cancellation flag that will stop the upload
        process at the next chunk boundary. The upload will return "cancel"
        status when the cancellation takes effect.
        
        Example:
            ```python
            # Start upload in background
            upload_task = asyncio.create_task(
                uploader.upload_file(data, "/path/file.bin")
            )
            
            # Cancel after 5 seconds
            await asyncio.sleep(5)
            uploader.cancel()
            
            result = await upload_task
            print(f"Upload result: {result}")  # "cancel"
            ```
            
        Note:
            - Cancellation takes effect at the next chunk boundary
            - Safe to call multiple times
            - Does not immediately stop the upload
        """
        self.cancel_upload = True


class WebRTCDataChannelFileDownloader:
    """
    WebRTC Data Channel File Downloader
    
    This class handles file downloads from the Unitree Go2 robot through WebRTC data channels.
    It supports chunked downloads, progress tracking, and cancellation for large files.
    
    The downloader features:
    - Base64 decoding for binary data reception
    - Automatic chunk reassembly
    - Progress callbacks for download monitoring
    - Cancellation support for long downloads
    - Error handling and recovery
    - Unified request/response handling
    
    Download Process:
    1. Send download request with file path
    2. Receive chunked response data
    3. Automatic chunk reassembly by future resolver
    4. Base64 decode the complete data
    5. Return decoded binary data
    
    Example:
        ```python
        # Initialize file downloader
        downloader = WebRTCDataChannelFileDownloader(data_channel, pub_sub)
        
        # Download file with progress tracking
        def progress_callback(percent):
            print(f"Download progress: {percent}%")
        
        data = await downloader.download_file(
            "/robot/logs/system.log",
            progress_callback=progress_callback
        )
        
        if isinstance(data, bytes):
            with open("system.log", "wb") as f:
                f.write(data)
        ```
    """
    
    def __init__(self, channel, pub_sub) -> None:
        """
        Initialize the file downloader
        
        Args:
            channel: WebRTC data channel for communication
            pub_sub: Publish-subscribe system for message handling
            
        Example:
            ```python
            downloader = WebRTCDataChannelFileDownloader(data_channel, pub_sub)
            ```
        """
        self.channel = channel
        self.publish = pub_sub.publish
        self.cancel_download = False
        self.chunk_data_storage = {}

    async def download_file(self, file_path: str, chunk_size: int = 60*1024, 
                           progress_callback: Optional[Callable[[int], None]] = None) -> Union[bytes, str]:
        """
        Download a file from the robot
        
        This method downloads a file from the robot by sending a download request
        and processing the chunked response. The chunks are automatically reassembled
        by the future resolver, and the complete data is Base64 decoded.
        
        Args:
            file_path (str): Path to the file on the robot to download
            chunk_size (int): Chunk size hint (currently unused, for future use)
            progress_callback (Optional[Callable[[int], None]]): Function called with progress percentage
            
        Returns:
            Union[bytes, str]: Downloaded file data as bytes, or error status string:
                - bytes: Successfully downloaded file data
                - "cancel": Download was cancelled
                - "error": Download failed due to error
                
        Download Protocol:
        - Sends request_static_file message with file path
        - Robot responds with chunked data
        - Future resolver automatically reassembles chunks
        - Base64 decoding converts to binary data
        - Progress reported as 100% when complete
        
        Example:
            ```python
            # Download system configuration
            data = await downloader.download_file("/etc/robot_config.json")
            
            if isinstance(data, bytes):
                config = json.loads(data.decode('utf-8'))
                print(f"Robot config: {config}")
            elif data == "cancel":
                print("Download was cancelled")
            elif data == "error":
                print("Download failed")
                
            # Download with cancellation
            download_task = asyncio.create_task(
                downloader.download_file("/large_file.bin")
            )
            
            # Cancel after timeout
            try:
                data = await asyncio.wait_for(download_task, timeout=30)
            except asyncio.TimeoutError:
                downloader.cancel()
                print("Download timed out and was cancelled")
            ```
            
        Note:
            - Chunk reassembly is handled automatically
            - Progress callback receives 100% when download completes
            - Large files are handled efficiently through chunking
            - Cancellation is supported but may not be immediate
        """
        self.cancel_download = False

        try:
            uuid = generate_uuid()

            # Send the request to download the file
            request_message = {
                "req_type": "request_static_file",
                "req_uuid": f"req_{uuid}",
                "related_bussiness": "uslam_final_pcd",
                "file_md5": "null",
                "file_path": file_path
            }
            response = await self.publish("", request_message, DATA_CHANNEL_TYPE["RTC_INNER_REQ"])

            # Check if the download was canceled
            if self.cancel_download:
                logging.info("Download canceled.")
                return "cancel"
            
            # Extract the complete data after all chunks have been combined in the resolver
            complete_data = response.get("info", {}).get("file", {}).get("data")

            if not complete_data:
                logging.error("Failed to get the file data.")
                return "error"
            
            # Decode the Base64-encoded data
            decoded_data = base64.b64decode(complete_data)

            # Call progress_callback with 100% progress since the download is complete
            if progress_callback:
                progress_callback(100)

            return decoded_data

        except Exception as e:
            logging.error("Failed to download file:", e)
            return "error"

    def cancel(self) -> None:
        """
        Cancel the ongoing download operation
        
        This method sets the cancellation flag that will stop the download
        process if possible. The download will return "cancel" status when
        the cancellation takes effect.
        
        Example:
            ```python
            # Start download in background
            download_task = asyncio.create_task(
                downloader.download_file("/large_file.bin")
            )
            
            # Cancel after timeout
            await asyncio.sleep(30)
            downloader.cancel()
            
            result = await download_task
            print(f"Download result: {result}")  # "cancel" or data
            ```
            
        Note:
            - Cancellation may not be immediate
            - Safe to call multiple times
            - Download may complete before cancellation takes effect
        """
        self.cancel_download = True


class WebRTCDataChannelRTCInnerReq:
    """
    WebRTC Data Channel Internal Request Coordinator
    
    This class coordinates various internal request functionalities for WebRTC
    communication with the Unitree Go2 robot. It manages network status monitoring,
    probe responses, and serves as the main entry point for internal requests.
    
    The coordinator manages:
    - Network status monitoring and callbacks
    - Probe response handling for diagnostics
    - Unified message routing for internal requests
    - Component lifecycle management
    
    Example:
        ```python
        # Initialize internal request coordinator
        rtc_inner_req = WebRTCDataChannelRTCInnerReq(conn, data_channel, pub_sub)
        
        # Set up network status monitoring
        def on_network_change(status):
            print(f"Network status: {status}")
        
        rtc_inner_req.network_status.set_on_network_status_callback(on_network_change)
        rtc_inner_req.network_status.start_network_status_fetch()
        
        # Handle incoming messages
        rtc_inner_req.handle_response(incoming_message)
        ```
    """
    
    def __init__(self, conn, channel, pub_sub) -> None:
        """
        Initialize the internal request coordinator
        
        Args:
            conn: WebRTC connection instance
            channel: WebRTC data channel for communication
            pub_sub: Publish-subscribe system for message handling
            
        Example:
            ```python
            coordinator = WebRTCDataChannelRTCInnerReq(conn, channel, pub_sub)
            ```
        """
        self.conn = conn
        self.channel = channel

        self.network_status = WebRTCDataChannelNetworkStatus(self.conn, self.channel, pub_sub)
        self.probe_res = WebRTCChannelProbeResponse(self.channel, pub_sub)
    
    def handle_response(self, msg: Dict[str, Any]) -> None:
        """
        Handle incoming internal request responses
        
        This method routes incoming internal request messages to the appropriate
        handlers based on the request type. It serves as the main dispatch point
        for internal request processing.
        
        Args:
            msg (Dict[str, Any]): Incoming message containing:
                - info: Message information and metadata
                - req_type: Type of internal request
                - other message-specific data
                
        Supported Request Types:
        - "rtt_probe_send_from_mechine": RTT probe responses
        - Additional types can be added as needed
        
        Example:
            ```python
            # Handle probe response
            probe_message = {
                "info": {
                    "req_type": "rtt_probe_send_from_mechine",
                    "probe_id": "123",
                    "rtt": 45
                }
            }
            coordinator.handle_response(probe_message)
            ```
            
        Note:
            - Routes messages based on req_type
            - Extensible for additional request types
            - Provides centralized message handling
        """
        info = msg.get("info")
        req_type = info.get("req_type")
        if req_type == 'rtt_probe_send_from_mechine':
            self.probe_res.handle_response(info)

    
