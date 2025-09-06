"""
Go2 Robot Trajectory Follow - Simple Example
===========================================

A simple example demonstrating TrajectoryFollow command in sports mode.
This example shows the basic usage pattern for trajectory following.

Usage:
    python examples/data_channel/trajectory_follow_simple.py
    python examples/data_channel/trajectory_follow_simple.py --ip 192.168.8.181

Notes:
- Robot must be in sports mode for TrajectoryFollow to work
- Uses proper sports mode sequence: StandDown -> Sports Mode -> TrajectoryFollow -> Stand
- Minimal console output as per user preferences
"""

import argparse
import asyncio
import logging

from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import WebRTCConnectionMethod


async def run_trajectory_follow_demo(robot: Go2RobotHelper) -> None:
    """
    Run a simple TrajectoryFollow demonstration
    
    Args:
        robot: Go2RobotHelper instance
    """
    print("🎯 Starting TrajectoryFollow demo")
    
    # Step 1: Ensure proper sports mode sequence
    print("🔄 Preparing for sports mode...")
    
    # Switch to normal mode first, then stand up
    await robot.ensure_mode("normal")
    await robot.execute_command("StandUp", wait_time=1.5)
    
    # Stand down before switching to sports mode (required)
    print("⬇️ Standing down for sports mode...")
    await robot.execute_command("StandDown", wait_time=2.0)
    
    # Switch to sports mode
    print("🏃 Switching to sports mode...")
    await robot.ensure_mode("sport")
    
    # Stand up in sports mode
    print("⬆️ Standing up in sports mode...")
    await robot.execute_command("StandUp", wait_time=1.5)
    
    # Step 2: Execute TrajectoryFollow command
    print("🎯 Executing TrajectoryFollow command...")
    
    # Basic trajectory data - this is a simplified example
    # The actual parameter structure may vary based on the robot's firmware
    trajectory_data = {
        "trajectory": [
            {"x": 0.0, "y": 0.0, "z": 0.0, "time": 0.0},
            {"x": 0.5, "y": 0.0, "z": 0.0, "time": 2.0},
            {"x": 0.5, "y": 0.3, "z": 0.0, "time": 4.0},
            {"x": 0.0, "y": 0.3, "z": 0.0, "time": 6.0},
            {"x": 0.0, "y": 0.0, "z": 0.0, "time": 8.0}
        ],
        "duration": 8.0,
        "loop": False
    }
    
    try:
        # Execute the TrajectoryFollow command
        response = await robot.execute_command(
            "TrajectoryFollow", 
            parameter=trajectory_data,
            wait_time=0.1
        )
        
        # Check response
        if response and "data" in response:
            status = response["data"].get("header", {}).get("status", {})
            code = status.get("code", 0)
            if code != 0:
                print(f"⚠️ TrajectoryFollow response code={code}, msg={status.get('msg', 'Unknown error')}")
            else:
                print("✅ TrajectoryFollow command accepted")
        
        # Wait for trajectory to complete
        print("⏳ Waiting for trajectory to complete...")
        await asyncio.sleep(8.5)  # Wait for trajectory duration + buffer
        
    except Exception as e:
        print(f"❌ Error executing TrajectoryFollow: {e}")
        print("💡 Note: TrajectoryFollow may require specific parameter format")
        print("   Check robot firmware version and API documentation")
        raise
    
    # Step 3: Cleanup - ensure robot is standing
    print("🧹 Cleaning up...")
    try:
        await robot.execute_command("StopMove", wait_time=0.5)
        await robot.execute_command("StandUp", wait_time=1.0)
    except Exception:
        pass
    
    print("✅ TrajectoryFollow demo completed!")


async def main(args) -> None:
    """Main function with minimal console output"""
    # Minimal console output as per user preference
    logging.getLogger().setLevel(logging.ERROR)
    
    connection_method = {
        "ap": WebRTCConnectionMethod.LocalAP,
        "sta": WebRTCConnectionMethod.LocalSTA,
        "remote": WebRTCConnectionMethod.Remote,
    }[args.method]
    
    async with Go2RobotHelper(
        connection_method=connection_method,
        serial_number=args.serial,
        ip=args.ip,
        username=args.username,
        password=args.password,
        enable_state_monitoring=False,
        detailed_state_display=False,
        logging_level=logging.ERROR,
    ) as robot:
        await run_trajectory_follow_demo(robot)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Go2 Robot TrajectoryFollow Demo")
    parser.add_argument("--method", choices=["ap", "sta", "remote"], default="sta")
    parser.add_argument("--ip", type=str, default=None, help="Robot IP for STA mode")
    parser.add_argument("--serial", type=str, default=None, help="Robot serial number")
    parser.add_argument("--username", type=str, default=None, help="Username for remote mode")
    parser.add_argument("--password", type=str, default=None, help="Password for remote mode")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\n⚠️ Demo interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
