"""
Simple Heart Gesture Example using Go2RobotHelper
================================================

This example demonstrates heart gesture commands using the Go2RobotHelper class.

The helper automatically handles:
- Connection management and cleanup
- Mode switching with firmware 1.1.7 compatibility  
- State monitoring and display
- Exception handling and emergency cleanup
- Proper resource management

Usage:
    python simple_heart_gesture_example.py
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper


async def heart_gesture_demo(robot: Go2RobotHelper):
    """
    Simple heart gesture demonstration
    """
    print("❤️  Starting heart gesture demonstration...")
    
    # Test basic Hello command first
    await robot.execute_command("Hello")
    
    # Perform heart gesture
    await robot.execute_command("FingerHeart", wait_time=5)
    
    # Try stretch command
    await robot.execute_command("Stretch", wait_time=4)
    
    print("❤️  Heart gesture demonstration completed!")


if __name__ == "__main__":
    """
    Main entry point - minimal boilerplate
    """
    async def main():
        # All connection management, state monitoring, and cleanup is automatic
        async with Go2RobotHelper() as robot:
            await heart_gesture_demo(robot)
    
    # Standard error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

 