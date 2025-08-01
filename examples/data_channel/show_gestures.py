"""
Go2 Robot Gesture Demonstration Example
=======================================

This example demonstrates various gesture commands for the Go2 robot using the Go2RobotHelper class.
It showcases how to execute different robot gestures including Hello, FingerHeart (heart gesture), 
and Stretch commands with proper timing and state management.

The Go2RobotHelper automatically handles:
- WebRTC connection establishment and cleanup
- Robot mode switching with firmware compatibility
- Real-time state monitoring and status display
- Exception handling and emergency shutdown procedures
- Proper resource management and cleanup

Features demonstrated:
- Hello gesture: Basic robot greeting
- FingerHeart gesture: Heart sign with 5-second duration
- Stretch gesture: Robot stretching motion with 4-second duration

Usage:
    python show_gestures.py

Requirements:
- Go2 robot with WebRTC connectivity
- Compatible firmware version
- Network connection to robot
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

 