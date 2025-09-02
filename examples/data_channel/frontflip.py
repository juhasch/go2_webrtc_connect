"""
Go2 Robot Stand Up Example
==========================

This example demonstrates how to make the Go2 robot stand up using the Go2RobotHelper class.
It's a very simple example that shows the basic stand up command execution.

The Go2RobotHelper automatically handles:
- WebRTC connection establishment and cleanup
- Robot mode switching with firmware compatibility
- Real-time state monitoring and status display
- Exception handling and emergency shutdown procedures
- Proper resource management and cleanup

Usage:
    python stand_up.py

Requirements:
- Go2 robot with WebRTC connectivity
- Compatible firmware version
- Network connection to robot
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper


async def stand_up_demo(robot: Go2RobotHelper):
    """
    Simple stand up demonstration
    """
    print("🦵 Starting stand up demonstration...")
    
    # Make the robot stand up
    await robot.execute_command("FrontFlip", wait_time=3)
    
    print("✅ Robot is now standing up!")
    print("🦵 Stand up demonstration completed!")


if __name__ == "__main__":
    """
    Main entry point - minimal boilerplate
    """
    async def main():
        # All connection management, state monitoring, and cleanup is automatic
        async with Go2RobotHelper() as robot:
            await stand_up_demo(robot)
    
    # Standard error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}") 