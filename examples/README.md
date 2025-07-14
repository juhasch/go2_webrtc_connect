# Go2 WebRTC Connect Examples

This directory contains comprehensive examples showcasing the remote control and communication functionalities of the Unitree Go2 robot via WebRTC connections. These examples demonstrate various aspects of robot interaction including movement control, sensor data monitoring, audio/video streaming, and advanced features like LiDAR processing.

## Overview

The examples are organized into categories based on functionality:

- **Data Channel Examples**: Robot control, sensor monitoring, and communication
- **Audio Examples**: Audio streaming, MP3 playback, and real-time audio communication  
- **Video Examples**: Camera streaming and video processing
- **Advanced Examples**: LiDAR visualization, multi-stream processing, and rerun integration

## Examples Directory

| Example | Description | Category |
|---------|-------------|----------|
| **Data Channel** | | |
| `handstand_example.py` | Simple handstand demonstration using Go2RobotHelper | Robot Control |
| `handstand_example_fixed.py` | Advanced handstand with state monitoring and debugging | Robot Control |
| `heart_gesture_test.py` | Heart gesture performance testing in multiple modes | Robot Control |
| `simple_handstand_example.py` | Minimal handstand example (25 lines) | Robot Control |
| `simple_heart_gesture_example.py` | Minimal heart gesture example with mode comparison | Robot Control |
| `sport_commands_example.py` | Comprehensive sport command demonstration | Robot Control |
| `sportmode/sportmode.py` | Basic sport mode operations and movement commands | Robot Control |
| `example_heartbeat.py` | Connection heartbeat monitoring with Go2RobotHelper | Communication |
| `example_heartbeat_advanced.py` | Advanced heartbeat with custom connection handling | Communication |
| `quick_heartbeat_test.py` | Fast heartbeat connectivity test | Communication |
| `lowstate/lowstate.py` | Low-level robot state monitoring and display | Sensor Data |
| `sportmodestate/sportmodestate.py` | Sport mode state monitoring with detailed feedback | Sensor Data |
| `sportmodestate/compare_timestamps.py` | Timestamp comparison and latency analysis | Sensor Data |
| `multiplestate/multiplestate.py` | Multiple sensor stream monitoring simultaneously | Sensor Data |
| `robot_odometry/robot_odometry.py` | Robot odometry and position tracking | Navigation |
| `robot_odometry/simple_robot_odometry.py` | Simplified odometry monitoring | Navigation |
| `lidar/lidar_stream.py` | Basic LiDAR data streaming and processing | LiDAR |
| `lidar/plot_lidar_stream.py` | Real-time LiDAR data visualization with matplotlib | LiDAR |
| `lidar/rerun_lidar_stream.py` | LiDAR visualization using Rerun framework | LiDAR |
| `vui/vui.py` | Voice User Interface (VUI) control and feedback | User Interface |
| **Audio** | | |
| `mp3_player/play_mp3.py` | MP3 file playback using FFmpeg audio player | Audio Streaming |
| `mp3_player/webrtc_audio_player.py` | Audio upload and playback via WebRTC AudioHub | Audio Management |
| `internet_radio/stream_radio.py` | Internet radio streaming to robot speakers | Audio Streaming |
| `live_audio/live_recv_audio.py` | Real-time audio reception from robot microphone | Audio Capture |
| `save_audio/save_audio_to_file.py` | Audio recording and file saving functionality | Audio Capture |
| **Video** | | |
| `video/camera_stream/display_video_channel.py` | Robot camera stream display and processing | Video Streaming |
| **Advanced** | | |
| `rerun_video_lidar_stream.py` | Combined video and LiDAR streaming with Rerun | Multi-Stream |
| `rerun_stream.py` | General Rerun streaming setup | Visualization |

## Connection Setup

### Environment Variables

Set the robot's IP address using the `ROBOT_IP` environment variable:

```bash
export ROBOT_IP=192.168.1.100
python examples/data_channel/handstand_example.py
```

### Connection Methods

The examples support three connection methods:

#### 1. **Local AP Mode** (Default for direct connection)
Direct connection when the robot is in Access Point mode:
```python
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
# Uses IP: 192.168.12.1 (robot's AP mode IP)
```

#### 2. **Local STA Mode** (Recommended for network connection)
Connection via local WiFi network using IP address:
```python
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip="192.168.1.100")
# Or using environment variable: ROBOT_IP=192.168.1.100
```

#### 3. **Remote Mode** (For internet connection)
Remote connection through Unitree's TURN server:
```python
conn = Go2WebRTCConnection(
    WebRTCConnectionMethod.Remote,
    serialNumber="B42D2000XXXXXXXX",
    username="your_email@example.com",
    password="your_password"
)
```

### Go2RobotHelper vs Direct Connection

Many examples now use the **Go2RobotHelper** for simplified connection management:

```python
# Using Go2RobotHelper (recommended for new examples)
from go2_webrtc_driver import Go2RobotHelper

async with Go2RobotHelper() as robot:
    await robot.ensure_mode("ai")
    await robot.execute_command("Hello")

# Using direct WebRTCConnection (for advanced control)
from go2_webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
await conn.connect()
```

## Running Examples

1. **Set connection parameters:**
   ```bash
   export ROBOT_IP=192.168.1.100  # Your robot's IP address
   ```

2. **Navigate to examples directory:**
   ```bash
   cd examples
   ```

3. **Run an example:**
   ```bash
   # Simple robot control
   python data_channel/handstand_example.py
   
   # Audio playback
   python audio/mp3_player/play_mp3.py
   
   # LiDAR visualization
   python data_channel/lidar/plot_lidar_stream.py
   
   # Video streaming
   python video/camera_stream/display_video_channel.py
   ```

## Prerequisites

- **Robot Requirements**: Unitree Go2 robot (AIR/PRO/EDU) with firmware 1.0.19-1.1.7
- **Network Setup**: Robot and computer connected to the same WiFi network (for LocalSTA mode)
- **Python Dependencies**: Install using `pip install -e .` from the project root

## Safety Notes

- Ensure adequate space around the robot before running movement examples
- Monitor the robot during operation and be prepared to stop programs (Ctrl+C)
- Start with simple examples before attempting complex maneuvers
- Check robot battery level and ensure stable surface for operations

## Getting Help

- Check individual example docstrings for specific usage instructions
- See `data_channel/README_robot_helper.md` for Go2RobotHelper documentation
- Review `data_channel/CONVERSION_SUMMARY.md` for example conversion details
- Refer to the main project README for additional setup and troubleshooting

For issues or questions, please check the project's GitHub issues page. 