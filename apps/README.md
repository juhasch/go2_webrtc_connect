# Small Apps for the Go2

## gesture

Control the Go2 using simple hand gestures captured from your webcam. The app uses MediaPipe to track hands and translates motion into robot commands over WebRTC via `Go2RobotHelper`. It supports a simulation mode (no robot) and an option to require two-hand up/down to reduce false triggers.

- Supported motions → actions:
  - push hand forward → move back (robot away from you)
  - pull hand backward → move forward (robot toward you)
  - push hand down → StandDown
  - push hand up → StandUp
  - swipe left/right → side step left/right

Script: `apps/gesture/hand_gestures.py`

## Controlling the robot using a Gamepad

Drive the Go2 with a USB/Bluetooth gamepad. Joystick axes provide continuous motion (x: forward/back, y: sidestep, z: yaw). Buttons and the D‑pad trigger discrete actions. Behavior is configurable via `apps/gamepad/gamepad_mapping.yaml` and validated with the schema in `apps/gamepad/gamepad_config.py`. Includes an optional obstacle-avoidance toggle and a visualizer to discover your controller’s indices.

Script: `apps/gamepad_control.py`

When you don't know the papping, use `apps/gamepad/gamepad_visualizer.py` to visualize the gampedad control mapings.

# Combined Video and LIDAR Visualization with Rerun

This application combines real-time video streaming and LIDAR point cloud visualization using Rerun.


## Features

- **Real-time Video Stream**: Displays live camera feed from Go2 robot in Rerun
- **Real-time LIDAR Visualization**: Shows 3D point clouds colored by height
- **CSV Support**: Can read from previously recorded CSV files or save new data
- **Flexible Filtering**: Y-value filtering for LIDAR points
- **Modular Design**: Can disable video or LIDAR streams independently

## Requirements

```bash
pip install rerun-sdk numpy opencv-python asyncio
```

## Usage

### Basic Real-time Streaming
```bash
python examples/rerun_video_lidar_stream.py
```

### Save LIDAR Data to CSV
```bash
python examples/rerun_video_lidar_stream.py --csv-write
```

### Read from Previously Saved CSV
```bash
python examples/rerun_video_lidar_stream.py --csv-read lidar_data_20250130_123456.csv
```

### Filter LIDAR Points by Y-value
```bash
python examples/rerun_video_lidar_stream.py --minYValue 10 --maxYValue 50
```

### Skip LIDAR Messages (Performance)
```bash
python examples/rerun_video_lidar_stream.py --skip-mod 5  # Process every 5th message
```

### Disable Video or LIDAR
```bash
# LIDAR only
python examples/rerun_video_lidar_stream.py --disable-video

# Video only  
python examples/rerun_video_lidar_stream.py --disable-lidar
```

## Command Line Arguments

- `--csv-read <file>`: Read LIDAR data from CSV file instead of live WebRTC
- `--csv-write`: Save LIDAR data to timestamped CSV file
- `--skip-mod <n>`: Process every nth LIDAR message (default: 1, no skipping)
- `--minYValue <n>`: Minimum Y value for LIDAR filtering (default: 0)
- `--maxYValue <n>`: Maximum Y value for LIDAR filtering (default: 100)
- `--disable-video`: Disable video stream
- `--disable-lidar`: Disable LIDAR stream
- `--version`: Show version information

## Rerun Visualization

The application creates two main visualization streams in Rerun:

1. **`camera/image`**: Real-time video feed from the robot's camera
2. **`lidar/points`**: 3D point cloud data colored by height (red=high, blue=low)

## Controls

- **Ctrl+C**: Exit the application gracefully
- **Rerun Viewer**: Use standard Rerun controls to navigate the 3D scene, adjust camera views, etc.

## Performance Tips

- Use `--skip-mod` to reduce LIDAR processing load
- Use `--disable-video` or `--disable-lidar` if you only need one stream
- Adjust Y-value filtering to focus on relevant areas
- CSV mode is useful for debugging and offline analysis

## Example Workflows

### Recording a Session
```bash
# Record LIDAR data while viewing both streams
python examples/rerun_video_lidar_stream.py --csv-write
```

### Analyzing Recorded Data
```bash
# Review recorded data with filtering
python examples/rerun_video_lidar_stream.py --csv-read lidar_data_20250130_123456.csv --minYValue 20 --maxYValue 80
```

### Performance Testing
```bash
# High-performance mode with reduced LIDAR processing
python examples/rerun_video_lidar_stream.py --skip-mod 10 --minYValue 30 --maxYValue 70
```

## Architecture

The application uses:
- **Threading**: Separates main thread from asyncio event loop
- **Asyncio**: Handles WebRTC connections and data streaming
- **Rerun**: Provides 3D visualization and video display
- **Queue-based Communication**: Manages data flow between threads
- **Graceful Shutdown**: Ensures proper cleanup on exit 
