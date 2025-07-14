# Go2 Robot Handstand Example

This example demonstrates how to make the Unitree Go2 robot perform a handstand for 10 seconds using the WebRTC driver.

## Overview

The handstand example showcases the robot's acrobatic capabilities by:
1. Connecting to the robot via WebRTC
2. Switching to AI mode (required for advanced maneuvers)
3. Performing a handstand for exactly 10 seconds
4. Returning to normal standing position
5. Switching back to normal mode

## Safety Requirements

⚠️ **Important Safety Notes:**
- Ensure the robot has **sufficient space** around it (at least 2 meters in all directions)
- Place the robot on a **flat, stable surface** with good traction
- **Monitor the robot** during the entire maneuver
- Be prepared to **stop the program** (Ctrl+C) if needed
- Ensure the robot is **fully charged** before attempting acrobatic moves

## Prerequisites

1. Go2 robot is powered on and connected to your network
2. Python environment with the go2_webrtc_driver installed
3. Robot should be in a stable standing position before starting

## Usage

### Basic Usage

```bash
# Navigate to the examples directory
cd examples/data_channel

# Run the handstand example
python handstand_example.py
```

### Connection Methods

The example uses `LocalSTA` mode by default. You can modify the connection method in the script:

```python
# Local Station mode (default) - connect via local network
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)

# Local Access Point mode - direct connection to robot's hotspot
# conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

# Remote mode - connection via Unitree cloud servers
# conn = Go2WebRTCConnection(WebRTCConnectionMethod.Remote, 
#                           serialNumber="YOUR_SERIAL", 
#                           username="your_email", 
#                           password="your_password")
```

### Setting Robot IP (LocalSTA mode)

If using LocalSTA mode, you can specify the robot's IP address:

```bash
# Set IP as environment variable
export ROBOT_IP="192.168.8.181"
python handstand_example.py

# Or find the robot using the built-in scanner
go2-scanner
```

## Example Output

```
Starting Go2 Robot Handstand Example...
Press Ctrl+C to stop the program at any time
==================================================
=== Go2 Robot Handstand Example ===
Initializing connection...
Connecting to robot...
✓ Connected to robot successfully!

Step 1: Checking current motion mode...
Current motion mode: normal

Step 2: Switching motion mode from 'normal' to 'ai'...
Waiting for mode switch to complete...
✓ Mode switch completed

Step 3: Ensuring robot is in proper standing position...
Waiting for robot to stand up...
✓ Robot is standing

Step 4: Performing handstand...
🤸 Robot is now attempting handstand!

⏰ Holding handstand for 10 seconds...
   10 seconds remaining...
   9 seconds remaining...
   8 seconds remaining...
   7 seconds remaining...
   6 seconds remaining...
   5 seconds remaining...
   4 seconds remaining...
   3 seconds remaining...
   2 seconds remaining...
   1 seconds remaining...
✓ Handstand completed!

Step 5: Returning to normal standing position...
Waiting for robot to return to standing position...
✓ Robot has returned to standing position

Step 6: Switching back to normal mode...
✓ Switched back to normal mode

🎉 Handstand demonstration completed successfully!
The robot has performed a handstand for 10 seconds and returned to normal position.
✓ WebRTC connection closed successfully
```

## Code Structure

The example follows these main steps:

1. **Connection Setup**: Establishes WebRTC connection to the robot
2. **Mode Switching**: Changes from normal to AI mode for advanced maneuvers
3. **Safety Positioning**: Ensures robot is in proper standing position
4. **Handstand Execution**: Performs the handstand using `SPORT_CMD["Handstand"]`
5. **Duration Control**: Holds the position for exactly 10 seconds
6. **Recovery**: Returns to normal standing position
7. **Mode Reset**: Switches back to normal mode
8. **Cleanup**: Properly closes the WebRTC connection

## Troubleshooting

### Robot doesn't perform handstand
- Ensure the robot is in AI mode (the script handles this automatically)
- Check that the robot has enough space and is on a stable surface
- Verify the robot is fully charged and in good condition

### Connection issues
- Check robot IP address and network connectivity
- Verify robot is powered on and WebRTC service is running
- Try using the `go2-scanner` tool to find the robot

### Program interruption
- The script includes emergency handling to return the robot to standing position
- Use Ctrl+C to stop the program safely at any time

### Motion mode issues
- The script automatically switches between normal and AI modes
- If issues persist, manually restart the robot and try again

## Related Examples

- `examples/data_channel/sportmode/sportmode.py` - General sport mode commands
- `examples/data_channel/sportmodestate/sportmodestate.py` - Monitor robot state
- Other acrobatic examples in the sport mode folder

## Technical Details

### Sport Commands Used
- `SPORT_CMD["Handstand"]` (1301) - Executes handstand maneuver
- `SPORT_CMD["StandUp"]` (1004) - Returns to standing position

### Topics Used
- `RTC_TOPIC["MOTION_SWITCHER"]` - Switch between normal/AI modes
- `RTC_TOPIC["SPORT_MOD"]` - Send sport mode commands

### API Calls
- `api_id: 1001` - Get current motion mode
- `api_id: 1002` - Set motion mode

## Notes

- The handstand duration is precisely controlled using a countdown timer
- The robot must be in AI mode to perform advanced acrobatic maneuvers
- Safety checks and emergency handling are built into the example
- The script automatically handles mode switching and cleanup 