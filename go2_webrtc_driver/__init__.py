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
__version__ = "1.0.0"

# Export main classes and constants for easier importing
from .webrtc_driver import Go2WebRTCConnection
from .constants import WebRTCConnectionMethod, SPORT_CMD, RTC_TOPIC, VUI_COLOR, MCF_CMD
from .multicast_scanner import discover_ip_sn
from .robot_helper import Go2RobotHelper, StateMonitor, RobotMode, create_example_main, simple_robot_connection

# Lazy import for WebRTCAudioHub to avoid soundfile import issues
def _get_webrtc_audiohub():
    """Lazy import for WebRTCAudioHub to avoid import errors"""
    try:
        from .webrtc_audiohub import WebRTCAudioHub
        return WebRTCAudioHub
    except ImportError as e:
        raise ImportError(f"WebRTCAudioHub import failed: {e}. This may be due to missing audio dependencies.") from e

__all__ = [
    'Go2WebRTCConnection',
    'WebRTCConnectionMethod', 
    'SPORT_CMD',
    'MCF_CMD',
    'RTC_TOPIC',
    'VUI_COLOR',
    'WebRTCAudioHub',
    'discover_ip_sn',
    'Go2RobotHelper',
    'StateMonitor',
    'RobotMode',
    'create_example_main',
    'simple_robot_connection',
]

# Create a module-level attribute that will be imported lazily
# This allows the package to be imported without triggering the audio dependencies
def __getattr__(name):
    if name == 'WebRTCAudioHub':
        return _get_webrtc_audiohub()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")