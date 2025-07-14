# Go2RobotHelper - Simplified Robot Control

The `Go2RobotHelper` class dramatically reduces boilerplate code in Go2 robot examples by providing a high-level interface that handles all common patterns automatically.

## ✨ Key Benefits

- **85% reduction in boilerplate code**
- **Automatic connection management** with context manager support
- **Firmware 1.1.7 compatibility** built-in (including the required sit-before-mode-switch)
- **Automatic state monitoring** with real-time display
- **Emergency cleanup** and safe robot positioning
- **Consistent error handling** across all examples
- **Simplified command execution** with parameter handling

## 📊 Before/After Comparison

| Feature | Original Examples | With Go2RobotHelper |
|---------|------------------|-------------------|
| **Lines of code** | 100-200+ lines | 15-30 lines |
| **Connection management** | Manual setup/cleanup | Automatic |
| **Mode switching** | Manual implementation | Built-in with firmware compatibility |
| **State monitoring** | Manual callback setup | Automatic |
| **Exception handling** | Repetitive try/except blocks | Automatic |
| **Emergency cleanup** | Manual implementation | Automatic |
| **Firmware compatibility** | Manual sit-before-switch | Built-in |

## 🚀 Quick Start

### Basic Usage

```python
import asyncio
from go2_webrtc_driver import Go2RobotHelper

async def main():
    async with Go2RobotHelper() as robot:
        await robot.execute_command("Hello")
        await robot.execute_command("FingerHeart", wait_time=5)

asyncio.run(main())
```

### Using the Factory Function

```python
from go2_webrtc_driver import create_example_main

async def robot_demo(robot):
    await robot.ensure_mode("ai")
    await robot.execute_command("Dance1", wait_time=6)
    await robot.handstand_sequence(duration=10.0)

# Factory function handles all boilerplate
main = create_example_main(robot_demo)
asyncio.run(main())
```

## 📚 Complete API Reference

### Go2RobotHelper Class

#### Constructor

```python
Go2RobotHelper(
    connection_method: WebRTCConnectionMethod = WebRTCConnectionMethod.LocalSTA,
    serial_number: Optional[str] = None,
    ip: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    enable_state_monitoring: bool = True,
    detailed_state_display: bool = False,
    logging_level: int = logging.WARNING
)
```

#### Core Methods

##### `ensure_mode(target_mode, sit_before_switch=True)`
Ensure robot is in the specified mode with firmware 1.1.7 compatibility.

```python
# Switch to AI mode (includes automatic sit-before-switch)
await robot.ensure_mode("ai")

# Switch to normal mode
await robot.ensure_mode("normal")

# Use enum for type safety
from go2_webrtc_driver import RobotMode
await robot.ensure_mode(RobotMode.AI)
```

##### `execute_command(command, parameter=None, wait_time=2.0)`
Execute a sport command with automatic parameter handling.

```python
# Basic commands
await robot.execute_command("Hello")
await robot.execute_command("StandUp")
await robot.execute_command("Sit")

# Commands with parameters
await robot.execute_command("Move", {"x": 0.5, "y": 0, "z": 0})
await robot.execute_command("StandOut", {"data": True})

# Custom wait time
await robot.execute_command("Dance1", wait_time=6)
```

##### `handstand_sequence(duration=10.0)`
Perform a complete handstand sequence with automatic mode switching.

```python
# Perform handstand for 10 seconds
success = await robot.handstand_sequence(duration=10.0)

if success:
    print("Handstand completed successfully!")
else:
    print("Handstand failed")
```

#### State Monitoring

```python
# Get state monitor
monitor = robot.get_state_monitor()

# Add custom callback
def my_callback(state):
    print(f"Custom state: {state}")

robot.add_state_callback(my_callback)

# Enable detailed state display
robot = Go2RobotHelper(detailed_state_display=True)
```

### Convenience Functions

#### `create_example_main(robot_operations)`
Factory function that creates a standardized main function.

```python
async def my_robot_demo(robot):
    await robot.execute_command("Hello")
    await robot.handstand_sequence()

# Automatically handles connection, exceptions, cleanup
main = create_example_main(my_robot_demo)
asyncio.run(main())
```

#### `simple_robot_connection(connection_method)`
Simple context manager for quick connections.

```python
async with simple_robot_connection() as robot:
    await robot.execute_command("Hello")
```

## 🔄 Migration Guide

### Step 1: Update Imports

**Before:**
```python
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
```

**After:**
```python
from go2_webrtc_driver import Go2RobotHelper
# or
from go2_webrtc_driver import Go2RobotHelper, create_example_main
```

### Step 2: Replace Connection Management

**Before:**
```python
conn = None
try:
    conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
    await conn.connect()
    
    # ... robot operations ...
    
except KeyboardInterrupt:
    print("Program interrupted")
    # Manual emergency cleanup
except Exception as e:
    print(f"Error: {e}")
    # Manual emergency cleanup
finally:
    if conn:
        await conn.disconnect()
```

**After:**
```python
async with Go2RobotHelper() as robot:
    # ... robot operations ...
```

### Step 3: Replace Mode Switching

**Before:**
```python
# Check current mode
response = await conn.datachannel.pub_sub.publish_request_new(
    RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1001}
)
current_mode = json.loads(response['data']['data'])['name']

# Switch to AI mode
if current_mode != "ai":
    # Manual sit command (firmware 1.1.7 requirement)
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD["Sit"]}
    )
    await asyncio.sleep(3)
    
    # Switch mode
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["MOTION_SWITCHER"], 
        {"api_id": 1002, "parameter": {"name": "ai"}}
    )
    await asyncio.sleep(5)
```

**After:**
```python
await robot.ensure_mode("ai")
```

### Step 4: Replace Command Execution

**Before:**
```python
await conn.datachannel.pub_sub.publish_request_new(
    RTC_TOPIC["SPORT_MOD"], 
    {"api_id": SPORT_CMD["Hello"]}
)
await asyncio.sleep(2)

await conn.datachannel.pub_sub.publish_request_new(
    RTC_TOPIC["SPORT_MOD"], 
    {
        "api_id": SPORT_CMD["StandOut"],
        "parameter": {"data": True}
    }
)
```

**After:**
```python
await robot.execute_command("Hello")
await robot.execute_command("StandOut", {"data": True})
```

### Step 5: Replace State Monitoring

**Before:**
```python
def sportmodestatus_callback(message):
    current_message = message['data']
    # Manual state processing
    
conn.datachannel.pub_sub.subscribe(
    RTC_TOPIC['LF_SPORT_MOD_STATE'], 
    sportmodestatus_callback
)
```

**After:**
```python
# Automatic state monitoring is enabled by default
# Add custom callbacks if needed
def my_callback(state):
    print(f"Custom processing: {state}")
    
robot.add_state_callback(my_callback)
```

## 📝 Example Code Transformations

### Example 1: Basic Sport Commands

**Before (50+ lines):**
```python
import asyncio
import logging
import json
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD

logging.basicConfig(level=logging.WARNING)

async def main():
    conn = None
    try:
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        await conn.connect()
        
        # ... mode switching logic ...
        # ... command execution ...
        # ... state monitoring setup ...
        
    except KeyboardInterrupt:
        print("Program interrupted")
        # ... emergency cleanup ...
    except Exception as e:
        print(f"Error: {e}")
        # ... emergency cleanup ...
    finally:
        if conn:
            await conn.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

**After (15 lines):**
```python
import asyncio
from go2_webrtc_driver import Go2RobotHelper

async def main():
    async with Go2RobotHelper() as robot:
        await robot.ensure_mode("normal")
        await robot.execute_command("Hello")
        await robot.execute_command("FingerHeart", wait_time=5)

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 2: Using Factory Function

**After (10 lines):**
```python
from go2_webrtc_driver import create_example_main

async def robot_demo(robot):
    await robot.ensure_mode("ai")
    await robot.execute_command("Dance1", wait_time=6)
    success = await robot.handstand_sequence(10.0)
    print(f"Handstand success: {success}")

main = create_example_main(robot_demo)
asyncio.run(main())
```

## 🔧 Advanced Configuration

### Custom Connection Methods

```python
# Local Access Point mode
robot = Go2RobotHelper(WebRTCConnectionMethod.LocalAP)

# Remote connection
robot = Go2RobotHelper(
    WebRTCConnectionMethod.Remote,
    serial_number="B12345678",
    username="your_email@example.com",
    password="your_password"
)

# Custom IP for LocalSTA
robot = Go2RobotHelper(
    WebRTCConnectionMethod.LocalSTA,
    ip="192.168.1.100"
)
```

### State Monitoring Options

```python
# Disable state monitoring
robot = Go2RobotHelper(enable_state_monitoring=False)

# Enable detailed state display
robot = Go2RobotHelper(detailed_state_display=True)

# Custom logging level
robot = Go2RobotHelper(logging_level=logging.DEBUG)
```

### Custom State Callbacks

```python
async def main():
    async with Go2RobotHelper() as robot:
        # Add custom state processing
        def check_handstand_position(state):
            imu = state.get('imu_state', {})
            rpy = imu.get('rpy', [0, 0, 0])
            if abs(rpy[0]) > 2.5:  # Inverted
                print("🤸 Robot is in handstand position!")
                
        robot.add_state_callback(check_handstand_position)
        
        await robot.handstand_sequence()
```

## 🛠️ Available Commands

The helper supports all sport commands from `SPORT_CMD`:

### Basic Commands
- `Hello` - Greeting gesture
- `StandUp` - Stand up from sitting/lying
- `Sit` - Sit down
- `StandDown` - Lower body position
- `StopMove` - Stop all movement

### Movement Commands
- `Move` - Basic movement (requires parameter: `{"x": 0.5, "y": 0, "z": 0}`)
- `SwitchGait` - Switch gait patterns
- `BodyHeight` - Adjust body height
- `SpeedLevel` - Set speed level

### Gesture Commands
- `Stretch` - Stretching movement
- `FingerHeart` - Heart gesture with legs
- `Hello` - Greeting gesture
- `Wallow` - Wallowing behavior

### Dance Commands
- `Dance1` - Dance routine 1
- `Dance2` - Dance routine 2

### Acrobatic Commands
- `Handstand` - Direct handstand command
- `StandOut` - Stand out behavior (use with `{"data": True/False}`)
- `BackFlip` - Back flip (use with caution!)
- `FrontFlip` - Front flip (use with caution!)

### Example Usage
```python
# Basic commands
await robot.execute_command("Hello")
await robot.execute_command("Sit")

# Commands with parameters
await robot.execute_command("Move", {"x": 0.5, "y": 0, "z": 0})
await robot.execute_command("BodyHeight", {"height": 0.1})

# Commands with custom wait time
await robot.execute_command("Dance1", wait_time=8)
```

## 🚨 Error Handling

The helper provides comprehensive error handling:

### Automatic Emergency Cleanup
- Turns off active special modes (handstand, etc.)
- Sits down before mode switching (firmware 1.1.7 requirement)
- Switches to normal mode
- Stands up in safe position
- Properly closes connection

### Exception Types
- `KeyboardInterrupt` - Handled gracefully with emergency cleanup
- `ConnectionError` - Automatic connection management
- `ValueError` - Invalid commands or parameters
- `TimeoutError` - Request timeouts

### Custom Error Handling
```python
try:
    async with Go2RobotHelper() as robot:
        await robot.execute_command("InvalidCommand")
except ValueError as e:
    print(f"Invalid command: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## 🎯 Best Practices

1. **Always use the context manager** for automatic cleanup
2. **Use `ensure_mode()` before mode-specific commands** for reliability
3. **Add custom state callbacks** for specific monitoring needs
4. **Use appropriate wait times** for commands that need time to complete
5. **Test handstand in a safe area** with sufficient space
6. **Handle exceptions appropriately** for production code

## 📖 Full Examples

See the following example files:
- `simple_handstand_example.py` - Basic handstand with minimal code
- `sport_commands_example.py` - Comprehensive sport command demo
- `simple_heart_gesture_example.py` - Before/after comparison

## 🔗 Related Documentation

- [Go2 WebRTC Driver Documentation](../../../README.md)
- [Sport Mode Commands](../sportmode/)
- [Handstand Examples](../handstand_example*.py)
- [State Monitoring](../sportmodestate/) 