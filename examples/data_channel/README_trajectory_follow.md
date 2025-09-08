# Go2 Robot Trajectory Follow Examples

This directory contains Python examples demonstrating how to use the `TrajectoryFollow` command in sports mode with the Go2 robot.

## Overview

The `TrajectoryFollow` command allows the robot to follow a predefined trajectory path in sports mode. This is useful for:
- Autonomous navigation along specific paths
- Demonstrating complex movement patterns
- Testing robot locomotion capabilities
- Creating choreographed movements

## Examples

### 1. Simple Trajectory Follow (`trajectory_follow_simple.py`)

A basic example showing the essential steps for using `TrajectoryFollow`:

```bash
python examples/data_channel/trajectory_follow_simple.py
```

**Features:**
- Minimal code for quick understanding
- Basic square trajectory
- Proper sports mode sequence
- Error handling

### 2. Advanced Trajectory Follow (`trajectory_follow_advanced.py`)

A comprehensive example with multiple trajectory shapes and configurations:

```bash
# Square trajectory
python examples/data_channel/trajectory_follow_advanced.py --shape square

# Circular trajectory with custom scale
python examples/data_channel/trajectory_follow_advanced.py --shape circle --scale 0.5

# Figure-8 trajectory with custom duration
python examples/data_channel/trajectory_follow_advanced.py --shape figure8 --duration 15.0
```

**Features:**
- Multiple trajectory shapes (square, circle, figure-8, line)
- Configurable scale and duration
- Advanced error handling
- Status monitoring

### 3. Full-Featured Trajectory Follow (`trajectory_follow.py`)

A complete example with extensive trajectory generation capabilities:

```bash
# Default square trajectory
python examples/data_channel/trajectory_follow.py

# Circular trajectory
python examples/data_channel/trajectory_follow.py --shape circle

# Figure-8 trajectory
python examples/data_channel/trajectory_follow.py --shape figure8
```

**Features:**
- Multiple trajectory generation algorithms
- Configurable parameters
- Comprehensive error handling
- Detailed logging and monitoring

## Sports Mode Sequence

All examples follow the proper sports mode sequence as required by the Go2 robot:

1. **Normal Mode**: Ensure robot is in normal mode and standing
2. **Stand Down**: Lower the robot before switching to sports mode
3. **Sports Mode**: Switch to sports mode
4. **Stand Up**: Stand up in sports mode
5. **Trajectory Follow**: Execute the trajectory
6. **Cleanup**: Stop movement and ensure robot is standing

## Trajectory Data Structure

The `TrajectoryFollow` command expects trajectory data in the following format:

```python
trajectory_data = {
    "trajectory": [
        {"x": 0.0, "y": 0.0, "z": 0.0, "time": 0.0},
        {"x": 0.5, "y": 0.0, "z": 0.0, "time": 2.0},
        {"x": 0.5, "y": 0.3, "z": 0.0, "time": 4.0},
        # ... more points
    ],
    "duration": 8.0,
    "loop": False,
    "interpolation": "linear"
}
```

**Parameters:**
- `trajectory`: List of waypoints with x, y, z coordinates and time
- `duration`: Total trajectory duration in seconds
- `loop`: Whether to loop the trajectory (boolean)
- `interpolation`: Interpolation method between points

## Usage Examples

### Basic Usage

```bash
# Run with default settings
python examples/data_channel/trajectory_follow_simple.py

# Run with specific robot IP
python examples/data_channel/trajectory_follow_simple.py --ip 192.168.8.181
```

### Advanced Usage

```bash
# Square trajectory with custom scale
python examples/data_channel/trajectory_follow_advanced.py --shape square --scale 1.5

# Circular trajectory with custom duration
python examples/data_channel/trajectory_follow_advanced.py --shape circle --duration 20.0

# Figure-8 trajectory with small scale
python examples/data_channel/trajectory_follow_advanced.py --shape figure8 --scale 0.3
```

### Connection Methods

```bash
# Local AP mode (default)
python examples/data_channel/trajectory_follow_simple.py --method ap

# Local STA mode with IP
python examples/data_channel/trajectory_follow_simple.py --method sta --ip 192.168.8.181

# Remote mode with credentials
python examples/data_channel/trajectory_follow_simple.py --method remote --serial YOUR_SERIAL --username YOUR_USERNAME --password YOUR_PASSWORD
```

## Requirements

- Go2 robot in sports mode
- Network connection to robot
- Python 3.8+
- go2_webrtc_connect package

## Safety Notes

⚠️ **Important Safety Considerations:**

1. **Clear Space**: Ensure the robot has enough clear space to execute the trajectory
2. **Sports Mode**: The robot must be in sports mode for `TrajectoryFollow` to work
3. **Supervision**: Always supervise the robot during trajectory execution
4. **Emergency Stop**: Be ready to stop the robot if needed
5. **Firmware**: Ensure robot firmware supports `TrajectoryFollow` command

## Troubleshooting

### Common Issues

1. **Command Not Recognized**: Ensure robot is in sports mode
2. **Trajectory Not Executed**: Check trajectory data format and parameters
3. **Connection Issues**: Verify network connection and robot IP
4. **Firmware Compatibility**: Check if `TrajectoryFollow` is supported

### Debug Mode

Enable debug logging to see detailed command execution:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## References

- [Unitree Sports Services Documentation](https://support.unitree.com/home/en/developer/sports_services)
- [Go2 WebRTC Driver Documentation](../README.md)
- [Unitree SDK2 Python Examples](https://github.com/unitreerobotics/unitree_sdk2_python)

## Contributing

When adding new trajectory shapes or features:

1. Follow the existing code structure
2. Include proper error handling
3. Add command-line arguments for configuration
4. Update this README with new features
5. Test with different robot configurations
