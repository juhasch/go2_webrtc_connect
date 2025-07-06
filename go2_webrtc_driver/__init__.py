"""
Unitree Go2 WebRTC Driver Package
=================================

This package provides a comprehensive Python implementation for connecting to the Unitree Go2 Robot 
via WebRTC protocol. It enables high-level control of the robot without requiring jailbreak or 
firmware manipulation, working out of the box with Go2 AIR/PRO/EDU models.

The package supports multiple connection methods:
- AP Mode: Direct connection to Go2 in access point mode
- STA-L Mode: Connection via local network using IP or serial number
- STA-T Mode: Remote connection through Unitree's TURN server

Key Features:
- Audio and video streaming (sendrecv/recvonly channels)
- LiDAR data processing with built-in decoders
- Robot control through data channels
- Multicast device discovery
- End-to-end encryption for secure communication

Supported firmware versions: 1.0.19-1.0.25, 1.1.1-1.1.7

Example:
    Basic usage with local AP mode:
    
    >>> from go2_webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
    >>> conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
    >>> await conn.connect()
    
Authors:
    - Original implementation by tfoldi
    - LiDAR support by abizovnuralem
    - Enhanced by MrRobotoW and TheRoboVerse community
"""

# Package version
__version__ = "1.0.0a"

# Export main classes and constants for easier importing
from .webrtc_driver import Go2WebRTCConnection
from .constants import WebRTCConnectionMethod, SPORT_CMD, RTC_TOPIC, VUI_COLOR
from .webrtc_audiohub import WebRTCAudioHub
from .multicast_scanner import discover_ip_sn

import aioice
import aiortc
import logging
from packaging import version

class Connection(aioice.Connection):
    local_username = aioice.utils.random_string(4)
    local_password = aioice.utils.random_string(22)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logging.info(f"aioice version: {aioice.__version__}")
        self.local_username = Connection.local_username
        self.local_password = Connection.local_password

aioice.Connection = Connection  # type: ignore

ver = version.Version(aiortc.__version__)
logging.info(f"aiortc version: {aiortc.__version__}")

if ver == version.Version("1.10.0"):
    X509_DIGEST_ALGORITHMS = {
        "sha-256": "SHA256",
    }
    aiortc.rtcdtlstransport.X509_DIGEST_ALGORITHMS = X509_DIGEST_ALGORITHMS

elif ver >= version.Version("1.11.0"):
    # Syntax changed in aiortc 1.11.0, so we need to use the hashes module
    from cryptography.hazmat.primitives import hashes

    X509_DIGEST_ALGORITHMS = {
        "sha-256": hashes.SHA256(),  # type: ignore
    }
    aiortc.rtcdtlstransport.X509_DIGEST_ALGORITHMS = X509_DIGEST_ALGORITHMS


__all__ = [
    'Go2WebRTCConnection',
    'WebRTCConnectionMethod', 
    'SPORT_CMD',
    'RTC_TOPIC',
    'VUI_COLOR',
    'WebRTCAudioHub',
    'discover_ip_sn',
]