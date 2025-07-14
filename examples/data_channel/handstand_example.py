"""
Go2 Robot Handstand Example (Updated with Go2RobotHelper)
========================================================

This example demonstrates how to make the Unitree Go2 robot perform a handstand
for 10 seconds using the simplified Go2RobotHelper interface.

UPDATED: This example has been converted to use Go2RobotHelper, reducing
code from ~180 lines to ~30 lines while adding firmware 1.1.7 compatibility.

The helper automatically handles:
- Connection management and cleanup
- Mode switching with firmware 1.1.7 compatibility (sit-before-switch)
- State monitoring and display
- Exception handling and emergency cleanup
- Proper resource management

Requirements:
- Robot must be in a stable position before starting
- Sufficient space around the robot for the handstand maneuver
- Robot should be on a flat, stable surface

Usage:
    python handstand_example.py

Safety Notes:
- Ensure the robot has enough space to perform the handstand
- Monitor the robot during the maneuver
- Be prepared to stop the program if needed (Ctrl+C)
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper


async def handstand_demo(robot: Go2RobotHelper):
    """
    Demonstrate handstand functionality using the robot helper
    
    This contains only the core handstand logic - all boilerplate
    is handled automatically by Go2RobotHelper.
    """
    print("=== Go2 Robot Handstand Example ===")
    print("🤸 Starting handstand demonstration...")
    
    # The helper automatically handles:
    # - Connection to robot
    # - State monitoring setup
    # - Mode switching with firmware 1.1.7 compatibility
    # - Emergency cleanup on interruption
    
    # Perform the complete handstand sequence
    success = await robot.handstand_sequence(duration=10.0)
    
    if success:
        print("🎉 Handstand demonstration completed successfully!")
        print("The robot performed a 10-second handstand and returned to standing position.")
    else:
        print("❌ Handstand demonstration failed")
        print("Check if the robot has sufficient space and is in good condition.")


if __name__ == "__main__":
    """
    Main entry point - all connection management and error handling
    is handled automatically by the helper
    """
    print("Starting Go2 Robot Handstand Example...")
    print("This will demonstrate the robot's handstand capability")
    print("Press Ctrl+C to stop the program at any time")
    print("=" * 50)
    
    async def main():
        # Context manager handles all connection setup, state monitoring, and cleanup
        async with Go2RobotHelper() as robot:
            await handstand_demo(robot)
    
    # Run with automatic error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}") 