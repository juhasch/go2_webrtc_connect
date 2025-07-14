"""
Go2 Robot Handstand Example with State Monitoring (Debug Version)
================================================================

This debug version includes real-time state monitoring to help understand
what's happening when the handstand command is sent.

This example demonstrates how to make the Unitree Go2 robot perform a handstand
for 10 seconds while monitoring the robot's state in real-time.

IMPORTANT: This version includes the critical "sit down" step before mode switching,
which is required in firmware 1.1.7 to enable proper mode transitions from MCF to AI mode.

Requirements:
- Robot must be in a stable position before starting
- Sufficient space around the robot for the handstand maneuver
- Robot should be on a flat, stable surface
- Firmware 1.1.7 compatibility: Includes sit command before mode switching

Usage:
    python handstand_example_debug.py

The debug version will show:
- Real-time robot state updates
- Mode changes
- Progress information
- IMU data
- Position and velocity data

Steps performed:
1. Check current motion mode
2. Make robot sit down (REQUIRED before mode switch in firmware 1.1.7)
3. Switch to AI mode
4. Stand up
5. Perform handstand
6. Turn off handstand mode
7. Return to standing position
8. Switch back to normal mode
"""

import asyncio
import logging
import json
import sys
import time
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD

# Enable logging for debugging
logging.basicConfig(level=logging.WARNING)

class RobotStateMonitor:
    """Monitor and display robot state information"""
    
    def __init__(self):
        self.latest_state = None
        self.state_count = 0
        self.monitoring_enabled = False
        
    def enable_monitoring(self):
        """Enable state monitoring output"""
        self.monitoring_enabled = True
        
    def disable_monitoring(self):
        """Disable state monitoring output"""
        self.monitoring_enabled = False
        
    def display_compact_state(self, message):
        """Display compact state information"""
        if not self.monitoring_enabled:
            return
            
        try:
            self.state_count += 1
            timestamp = message.get('stamp', 'N/A')
            mode = message.get('mode', 'N/A')
            progress = message.get('progress', 'N/A')
            gait_type = message.get('gait_type', 'N/A')
            body_height = message.get('body_height', 'N/A')
            
            imu_state = message.get('imu_state', {})
            rpy = imu_state.get('rpy', [0, 0, 0])
            
            # Clear line and print compact state
            print(f"\r🤖 State #{self.state_count}: Mode={mode}, Progress={progress}, Gait={gait_type}, Height={body_height:.3f}m, Roll={rpy[0]:.3f}, Pitch={rpy[1]:.3f}, Yaw={rpy[2]:.3f}", end='', flush=True)
            
            self.latest_state = message
            
        except Exception as e:
            print(f"\nError displaying state: {e}")
    
    def display_detailed_state(self, message):
        """Display detailed state information"""
        try:
            print("\n" + "="*60)
            print("🤖 DETAILED ROBOT STATE")
            print("="*60)
            
            timestamp = message.get('stamp', 'N/A')
            mode = message.get('mode', 'N/A')
            progress = message.get('progress', 'N/A')
            gait_type = message.get('gait_type', 'N/A')
            body_height = message.get('body_height', 'N/A')
            position = message.get('position', 'N/A')
            velocity = message.get('velocity', 'N/A')
            
            print(f"Timestamp: {timestamp}")
            print(f"Mode: {mode}")
            print(f"Progress: {progress}")
            print(f"Gait Type: {gait_type}")
            print(f"Body Height: {body_height} m")
            print(f"Position: {position}")
            print(f"Velocity: {velocity}")
            
            imu_state = message.get('imu_state', {})
            if imu_state:
                rpy = imu_state.get('rpy', [0, 0, 0])
                quaternion = imu_state.get('quaternion', [0, 0, 0, 1])
                gyroscope = imu_state.get('gyroscope', [0, 0, 0])
                accelerometer = imu_state.get('accelerometer', [0, 0, 0])
                
                print(f"IMU - Roll: {rpy[0]:.3f}, Pitch: {rpy[1]:.3f}, Yaw: {rpy[2]:.3f}")
                print(f"IMU - Quaternion: {quaternion}")
                print(f"IMU - Gyroscope: {gyroscope}")
                print(f"IMU - Accelerometer: {accelerometer}")
            
            print("="*60)
            
        except Exception as e:
            print(f"\nError displaying detailed state: {e}")

async def main():
    """
    Main function to demonstrate handstand functionality with state monitoring
    """
    conn = None
    state_monitor = RobotStateMonitor()
    
    try:
        print("=== Go2 Robot Handstand Example (Debug Version) ===")
        print("This version includes real-time state monitoring for debugging")
        print("Initializing connection...")
        
        # Choose a connection method
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)

        # Connect to the WebRTC service
        print("Connecting to robot...")
        await conn.connect()
        print("✓ Connected to robot successfully!")

        # Set up state monitoring
        print("Setting up state monitoring...")
        def sportmodestatus_callback(message):
            current_message = message['data']
            state_monitor.display_compact_state(current_message)

        # Subscribe to the sportmode status data
        conn.datachannel.pub_sub.subscribe(RTC_TOPIC['LF_SPORT_MOD_STATE'], sportmodestatus_callback)
        print("✓ State monitoring enabled")
        
        # Wait a moment to get initial state
        print("Getting initial robot state...")
        state_monitor.enable_monitoring()
        await asyncio.sleep(2)
        
        # Display initial detailed state
        if state_monitor.latest_state:
            print("\n")
            state_monitor.display_detailed_state(state_monitor.latest_state)
            initial_mode = state_monitor.latest_state.get('mode', 'unknown')
            print(f"Initial robot mode: {initial_mode}")
        
        # Step 1: Check current motion mode
        print("\nStep 1: Checking current motion mode...")
        response = await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], 
            {"api_id": 1001}
        )

        if response['data']['header']['status']['code'] == 0:
            data = json.loads(response['data']['data'])
            current_motion_switcher_mode = data['name']
            print(f"Current motion mode: {current_motion_switcher_mode}")
        else:
            print("Warning: Could not determine current motion mode")
            current_motion_switcher_mode = "unknown"

        # Step 2: Make robot sit down/lay down (REQUIRED before mode switch)
        print("\nStep 2: Making robot sit down (required before mode switch)...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {"api_id": SPORT_CMD["Sit"]}
        )
        print("Waiting for robot to sit down (monitoring state)...")
        await asyncio.sleep(5)  # Wait for robot to sit down
        print("✓ Robot should now be sitting/laying down")

        # Show current state after sitting
        if state_monitor.latest_state:
            print("\nState after sitting command:")
            state_monitor.display_detailed_state(state_monitor.latest_state)

        # Step 3: Switch to AI mode (required for advanced maneuvers)
        if current_motion_switcher_mode != "ai":
            print(f"\nStep 3: Switching motion mode from '{current_motion_switcher_mode}' to 'ai'...")
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"], 
                {
                    "api_id": 1002,
                    "parameter": {"name": "ai"}
                }
            )
            print("Waiting for mode switch to complete (monitoring state)...")
            await asyncio.sleep(8)  # Wait for mode switch to complete
            print("\n✓ Mode switch completed")
        else:
            print("✓ Already in AI mode")

        # Show current state after mode switch
        if state_monitor.latest_state:
            print("\nState after mode switch:")
            state_monitor.display_detailed_state(state_monitor.latest_state)

        # Step 4: Ensure robot is in standing position
        print("\nStep 4: Ensuring robot is in proper standing position...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {"api_id": SPORT_CMD["StandUp"]}
        )
        print("Waiting for robot to stand up (monitoring state)...")
        await asyncio.sleep(3)
        print("\n✓ Robot should be standing")

        # Show current state after standing
        if state_monitor.latest_state:
            print("\nState after standing command:")
            state_monitor.display_detailed_state(state_monitor.latest_state)

        # Step 5: Perform handstand
        print("\nStep 5: Performing handstand...")
        print("🤸 Sending handstand command and monitoring state...")
        
        # Send handstand command (using StandOut with data=True)
        handstand_response = await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {
                "api_id": SPORT_CMD["StandOut"],
                "parameter": {"data": True}
            }
        )
        
        print(f"Handstand command response: {handstand_response}")
        
        # Monitor state during handstand attempt
        print("Monitoring robot state during handstand attempt...")
        for i in range(15):  # Monitor for 15 seconds
            print(f"\n--- Monitoring second {i+1}/15 ---")
            await asyncio.sleep(1)
            
            if state_monitor.latest_state:
                current_mode = state_monitor.latest_state.get('mode', 'unknown')
                current_progress = state_monitor.latest_state.get('progress', 'unknown')
                print(f"Current mode: {current_mode}, Progress: {current_progress}")
                
                # Check if robot is in handstand position based on IMU
                imu_state = state_monitor.latest_state.get('imu_state', {})
                if imu_state:
                    rpy = imu_state.get('rpy', [0, 0, 0])
                    print(f"IMU Roll: {rpy[0]:.3f}, Pitch: {rpy[1]:.3f}, Yaw: {rpy[2]:.3f}")
                    
                    # Check if robot is inverted (rough check for handstand)
                    if abs(rpy[0]) > 2.5 or abs(rpy[1]) > 2.5:  # Roughly inverted
                        print("🎉 Robot appears to be in handstand position!")
                        break
                    else:
                        print("🤔 Robot does not appear to be in handstand position")

        # Step 6: Turn off handstand mode first
        print("\nStep 6: Turning off handstand mode...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {
                "api_id": SPORT_CMD["StandOut"],
                "parameter": {"data": False}
            }
        )
        
        await asyncio.sleep(3)
        
        # Step 7: Return to normal standing position
        print("\nStep 7: Returning to normal standing position...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {"api_id": SPORT_CMD["StandUp"]}
        )
        
        print("Waiting for robot to return to standing position...")
        await asyncio.sleep(3)
        print("\n✓ Robot should have returned to standing position")

        # Final state check
        if state_monitor.latest_state:
            print("\nFinal robot state:")
            state_monitor.display_detailed_state(state_monitor.latest_state)

        # Step 8: Switch back to normal mode
        print("\nStep 8: Switching back to normal mode...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], 
            {
                "api_id": 1002,
                "parameter": {"name": "normal"}
            }
        )
        await asyncio.sleep(3)
        print("✓ Switched back to normal mode")

        print("\n🎉 Handstand debug demonstration completed!")
        print("Please review the state information above to understand what happened.")

    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
        if conn:
            # Emergency: try to return robot to safe position
            print("Attempting to return robot to safe position...")
            try:
                # First turn off handstand mode
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"], 
                    {
                        "api_id": SPORT_CMD["StandOut"],
                        "parameter": {"data": False}
                    }
                )
                await asyncio.sleep(2)
                # Sit down first (required before mode switch)
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"], 
                    {"api_id": SPORT_CMD["Sit"]}
                )
                await asyncio.sleep(2)
                # Switch back to normal mode
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"], 
                    {
                        "api_id": 1002,
                        "parameter": {"name": "normal"}
                    }
                )
                await asyncio.sleep(2)
                # Then stand up
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"], 
                    {"api_id": SPORT_CMD["StandUp"]}
                )
                await asyncio.sleep(2)
            except:
                pass
    
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        logging.error(f"Error during handstand demonstration: {e}")
        
        if conn:
            # Emergency: try to return robot to safe position
            print("Attempting to return robot to safe position...")
            try:
                # First turn off handstand mode
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"], 
                    {
                        "api_id": SPORT_CMD["StandOut"],
                        "parameter": {"data": False}
                    }
                )
                await asyncio.sleep(2)
                # Sit down first (required before mode switch)
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"], 
                    {"api_id": SPORT_CMD["Sit"]}
                )
                await asyncio.sleep(2)
                # Switch back to normal mode
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"], 
                    {
                        "api_id": 1002,
                        "parameter": {"name": "normal"}
                    }
                )
                await asyncio.sleep(2)
                # Then stand up
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"], 
                    {"api_id": SPORT_CMD["StandUp"]}
                )
                await asyncio.sleep(2)
            except:
                pass
    
    finally:
        # Disable monitoring
        state_monitor.disable_monitoring()
        
        # Ensure proper cleanup of the WebRTC connection
        if conn:
            try:
                await conn.disconnect()
                print("\n✓ WebRTC connection closed successfully")
            except Exception as e:
                logging.error(f"Error closing WebRTC connection: {e}")

if __name__ == "__main__":
    """
    Entry point for the handstand debug demonstration
    """
    print("Starting Go2 Robot Handstand Debug Example...")
    print("This version includes real-time state monitoring")
    print("Press Ctrl+C to stop the program at any time")
    print("=" * 60)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1) 