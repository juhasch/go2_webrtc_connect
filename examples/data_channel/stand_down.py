"""
Go2 Robot Lay Down Example
==========================

This example demonstrates how to make the Go2 robot lay down using the Go2RobotHelper class.
It uses the "StandDown" command to lower the robot's body position.

The Go2RobotHelper automatically handles:
- WebRTC connection establishment and cleanup
- Robot mode switching with firmware compatibility
- Real-time state monitoring and status display
- Exception handling and emergency shutdown procedures
- Proper resource management and cleanup

Usage:
    python lay_down.py

Requirements:
- Go2 robot with WebRTC connectivity
- Compatible firmware version
- Network connection to robot
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper


async def lay_down_demo(robot: Go2RobotHelper):
    """
    Simple lay down demonstration
    """
    print("🛏️  Starting lay down demonstration...")
    
    # Make the robot lay down (lower body position)
    await robot.execute_command("StandDown", wait_time=3)
    
    print("✅ Robot is now laying down!")
    print("🛏️  Lay down demonstration completed!")


if __name__ == "__main__":
    """
    Main entry point - minimal boilerplate
    """
    async def main():
        # All connection management, state monitoring, and cleanup is automatic
        async with Go2RobotHelper() as robot:
            await lay_down_demo(robot)
    
    # Standard error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}") 