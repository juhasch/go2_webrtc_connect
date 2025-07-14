"""
Go2 Robot Sport Mode State Monitoring - Updated with Go2RobotHelper
===================================================================

This example demonstrates how to monitor the robot's sport mode state data
using the simplified Go2RobotHelper interface.

UPDATED: Converted to use Go2RobotHelper, reducing boilerplate code while
maintaining all sport mode state monitoring functionality and adding better connection management.

The helper automatically handles:
- Connection management and cleanup
- Exception handling and recovery
- Proper resource management

This example demonstrates:
- Subscribing to sport mode state data
- Real-time monitoring of robot movement state
- Data processing and display

Usage:
    python sportmodestate.py
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import RTC_TOPIC


def display_data(data):
    """
    Process and display sport mode state data from the robot
    
    This function handles the incoming sport mode state messages
    and displays relevant information about the robot's movement state.
    """
    try:
        # Extract key information from sport mode state data
        timestamp = data.get('stamp', 'N/A')
        mode = data.get('mode', 'N/A')
        progress = data.get('progress', 'N/A')
        gait_type = data.get('gait_type', 'N/A')
        body_height = data.get('body_height', 0)
        position = data.get('position', [0, 0, 0])
        velocity = data.get('velocity', [0, 0, 0])
        
        # IMU state
        imu_state = data.get('imu_state', {})
        rpy = imu_state.get('rpy', [0, 0, 0])
        quaternion = imu_state.get('quaternion', [0, 0, 0, 1])
        gyroscope = imu_state.get('gyroscope', [0, 0, 0])
        accelerometer = imu_state.get('accelerometer', [0, 0, 0])
        
        # Foot contact information
        foot_contact = data.get('foot_contact', [0, 0, 0, 0])
        
        # Display formatted data
        print(f"\n🎯 Sport Mode State Data (Timestamp: {timestamp})")
        print("-" * 60)
        
        # Basic State Information
        print(f"🏃 Movement State:")
        print(f"   Mode: {mode}")
        print(f"   Progress: {progress}")
        print(f"   Gait Type: {gait_type}")
        print(f"   Body Height: {body_height:.3f}m")
        
        # Position and Velocity
        print(f"📍 Position: [{position[0]:.3f}, {position[1]:.3f}, {position[2]:.3f}]")
        print(f"🏃 Velocity: [{velocity[0]:.3f}, {velocity[1]:.3f}, {velocity[2]:.3f}]")
        
        # IMU Information
        print(f"🧭 IMU Data:")
        print(f"   RPY:        [{rpy[0]:.3f}, {rpy[1]:.3f}, {rpy[2]:.3f}]")
        print(f"   Quaternion: [{quaternion[0]:.3f}, {quaternion[1]:.3f}, {quaternion[2]:.3f}, {quaternion[3]:.3f}]")
        print(f"   Gyroscope:  [{gyroscope[0]:.3f}, {gyroscope[1]:.3f}, {gyroscope[2]:.3f}]")
        print(f"   Accel:      [{accelerometer[0]:.3f}, {accelerometer[1]:.3f}, {accelerometer[2]:.3f}]")
        
        # Foot Contact
        foot_names = ["FR", "FL", "RR", "RL"]  # Front Right, Front Left, Rear Right, Rear Left
        foot_status = []
        for i, contact in enumerate(foot_contact):
            status = "��" if contact else "🔴"
            foot_status.append(f"{foot_names[i]}:{status}")
        
        print(f"🦶 Foot Contact: {' '.join(foot_status)}")
        
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Error processing sport mode state data: {e}")


async def sportmode_state_monitoring_demo(robot: Go2RobotHelper):
    """
    Demonstrate sport mode state monitoring using the robot helper
    
    This subscribes to the robot's sport mode state data and displays
    real-time movement and sensor information.
    """
    print("=== Go2 Robot Sport Mode State Monitoring ===")
    print("📡 Starting sport mode state data monitoring...")
    print("This will display real-time movement state data from the robot")
    print("Press Ctrl+C to stop")
    
    # Get access to the underlying connection for data subscription
    conn = robot.conn
    
    print(f"\n📊 Setting up sport mode state data subscription...")
    
    # Define callback function to handle sportmode state data when received
    def sportmodestatus_callback(message):
        current_message = message['data']
        display_data(current_message)
    
    # Subscribe to the sport mode state data
    conn.datachannel.pub_sub.subscribe(RTC_TOPIC['LF_SPORT_MOD_STATE'], sportmodestatus_callback)
    print("✅ Subscribed to sport mode state data stream")
    
    print(f"\n🔄 Monitoring sport mode state data...")
    print("Data will appear below as it's received from the robot:")
    
    try:
        # Keep the program running to allow event handling
        # The helper will handle connection management
        await asyncio.sleep(3600)  # Monitor for up to 1 hour
        
    except asyncio.CancelledError:
        print(f"\n🛑 Monitoring cancelled")
        raise
    except Exception as e:
        print(f"\n❌ Error during monitoring: {e}")
        raise
    
    print(f"\n📊 Sport mode state monitoring completed")


if __name__ == "__main__":
    """
    Main entry point with automatic error handling
    """
    print("Starting Go2 Robot Sport Mode State Monitoring...")
    print("This will display real-time sport mode state data from the robot")
    print("Press Ctrl+C to stop the program at any time")
    print("=" * 60)
    
    async def main():
        # Context manager handles all connection setup and cleanup
        # Disable built-in state monitoring since we're doing our own
        async with Go2RobotHelper(enable_state_monitoring=False) as robot:
            await sportmode_state_monitoring_demo(robot)
    
    # Run with automatic error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
        print("Sport mode state monitoring stopped")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
