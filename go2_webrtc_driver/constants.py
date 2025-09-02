"""
WebRTC Driver Constants and Configuration
========================================

This module contains all constants, enums, and configuration dictionaries used throughout
the Go2 WebRTC driver. It centralizes all hardcoded values for easy maintenance and 
configuration management.

Contents:
- WebRTC data channel message types
- Connection method enumeration
- Robot error codes and messages
- RTC topic definitions for pub/sub messaging
- Sport mode command mappings
- VUI color constants
- Audio API command identifiers
"""

from enum import Enum

# WebRTC Data Channel Message Types
# These constants define the various message types used in WebRTC data channel communication
DATA_CHANNEL_TYPE = {
    "VALIDATION": "validation",        # Connection validation messages
    "SUBSCRIBE": "subscribe",          # Topic subscription requests
    "UNSUBSCRIBE": "unsubscribe",      # Topic unsubscription requests
    "MSG": "msg",                      # General data messages
    "REQUEST": "req",                  # Request messages
    "RESPONSE": "res",                 # Response messages
    "VID": "vid",                      # Video channel control
    "AUD": "aud",                      # Audio channel control
    "ERR": "err",                      # Error messages
    "HEARTBEAT": "heartbeat",          # Connection heartbeat
    "RTC_INNER_REQ": "rtc_inner_req",  # Internal RTC requests
    "RTC_REPORT": "rtc_report",        # RTC status reports
    "ADD_ERROR": "add_error",          # Add error notification
    "RM_ERROR": "rm_error",            # Remove error notification
    "ERRORS": "errors",                # Error list messages
}


class WebRTCConnectionMethod(Enum):
    """
    Enumeration of supported WebRTC connection methods.
    
    Values:
        LocalAP (1): Direct connection to Go2 in Access Point mode (IP: 192.168.12.1)
        LocalSTA (2): Connection via local network using IP address or serial number
        Remote (3): Remote connection through Unitree's TURN server with authentication
    
    Example:
        >>> conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
        >>> await conn.connect()
    """
    LocalAP = 1
    LocalSTA = 2
    Remote = 3


# Application Error Messages
# Maps error codes to human-readable descriptions for troubleshooting
app_error_messages = {
    # Communication errors (100 series)
    "app_error_code_100_1": "DDS message timeout",
    "app_error_code_100_10": "Battery communication error",
    "app_error_code_100_2": "Distribution switch abnormal",
    "app_error_code_100_20": "Abnormal mote control communication",
    "app_error_code_100_40": "MCU communication error",
    "app_error_code_100_80": "Motor communication error",
    
    # Fan system errors (200 series)
    "app_error_code_200_1": "Rear left fan jammed",
    "app_error_code_200_2": "Rear right fan jammed",
    "app_error_code_200_4": "Front fan jammed",
    
    # Motor system errors (300 series)
    "app_error_code_300_1": "Overcurrent",
    "app_error_code_300_10": "Winding overheating",
    "app_error_code_300_100": "Motor communication interruption",
    "app_error_code_300_2": "Overvoltage",
    "app_error_code_300_20": "Encoder abnormal",
    "app_error_code_300_4": "Driver overheating",
    "app_error_code_300_8": "Generatrix undervoltage",
    
    # Sensor errors (400 series)
    "app_error_code_400_1": "Motor rotate speed abnormal",
    "app_error_code_400_10": "Abnormal dirt index",
    "app_error_code_400_2": "PointCloud data abnormal",
    "app_error_code_400_4": "Serial port data abnormal",
    
    # UWB system errors (500 series)
    "app_error_code_500_1": "UWB serial port open abnormal",
    "app_error_code_500_2": "Robot dog information retrieval abnormal",
    
    # Protection system errors (600 series)
    "app_error_code_600_4": "Overheating software protection",
    "app_error_code_600_8": "Low battery software protection",
    
    # Error source categories
    "app_error_source_100": "Communication firmware malfunction",
    "app_error_source_200": "Communication firmware malfunction",
    "app_error_source_300": "Motor malfunction",
    "app_error_source_400": "Radar malfunction",
    "app_error_source_500": "UWB malfunction",
    "app_error_source_600": "Motion Control",
    
    # Wheel-specific errors
    "app_error_wheel_300_100": "Motor Communication Interruption",
    "app_error_wheel_300_40": "Calibration Data Abnormality",
    "app_error_wheel_300_80": "Abnormal Reset"
}

# RTC Topic Definitions
# Maps topic names to their corresponding message routing paths in the pub/sub system
RTC_TOPIC = {
    # Low-level state topics
    "LOW_STATE": "rt/lf/lowstate",                    # Robot low-level state information
    "MULTIPLE_STATE": "rt/multiplestate",             # Multiple sensor state data
    "LOW_CMD": "rt/lowcmd",                           # Low-level motor commands
    "WIRELESS_CONTROLLER": "rt/wirelesscontroller",   # Wireless controller input
    
    # Camera and video topics
    "FRONT_PHOTO_REQ": "rt/api/videohub/request",     # Front camera photo requests
    
    # LiDAR topics
    "ULIDAR_SWITCH": "rt/utlidar/switch",             # LiDAR on/off control
    "ULIDAR": "rt/utlidar/voxel_map",                 # LiDAR voxel map data
    "ULIDAR_ARRAY": "rt/utlidar/voxel_map_compressed", # Compressed LiDAR data
    "ULIDAR_STATE": "rt/utlidar/lidar_state",         # LiDAR system state
    "ROBOTODOM": "rt/utlidar/robot_pose",             # Robot pose from LiDAR
    
    # UWB (Ultra-Wideband) topics
    "UWB_REQ": "rt/api/uwbswitch/request",            # UWB system requests
    "UWB_STATE": "rt/uwbstate",                       # UWB system state
    
    # Sport mode topics
    "SPORT_MOD": "rt/api/sport/request",              # Sport mode commands
    "SPORT_MOD_STATE": "rt/sportmodestate",           # Sport mode state
    "LF_SPORT_MOD_STATE": "rt/lf/sportmodestate",     # Low-frequency sport mode state
    
    # System and service topics
    "BASH_REQ": "rt/api/bashrunner/request",          # Bash command execution
    "SELF_TEST": "rt/selftest",                       # System self-test
    "SERVICE_STATE": "rt/servicestate",               # Service status
    
    # Navigation and mapping topics
    "GRID_MAP": "rt/mapping/grid_map",                # 2D grid map data
    "SLAM_QT_COMMAND": "rt/qt_command",               # SLAM Qt interface commands
    "SLAM_ADD_NODE": "rt/qt_add_node",                # SLAM graph node addition
    "SLAM_ADD_EDGE": "rt/qt_add_edge",                # SLAM graph edge addition
    "SLAM_QT_NOTICE": "rt/qt_notice",                 # SLAM notifications
    "SLAM_PC_TO_IMAGE_LOCAL": "rt/pctoimage_local",   # Point cloud to image conversion
    "SLAM_ODOMETRY": "rt/lio_sam_ros2/mapping/odometry", # SLAM odometry data
    
    # Audio topics
    "AUDIO_HUB_REQ": "rt/api/audiohub/request",       # Audio hub requests
    "AUDIO_HUB_PLAY_STATE": "rt/audiohub/player/state", # Audio playback state
    
    # AI and interaction topics
    "GPT_FEEDBACK": "rt/gptflowfeedback",             # GPT interaction feedback
    "VUI": "rt/api/vui/request",                      # Voice User Interface requests
    "ASSISTANT_RECORDER": "rt/api/assistant_recorder/request", # Voice assistant recording
    
    # Robotic arm topics
    "ARM_COMMAND": "rt/arm_Command",                  # Robotic arm commands
    "ARM_FEEDBACK": "rt/arm_Feedback",                # Robotic arm feedback
    
    # Sensor topics
    "GAS_SENSOR": "rt/gas_sensor",                    # Gas sensor readings
    "GAS_SENSOR_REQ": "rt/api/gas_sensor/request",    # Gas sensor requests
    
    # Advanced navigation topics
    "OBSTACLES_AVOID": "rt/api/obstacles_avoid/request", # Obstacle avoidance
    "LIDAR_MAPPING_CMD": "rt/uslam/client_command",   # LiDAR mapping commands
    "LIDAR_MAPPING_CLOUD_POINT": "rt/uslam/frontend/cloud_world_ds", # Downsampled point cloud
    "LIDAR_MAPPING_ODOM": "rt/uslam/frontend/odom",   # LiDAR mapping odometry
    "LIDAR_MAPPING_PCD_FILE": "rt/uslam/cloud_map",   # Point cloud map file
    "LIDAR_MAPPING_SERVER_LOG": "rt/uslam/server_log", # Mapping server logs
    "LIDAR_LOCALIZATION_ODOM": "rt/uslam/localization/odom", # Localization odometry
    "LIDAR_NAVIGATION_GLOBAL_PATH": "rt/uslam/navigation/global_path", # Global path planning
    "LIDAR_LOCALIZATION_CLOUD_POINT": "rt/uslam/localization/cloud_world", # Localization point cloud
    
    # Programming and control topics
    "PROGRAMMING_ACTUATOR_CMD": "rt/programming_actuator/command", # Programming interface commands
    "MOTION_SWITCHER": "rt/api/motion_switcher/request", # Motion mode switching
}

# Sport Mode Command Mappings
# Maps command names to their corresponding API identifiers for robot movement control
SPORT_CMD = {
    # Basic movement commands
    "Damp": 1001,                    # Enable damping mode
    "BalanceStand": 1002,            # Maintain balanced standing position
    "StopMove": 1003,                # Stop all movement
    "StandUp": 1004,                 # Stand up from sitting/lying position
    "StandDown": 1005,               # Lower body position
    "RecoveryStand": 1006,           # Recovery standing after fall
    "Sit": 1009,                     # Sit down
    "RiseSit": 1010,                 # Rise from sitting position
    
    # Movement and gait commands
    "Move": 1008,                    # Basic movement command
    "SwitchGait": 1011,              # Switch between gait patterns
    "ContinuousGait": 1019,          # Continuous gait pattern
    "EconomicGait": 1035,            # Energy-efficient gait
    "FreeWalk": 1045,                # Free walking mode
    "LeadFollow": 1045,              # Leader-follower mode
    
    # Orientation and pose commands
    "Euler": 1007,                   # Euler angle orientation control
    "Pose": 1028,                    # Pose adjustment
    "BodyHeight": 1013,              # Body height adjustment
    "FootRaiseHeight": 1014,         # Foot raise height control
    "SpeedLevel": 1015,              # Speed level setting
    
    # Action commands
    "Hello": 1016,                   # Greeting gesture
    "Stretch": 1017,                 # Stretching movement
    "Wallow": 1021,                  # Wallowing behavior
    "Scrape": 1029,                  # Scraping motion
    "WiggleHips": 1033,              # Hip wiggling motion
    "FingerHeart": 1036,             # Heart gesture with legs
    "Content": 1020,                 # Content/satisfied behavior
    "StandOut": 1039,                # Stand out behavior
    
    # Dance and entertainment commands
    "Dance1": 1022,                  # Dance routine 1
    "Dance2": 1023,                  # Dance routine 2
    
    # Acrobatic commands
    "FrontFlip": 1030,               # Front flip
    "BackFlip": 1044,                # Back flip
    "LeftFlip": 1042,                # Left flip
    "RightFlip": 1043,               # Right flip
    "FrontJump": 1031,               # Front jump
    "FrontPounce": 1032,             # Front pounce
    "Bound": 1304,                   # Bounding movement
    "Handstand": 1301,               # Handstand position
    
    # Special movement patterns
    "MoonWalk": 1305,                # Moonwalk movement
    "OnesidedStep": 1303,            # One-sided stepping
    "CrossStep": 1302,               # Cross stepping
    "CrossWalk": 1051,               # Cross walking
    
    # Trajectory and control commands
    "TrajectoryFollow": 1018,        # Follow predefined trajectory
    "Trigger": 1012,                 # Trigger command
    "SwitchJoystick": 1027,          # Switch joystick control mode
    
    # Status and query commands
    "GetBodyHeight": 1024,           # Get current body height
    "GetFootRaiseHeight": 1025,      # Get current foot raise height
    "GetSpeedLevel": 1026,           # Get current speed level
    "GetState": 1034,                # Get current robot state
    
    # Legacy commands (for backward compatibility)
    "Standup": 1050,                 # Alternative standup command
}


# MCF Mode Command Mappings (Firmware 1.1.7+)
# Default motion control framework that unifies normal and AI modes
MCF_CMD = {
    # Basic movement commands
    "Damp": 1001,
    "BalanceStand": 1002,
    "StopMove": 1003,
    "StandUp": 1004,
    "StandDown": 1005,
    "RecoveryStand": 1006,
    "Sit": 1009,
    "RiseSit": 1010,

    # Movement and gait commands
    "Move": 1008,
    "SwitchGait": 1011,
    "ContinuousGait": 1019,
    "EconomicGait": 1063,
    "StaticWalk": 1061,
    "TrotRun": 1062,
    "FreeWalk": 2045,
    "FreeBound": 2046,
    "FreeJump": 2047,
    "FreeAvoid": 2048,
    "ClassicWalk": 2049,
    "BackStand": 2050,
    "CrossStep": 2051,
    "LeadFollow": 2056,

    # Orientation and pose commands
    "Euler": 1007,
    "Pose": 1028,
    "BodyHeight": 1013,
    "FootRaiseHeight": 1014,
    "SpeedLevel": 1015,

    # Action commands
    "Hello": 1016,
    "Stretch": 1017,
    "Content": 1020,
    "Scrape": 1029,
    "Heart": 1036,

    # Dance and entertainment commands
    "Dance1": 1022,
    "Dance2": 1023,

    # Acrobatic commands
    "FrontFlip": 1030,
    "LeftFlip": 2041,
    "BackFlip": 2043,
    "FrontJump": 1031,
    "FrontPounce": 1032,
    "Handstand": 2044,

    # Trajectory and control commands
    "TrajectoryFollow": 1018,
    "Trigger": 1012,
    "SwitchJoystick": 1027,

    # Status and query commands
    "GetBodyHeight": 1024,
    "GetFootRaiseHeight": 1025,
    "GetSpeedLevel": 1026,
    "GetState": 1034,

    # Recovery settings
    "SetAutoRecovery": 2054,
    "GetAutoRecovery": 2055,

    # Avoidance settings
    "SwitchAvoidMode": 2058,
}


class VUI_COLOR:
    """
    Voice User Interface LED color constants.
    
    These constants define the available colors for the robot's LED indicators
    during voice interaction modes.
    
    Usage:
        >>> from go2_webrtc_driver.constants import VUI_COLOR
        >>> color = VUI_COLOR.BLUE
    """
    WHITE: str = 'white'
    RED: str = 'red'
    YELLOW: str = 'yellow'
    BLUE: str = 'blue'
    GREEN: str = 'green'
    CYAN: str = 'cyan'
    PURPLE: str = 'purple'


# Audio API Command Identifiers
# Maps audio-related commands to their API identifiers for the audio hub system
AUDIO_API = {
    # Audio Player Commands (1000 series)
    "GET_AUDIO_LIST": 1001,          # Retrieve list of available audio files
    "SELECT_START_PLAY": 1002,       # Select and start playing audio file
    "PAUSE": 1003,                   # Pause current audio playback
    "UNSUSPEND": 1004,               # Resume paused audio playback
    "SELECT_PREV_START_PLAY": 1005,  # Select and play previous audio file
    "SELECT_NEXT_START_PLAY": 1006,  # Select and play next audio file
    "SET_PLAY_MODE": 1007,           # Set audio playback mode (loop, single, etc.)
    "SELECT_RENAME": 1008,           # Rename selected audio file
    "SELECT_DELETE": 1009,           # Delete selected audio file
    "GET_PLAY_MODE": 1010,           # Get current playback mode
    
    # Audio Upload Commands (2000 series)
    "UPLOAD_AUDIO_FILE": 2001,       # Upload new audio file to robot
    
    # Internal Corpus Commands (3000 series)
    "PLAY_START_OBSTACLE_AVOIDANCE": 3001,  # Play obstacle avoidance start sound
    "PLAY_EXIT_OBSTACLE_AVOIDANCE": 3002,   # Play obstacle avoidance exit sound
    "PLAY_START_COMPANION_MODE": 3003,      # Play companion mode start sound
    "PLAY_EXIT_COMPANION_MODE": 3004,       # Play companion mode exit sound
    
    # Megaphone Commands (4000 series)
    "ENTER_MEGAPHONE": 4001,         # Enter megaphone mode
    "EXIT_MEGAPHONE": 4002,          # Exit megaphone mode
    "UPLOAD_MEGAPHONE": 4003,        # Upload audio for megaphone use
    
    # Internal Long Corpus Commands (5000 series)
    "INTERNAL_LONG_CORPUS_SELECT_TO_PLAY": 5001,  # Select and play long audio corpus
}