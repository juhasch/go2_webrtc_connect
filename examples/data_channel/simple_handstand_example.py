"""
Simple Handstand Example using Go2RobotHelper
=============================================

This example demonstrates a simple handstand using the Go2RobotHelper class.

The helper automatically handles:
- Connection management
- Mode switching with firmware 1.1.7 compatibility
- State monitoring
- Emergency cleanup
- Exception handling
- Proper resource cleanup

Usage:
    python simple_handstand_example.py
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper


async def handstand_demo(robot: Go2RobotHelper):
    """
    Demonstrate handstand using the robot helper
    
    This function contains only the core logic - all boilerplate
    is handled by the Go2RobotHelper class.
    """
    print("🎯 Starting handstand demonstration...")
    
    # Perform handstand sequence (includes mode switching, standing, handstand, cleanup)
    success = await robot.handstand_sequence(duration=10.0)
    
    if success:
        print("🎉 Handstand demonstration completed successfully!")
    else:
        print("❌ Handstand demonstration failed")
    
    # Additional commands if needed
    await robot.execute_command("Hello")
    

if __name__ == "__main__":
    """
    Main entry point - all connection management and error handling
    is handled by the helper
    """
    async def main():
        # The context manager handles all connection setup and cleanup
        async with Go2RobotHelper() as robot:
            await handstand_demo(robot)
    
    # Run with automatic error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}") 