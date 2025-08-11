# Go2 WebRTC Examples

This directory contains essential examples for using the Go2 WebRTC driver.

It is based on the code from `https://github.com/legion1581/go2_webrtc_connect` and adds:

- More/improved examples
- Small apps

## All examples

| Example | Description |
| --- | --- |
| `audio/internet_radio/stream_radio.py` | Stream internet radio to the robot over WebRTC. |
| `audio/live_audio/live_recv_audio.py` | Play robot audio live through host speakers. |
| `audio/mp3_player/webrtc_audio_player.py` | Upload and play an audio file on the robot. |
| `audio/save_audio/save_audio_to_file.py` | Record robot audio to a WAV file. |
| `data_channel/handstand.py` | Perform a handstand demonstration using the helper. |
| `data_channel/lidar/lidar_performance_test.py` | Measure LIDAR decoding performance (libvoxel/native). |
| `data_channel/lidar/lidar_stream.py` | Basic subscription to LIDAR voxel map; prints decoded data. |
| `data_channel/lidar/plot_lidar_stream.py` | Web-based LIDAR visualization via Flask/Socket.IO/Three.js; CSV replay. |
| `data_channel/lidar/rerun_lidar_stream.py` | LIDAR visualization with Rerun; supports CSV read/write and accumulation. |
| `data_channel/lowstate/lowstate.py` | Comprehensive low-level state monitoring with formatted tables. |
| `data_channel/move_demo.py` | Simple movement demo (forward/back/left/right). |
| `data_channel/move_test.py` | Minimal Move command tester; single move or sequence; restores defaults. |
| `data_channel/robot_odometry/robot_odometry.py` | Display robot odometry: pose and velocities. |
| `data_channel/show_gestures.py` | Demonstrate gestures (Hello, FingerHeart, Stretch). |
| `data_channel/sit_down.py` | Make the robot sit using the Sit command. |
| `data_channel/sportmode/sportmode.py` | Sport mode demo: normal/AI modes, movement, gestures. |
| `data_channel/sportmodestate/sportmodestate.py` | Monitor sport mode state values in real time. |
| `data_channel/stand_down.py` | Lay the robot down using StandDown. |
| `data_channel/stand_up.py` | Stand the robot up using StandUp. |
| `data_channel/vui/vui.py` | Control LED brightness, color, and flashing via VUI APIs. |
| `rerun_video_lidar_stream.py` | Combined video + LIDAR visualization with Rerun; CSV read/write; accumulation. |
| `video/camera_stream/display_video_channel.py` | Display live video frames with OpenCV. |

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
