# Go2 WebRTC Examples

This directory contains essential examples for using the Go2 WebRTC driver.

## Data Channel Examples

### Basic Examples
- **`simple_handstand_example.py`** - Simple handstand demonstration using Go2RobotHelper
- **`simple_heart_gesture_example.py`** - Heart gesture demonstration using Go2RobotHelper
- **`simple_stand_example.py`** - Basic stand command example

### Advanced Examples
- **`lowstate/lowstate.py`** - Comprehensive robot state monitoring
- **`robot_odometry/robot_odometry.py`** - Robot position and orientation tracking
- **`robot_odometry/simple_robot_odometry.py`** - Simple odometry data display
- **`sportmode/sportmode.py`** - Sport mode commands and acrobatics
- **`vui/vui.py`** - LED control and volume management
- **`lidar/lidar_stream.py`** - Basic LiDAR data streaming

## Audio Examples

### Audio Playback
- **`audio/mp3_player/webrtc_audio_player.py`** - Audio file upload and playback
- **`audio/live_audio/live_recv_audio.py`** - Real-time audio reception
- **`audio/save_audio/save_audio_to_file.py`** - Audio recording to file
- **`audio/internet_radio/stream_radio.py`** - Internet radio streaming

## Video Examples

### Video Streaming
- **`video/camera_stream/display_video_channel.py`** - Real-time video display

## Usage

Each example can be run directly:

```bash
# Basic handstand example
python examples/data_channel/simple_handstand_example.py

# Audio playback
python examples/audio/mp3_player/webrtc_audio_player.py

# Video streaming
python examples/video/camera_stream/display_video_channel.py
```

## Requirements

- Go2 robot with WebRTC enabled
- Python 3.8+
- Required dependencies (see pyproject.toml)

## Notes

- Examples use Go2RobotHelper for simplified connection management
- All examples include proper error handling and cleanup
- Examples are designed to be minimal and focused on core functionality 