"""
Go2 Robot Sit Down Example
==========================

This example demonstrates how to make the Go2 robot sit down using the Go2RobotHelper class.
It's a very simple example that shows the basic sit command execution.

The Go2RobotHelper automatically handles:
- WebRTC connection establishment and cleanup
- Robot mode switching with firmware compatibility
- Real-time state monitoring and status display
- Exception handling and emergency shutdown procedures
- Proper resource management and cleanup

Usage:
    python sit_down.py

Requirements:
- Go2 robot with WebRTC connectivity
- Compatible firmware version
- Network connection to robot
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper


async def sit_down_demo(robot: Go2RobotHelper):
    """
    Simple sit down demonstration
    """
    print("🪑 Starting sit down demonstration...")
    
    # Make the robot sit down
    await robot.execute_command("Sit", wait_time=10)
    await robot.execute_command("StandUp", wait_time=3)
 

if __name__ == "__main__":
    """
    Main entry point - minimal boilerplate
    """
    async def main():
        # All connection management, state monitoring, and cleanup is automatic
        async with Go2RobotHelper() as robot:
            await sit_down_demo(robot)
    
    # Standard error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}") 