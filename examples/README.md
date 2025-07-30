# Go2 WebRTC Examples

This directory contains essential examples for using the Go2 WebRTC driver.

## Data Channel Examples

### Basic Examples
- **`show_gestures.py`** - Show different gestures

### Advanced Examples
- **`lowstate/lowstate.py`** - Comprehensive robot state monitoring
- **`robot_odometry/robot_odometry.py`** - Robot position and orientation tracking
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
(be sure to set the ROBOT_IP environment variable first)

```bash
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