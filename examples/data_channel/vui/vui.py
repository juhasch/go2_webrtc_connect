"""
Go2 Robot VUI (Visual User Interface) Demonstration Example
==========================================================

This example demonstrates VUI (Visual User Interface) controls for the Go2 robot using the Go2RobotHelper class.
It showcases how to control the robot's LED brightness, colors, and flashing patterns with proper timing and state management.

The Go2RobotHelper automatically handles:
- WebRTC connection establishment and cleanup
- Robot mode switching with firmware compatibility
- Real-time state monitoring and status display
- Exception handling and emergency shutdown procedures
- Proper resource management and cleanup

Features demonstrated:
- LED brightness control: Adjust brightness from 0 to 10 and back
- LED color changes: Purple and cyan colors with timing
- LED flashing patterns: Cyan color with 1-second flash cycle

Usage:
    python vui.py

Requirements:
- Go2 robot with WebRTC connectivity
- Compatible firmware version
- Network connection to robot
"""

import asyncio
import json
from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import RTC_TOPIC, VUI_COLOR


async def vui_demo(robot: Go2RobotHelper):
    """
    VUI demonstration with LED brightness and color controls
    """
    print("💡 Starting VUI demonstration...")
    
    # Get the current brightness
    print("\nFetching the current brightness level...")
    response = await robot.conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["VUI"], 
        {"api_id": 1006}
    )

    if response['data']['header']['status']['code'] == 0:
        data = json.loads(response['data']['data'])
        current_brightness = data['brightness']
        print(f"Current brightness level: {current_brightness}\n")

    # Adjusting brightness level from 0 to 10
    print("Increasing brightness from 0 to 10...")
    for brightness_level in range(0, 11):
        await robot.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["VUI"], 
            {
                "api_id": 1005,
                "parameter": {"brightness": brightness_level}
            }
        )
        print(f"Brightness level: {brightness_level}/10")
        await asyncio.sleep(0.5)

    # Adjusting brightness level from 10 back to 0
    print("\nDecreasing brightness from 10 to 0...")
    for brightness_level in range(10, -1, -1):
        await robot.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["VUI"], 
            {
                "api_id": 1005,
                "parameter": {"brightness": brightness_level}
            }
        )
        print(f"Brightness level: {brightness_level}/10")
        await asyncio.sleep(0.5)

    # Change the LED color to purple
    print("\nChanging LED color to purple for 5 seconds...")
    await robot.conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["VUI"], 
        {
            "api_id": 1007,
            "parameter": 
            {
                "color": VUI_COLOR.PURPLE,
                "time": 5
            }
        }
    )
    await asyncio.sleep(6)

    # Change the LED color to cyan and flash
    # flash_cycle is between 499 and time*1000
    print("\nChanging LED color to cyan with flash (cycle: 1000ms)...")
    await robot.conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["VUI"], 
        {
            "api_id": 1007,
            "parameter": 
            {
                "color": VUI_COLOR.CYAN,
                "time": 5,
                "flash_cycle": 1000  # Flash every second
            }
        }
    )
    await asyncio.sleep(5)
    
    print("💡 VUI demonstration completed!")


if __name__ == "__main__":
    """
    Main entry point - minimal boilerplate
    """
    async def main():
        # All connection management, state monitoring, and cleanup is automatic
        async with Go2RobotHelper() as robot:
            await vui_demo(robot)
    
    # Standard error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
