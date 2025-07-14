"""
Go2 Robot Handstand Example (Fixed Version) - Updated with Go2RobotHelper
=========================================================================

This example demonstrates the "fixed" handstand approach using StandOut command
with data parameter, now simplified with Go2RobotHelper.

UPDATED: Converted to use Go2RobotHelper, reducing code from ~300 lines to ~50 lines
while maintaining all state monitoring capabilities and adding firmware 1.1.7 compatibility.

The helper automatically handles:
- Connection management and cleanup
- Mode switching with firmware 1.1.7 compatibility (sit-before-switch)
- State monitoring and display (with detailed state option)
- Exception handling and emergency cleanup
- Proper resource management

This version uses:
- StandOut command with {"data": True} for handstand
- StandOut command with {"data": False} to exit handstand
- Real-time state monitoring during handstand

Requirements:
- Robot must be in a stable position before starting
- Sufficient space around the robot for the handstand maneuver
- Robot should be on a flat, stable surface

Usage:
    python handstand_example_fixed.py
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper


async def handstand_fixed_demo(robot: Go2RobotHelper):
    """
    Demonstrate the "fixed" handstand approach with detailed state monitoring
    
    This uses the StandOut command approach with real-time state monitoring
    to show what's happening during the handstand attempt.
    """
    print("=== Go2 Robot Handstand Example (Fixed Version) ===")
    print("Using StandOut command with data parameter")
    print("🤸 Starting handstand demonstration with state monitoring...")
    
    # Get the state monitor for custom monitoring
    state_monitor = robot.get_state_monitor()
    
    # Add custom callback to detect handstand position
    handstand_detected = False
    
    def check_handstand_position(state):
        nonlocal handstand_detected
        imu_state = state.get('imu_state', {})
        if imu_state:
            rpy = imu_state.get('rpy', [0, 0, 0])
            # Check if robot is inverted (rough check for handstand)
            if abs(rpy[0]) > 2.5 or abs(rpy[1]) > 2.5:  # Roughly inverted
                if not handstand_detected:
                    print("\n🎉 Robot appears to be in handstand position!")
                    handstand_detected = True
            else:
                if handstand_detected:
                    print("\n🤔 Robot no longer in handstand position")
                    handstand_detected = False
    
    robot.add_state_callback(check_handstand_position)
    
    # Ensure robot is in AI mode (required for StandOut command)
    print("\n🔄 Ensuring robot is in AI mode...")
    await robot.ensure_mode("sport")
    
    # Stand up first
    print("\n🦿 Ensuring robot is standing...")
    await robot.execute_command("StandUp", wait_time=3)
    
    # Show current state
    print("\n📊 Current robot state before handstand:")
    if state_monitor.latest_state:
        current_mode = state_monitor.latest_state.get('mode', 'unknown')
        current_progress = state_monitor.latest_state.get('progress', 'unknown')
        print(f"Mode: {current_mode}, Progress: {current_progress}")
    
    # Perform handstand using StandOut command
    print("\n🤸 Performing handstand using StandOut command...")
    print("Sending StandOut command with data=True...")
    
    await robot.execute_command("StandOut", {"data": True}, wait_time=0)
    
    # Monitor state during handstand attempt
    print("📊 Monitoring robot state during handstand attempt...")
    for i in range(15):  # Monitor for 15 seconds
        print(f"\n--- Monitoring second {i+1}/15 ---")
        await asyncio.sleep(1)
        
        if state_monitor.latest_state:
            current_mode = state_monitor.latest_state.get('mode', 'unknown')
            current_progress = state_monitor.latest_state.get('progress', 'unknown')
            print(f"State: Mode={current_mode}, Progress={current_progress}")
            
            # Show IMU data
            imu_state = state_monitor.latest_state.get('imu_state', {})
            if imu_state:
                rpy = imu_state.get('rpy', [0, 0, 0])
                print(f"IMU: Roll={rpy[0]:.3f}, Pitch={rpy[1]:.3f}, Yaw={rpy[2]:.3f}")
    
    # Turn off handstand mode
    print("\n🤸 Turning off handstand mode...")
    await robot.execute_command("StandOut", {"data": False}, wait_time=3)
    
    # Return to standing position
    print("\n🦿 Returning to standing position...")
    await robot.execute_command("StandUp", wait_time=3)
    
    # Show final state
    if state_monitor.latest_state:
        final_mode = state_monitor.latest_state.get('mode', 'unknown')
        final_progress = state_monitor.latest_state.get('progress', 'unknown')
        print(f"\n📊 Final state: Mode={final_mode}, Progress={final_progress}")
    
    print("\n🎉 Handstand demonstration completed!")
    print("The robot used StandOut command with data=True/False for handstand control.")


if __name__ == "__main__":
    """
    Main entry point with automatic error handling
    """
    print("Starting Go2 Robot Handstand Example (Fixed Version)...")
    print("This version uses StandOut command with state monitoring")
    print("Press Ctrl+C to stop the program at any time")
    print("=" * 60)
    
    async def main():
        # Use detailed state display for this example
        async with Go2RobotHelper(detailed_state_display=False) as robot:
            await handstand_fixed_demo(robot)
    
    # Run with automatic error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

 