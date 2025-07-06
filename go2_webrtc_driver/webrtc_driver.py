"""
Main WebRTC Driver for Unitree Go2 Robot Communication
======================================================

This module contains the main WebRTC connection class for communicating with the
Unitree Go2 robot. It provides a high-level interface for establishing WebRTC
connections, managing audio/video streams, and controlling the robot.

Key Features:
- Multiple connection methods (AP, Local Network, Remote)
- Automatic device discovery and connection
- Audio and video streaming management
- Data channel for robot control and sensor data
- Connection state monitoring and reconnection

Connection Methods:
- LocalAP: Direct connection in Access Point mode
- LocalSTA: Local network connection using IP or serial number
- Remote: Remote connection through Unitree's TURN server

Example:
    >>> # Connect in AP mode
    >>> conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
    >>> await conn.connect()
    >>> 
    >>> # Subscribe to robot state
    >>> await conn.datachannel.pub_sub.subscribe("rt/lf/lowstate")
"""

import logging
import json
import sys
import os
from typing import Optional, Dict, Any
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceServer, RTCConfiguration

from .unitree_auth import send_sdp_to_local_peer, send_sdp_to_remote_peer
from .webrtc_datachannel import WebRTCDataChannel
from .webrtc_audio import WebRTCAudioChannel
from .webrtc_video import WebRTCVideoChannel
from .constants import WebRTCConnectionMethod
from .util import fetch_public_key, fetch_token, fetch_turn_server_info, print_status
from .multicast_scanner import discover_ip_sn

# Enable logging for debugging if needed
# logging.basicConfig(level=logging.INFO)


class Go2WebRTCConnection:
    """
    Main WebRTC connection class for Unitree Go2 robot communication.
    
    This class provides a comprehensive interface for establishing and managing
    WebRTC connections with the Go2 robot across different connection methods.
    It handles authentication, connection establishment, and provides access
    to audio, video, and data channels.
    
    Attributes:
        pc (RTCPeerConnection): WebRTC peer connection instance
        sn (str): Robot serial number
        ip (str): Robot IP address
        connectionMethod (WebRTCConnectionMethod): Connection method being used
        isConnected (bool): Current connection status
        token (str): Authentication token for remote connections
        public_key: RSA public key for encryption (remote connections)
        datachannel (WebRTCDataChannel): Data channel for robot communication
        audio (WebRTCAudioChannel): Audio channel manager
        video (WebRTCVideoChannel): Video channel manager
    """
    
    def __init__(
        self, 
        connectionMethod: WebRTCConnectionMethod, 
        serialNumber: Optional[str] = None, 
        ip: Optional[str] = None, 
        username: Optional[str] = None, 
        password: Optional[str] = None
    ) -> None:
        """
        Initialize the Go2 WebRTC connection.
        
        Args:
            connectionMethod: Method to use for connection (LocalAP, LocalSTA, Remote)
            serialNumber: Robot serial number (required for LocalSTA and Remote)
            ip: Robot IP address (optional for LocalSTA, overrides environment variable)
            username: Unitree account username (required for Remote connections)
            password: Unitree account password (required for Remote connections)
            
        Example:
            >>> # AP mode connection
            >>> conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
            >>> 
            >>> # Local network with IP
            >>> conn = Go2WebRTCConnection(
            ...     WebRTCConnectionMethod.LocalSTA, 
            ...     ip="192.168.1.100"
            ... )
            >>> 
            >>> # Remote connection
            >>> conn = Go2WebRTCConnection(
            ...     WebRTCConnectionMethod.Remote,
            ...     serialNumber="B42D2000XXXXXXXX",
            ...     username="user@example.com",
            ...     password="password"
            ... )
        """
        self.pc: Optional[RTCPeerConnection] = None
        self.sn = serialNumber
        self.ip = ip if ip else os.getenv("ROBOT_IP")
        self.connectionMethod = connectionMethod
        self.isConnected = False
        
        # Initialize authentication for remote connections
        self.token = fetch_token(username, password) if username and password else ""
        self.public_key = None
        
        # Initialize channel managers (will be set up during connection)
        self.datachannel: Optional[WebRTCDataChannel] = None
        self.audio: Optional[WebRTCAudioChannel] = None
        self.video: Optional[WebRTCVideoChannel] = None

    async def connect(self) -> None:
        """
        Establish WebRTC connection to the Go2 robot.
        
        This method handles the complete connection process including device
        discovery (if needed), authentication, WebRTC setup, and channel
        initialization.
        
        Raises:
            ValueError: If device discovery fails or invalid configuration
            ConnectionError: If WebRTC connection fails
            SystemExit: If critical connection errors occur
            
        Example:
            >>> conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
            >>> await conn.connect()
            >>> print(f"Connected: {conn.isConnected}")
        """
        print_status("WebRTC connection", "🟡 started")
        
        if self.connectionMethod == WebRTCConnectionMethod.Remote:
            await self._connect_remote()
        elif self.connectionMethod == WebRTCConnectionMethod.LocalSTA:
            await self._connect_local_sta()
        elif self.connectionMethod == WebRTCConnectionMethod.LocalAP:
            await self._connect_local_ap()
        else:
            raise ValueError(f"Unsupported connection method: {self.connectionMethod}")

    async def _connect_remote(self) -> None:
        """Handle remote connection setup."""
        self.public_key = fetch_public_key()
        if not self.public_key:
            raise ConnectionError("Failed to fetch public key for remote connection")
            
        turn_server_info = fetch_turn_server_info(self.sn, self.token, self.public_key)
        if not turn_server_info:
            raise ConnectionError("Failed to fetch TURN server information")
            
        await self.init_webrtc(turn_server_info)

    async def _connect_local_sta(self) -> None:
        """Handle local STA connection setup with optional device discovery."""
        if not self.ip and self.sn:
            # Attempt device discovery using serial number
            discovered_ip_sn_addresses = discover_ip_sn()
            
            if discovered_ip_sn_addresses:
                if self.sn in discovered_ip_sn_addresses:
                    self.ip = discovered_ip_sn_addresses[self.sn]
                    logging.info(f"Discovered robot at IP: {self.ip}")
                else:
                    raise ValueError(
                        f"Serial number {self.sn} not found on network. "
                        "Please provide an IP address instead."
                    )
            else:
                raise ValueError(
                    "No devices found on the network. "
                    "Please provide an IP address instead."
                )
        
        if not self.ip:
            raise ValueError("IP address is required for LocalSTA connection")
            
        await self.init_webrtc(ip=self.ip)

    async def _connect_local_ap(self) -> None:
        """Handle local AP connection setup."""
        self.ip = "192.168.12.1"  # Standard Go2 AP mode IP
        await self.init_webrtc(ip=self.ip)
    
    async def disconnect(self) -> None:
        """
        Disconnect from the Go2 robot and clean up resources.
        
        This method properly closes the WebRTC connection and resets
        the connection state.
        
        Example:
            >>> await conn.disconnect()
            >>> print(f"Connected: {conn.isConnected}")  # False
        """
        if self.pc:
            await self.pc.close()
            self.pc = None
        self.isConnected = False
        print_status("WebRTC connection", "🔴 disconnected")

    async def reconnect(self) -> None:
        """
        Reconnect to the Go2 robot.
        
        This method performs a clean disconnect followed by a new connection
        attempt using the same configuration.
        
        Example:
            >>> # Reconnect after connection loss
            >>> await conn.reconnect()
        """
        await self.disconnect()
        await self.connect()
        print_status("WebRTC connection", "🟢 reconnected")

    def create_webrtc_configuration(
        self, 
        turn_server_info: Optional[Dict[str, Any]], 
        stunEnable: bool = True, 
        turnEnable: bool = True
    ) -> RTCConfiguration:
        """
        Create WebRTC configuration with ICE servers.
        
        This method sets up the ICE servers configuration for WebRTC connection,
        including TURN servers for NAT traversal and STUN servers for connection
        establishment.
        
        Args:
            turn_server_info: TURN server configuration from Unitree
            stunEnable: Whether to enable STUN server
            turnEnable: Whether to enable TURN server
            
        Returns:
            RTCConfiguration: Configured WebRTC configuration object
            
        Raises:
            ValueError: If TURN server information is invalid
        """
        ice_servers = []

        if turn_server_info:
            username = turn_server_info.get("user")
            credential = turn_server_info.get("passwd")
            turn_url = turn_server_info.get("realm")
            
            if username and credential and turn_url:
                if turnEnable:
                    ice_servers.append(
                        RTCIceServer(
                            urls=[turn_url],
                            username=username,
                            credential=credential
                        )
                    )
                if stunEnable:
                    # Use Google's public STUN server as fallback
                    stun_url = "stun:stun.l.google.com:19302"
                    ice_servers.append(
                        RTCIceServer(urls=[stun_url])
                    )
            else:
                raise ValueError("Invalid TURN server information provided")
        
        return RTCConfiguration(iceServers=ice_servers)

    async def init_webrtc(
        self, 
        turn_server_info: Optional[Dict[str, Any]] = None, 
        ip: Optional[str] = None
    ) -> None:
        """
        Initialize WebRTC peer connection and channels.
        
        This method sets up the complete WebRTC connection including peer
        connection, data channel, audio/video channels, and event handlers.
        
        Args:
            turn_server_info: TURN server configuration for remote connections
            ip: Robot IP address for local connections
        """
        # Create WebRTC configuration and peer connection
        configuration = self.create_webrtc_configuration(turn_server_info)
        self.pc = RTCPeerConnection(configuration)

        # Initialize communication channels
        self.datachannel = WebRTCDataChannel(self, self.pc)
        self.audio = WebRTCAudioChannel(self.pc, self.datachannel)
        self.video = WebRTCVideoChannel(self.pc, self.datachannel)

        # Set up WebRTC event handlers
        self._setup_webrtc_handlers()

        # Create and exchange SDP offer
        await self._handle_sdp_exchange(turn_server_info, ip)

        # Wait for data channel to be ready
        await self.datachannel.wait_datachannel_open()

    def _setup_webrtc_handlers(self) -> None:
        """Set up WebRTC connection event handlers."""
        
        @self.pc.on("icegatheringstatechange")
        async def on_ice_gathering_state_change() -> None:
            """Handle ICE gathering state changes."""
            state = self.pc.iceGatheringState
            status_map = {
                "new": "🔵 new",
                "gathering": "🟡 gathering",
                "complete": "🟢 complete"
            }
            if state in status_map:
                print_status("ICE Gathering State", status_map[state])

        @self.pc.on("iceconnectionstatechange")
        async def on_ice_connection_state_change() -> None:
            """Handle ICE connection state changes."""
            state = self.pc.iceConnectionState
            status_map = {
                "checking": "🔵 checking",
                "completed": "🟢 completed",
                "failed": "🔴 failed",
                "closed": "⚫ closed"
            }
            if state in status_map:
                print_status("ICE Connection State", status_map[state])

        @self.pc.on("connectionstatechange")
        async def on_connection_state_change() -> None:
            """Handle peer connection state changes."""
            state = self.pc.connectionState
            
            if state == "connecting":
                print_status("Peer Connection State", "🔵 connecting")
            elif state == "connected":
                self.isConnected = True
                print_status("Peer Connection State", "🟢 connected")
            elif state == "closed":
                self.isConnected = False
                print_status("Peer Connection State", "⚫ closed")
            elif state == "failed":
                self.isConnected = False
                print_status("Peer Connection State", "🔴 failed")
        
        @self.pc.on("signalingstatechange")
        async def on_signaling_state_change() -> None:
            """Handle signaling state changes."""
            state = self.pc.signalingState
            status_map = {
                "stable": "🟢 stable",
                "have-local-offer": "🟡 have-local-offer",
                "have-remote-offer": "🟡 have-remote-offer",
                "closed": "⚫ closed"
            }
            if state in status_map:
                print_status("Signaling State", status_map[state])
        
        @self.pc.on("track")
        async def on_track(track) -> None:
            """Handle incoming media tracks."""
            logging.info(f"Track received: {track.kind}")

            if track.kind == "video":
                # Wait for first frame and start video processing
                frame = await track.recv()
                await self.video.track_handler(track)
                
            elif track.kind == "audio":
                # Start audio processing loop
                frame = await track.recv()
                while True:
                    try:
                        frame = await track.recv()
                        await self.audio.frame_handler(frame)
                    except Exception as e:
                        logging.error(f"Audio processing error: {e}")
                        break

    async def _handle_sdp_exchange(
        self, 
        turn_server_info: Optional[Dict[str, Any]], 
        ip: Optional[str]
    ) -> None:
        """Handle SDP offer/answer exchange."""
        logging.info("Creating SDP offer...")
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        # Get SDP answer based on connection method
        if self.connectionMethod == WebRTCConnectionMethod.Remote:
            peer_answer_json = await self.get_answer_from_remote_peer(self.pc, turn_server_info)
        else:  # LocalSTA or LocalAP
            peer_answer_json = await self.get_answer_from_local_peer(self.pc, ip)

        # Process SDP answer
        if peer_answer_json is None:
            logging.error("Failed to get SDP answer from peer")
            print("Could not get SDP from the peer. Check if the Go2 is switched on")
            sys.exit(1)

        try:
            peer_answer = json.loads(peer_answer_json)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in SDP answer: {e}")
            sys.exit(1)

        if peer_answer.get('sdp') == "reject":
            print("Go2 is connected by another WebRTC client. Close your mobile APP and try again.")
            sys.exit(1)

        # Set remote description
        remote_sdp = RTCSessionDescription(
            sdp=peer_answer['sdp'], 
            type=peer_answer['type']
        )
        await self.pc.setRemoteDescription(remote_sdp)

    async def get_answer_from_remote_peer(
        self, 
        pc: RTCPeerConnection, 
        turn_server_info: Dict[str, Any]
    ) -> Optional[str]:
        """
        Get SDP answer from remote peer via Unitree's servers.
        
        Args:
            pc: RTCPeerConnection with local description set
            turn_server_info: TURN server configuration
            
        Returns:
            JSON string containing SDP answer, or None if failed
        """
        sdp_offer = pc.localDescription
        sdp_offer_json = {
            "id": "",
            "turnserver": turn_server_info,
            "sdp": sdp_offer.sdp,
            "type": sdp_offer.type,
            "token": self.token
        }

        logging.debug("Sending SDP offer for remote connection")
        return send_sdp_to_remote_peer(
            self.sn, 
            json.dumps(sdp_offer_json), 
            self.token, 
            self.public_key
        )

    async def get_answer_from_local_peer(
        self, 
        pc: RTCPeerConnection, 
        ip: str
    ) -> Optional[str]:
        """
        Get SDP answer from local peer via direct HTTP.
        
        Args:
            pc: RTCPeerConnection with local description set
            ip: Robot IP address
            
        Returns:
            JSON string containing SDP answer, or None if failed
        """
        sdp_offer = pc.localDescription
        sdp_offer_json = {
            "id": "STA_localNetwork" if self.connectionMethod == WebRTCConnectionMethod.LocalSTA else "",
            "sdp": sdp_offer.sdp,
            "type": sdp_offer.type,
            "token": self.token
        }

        logging.debug(f"Sending SDP offer to local peer at {ip}")
        return send_sdp_to_local_peer(ip, json.dumps(sdp_offer_json))


