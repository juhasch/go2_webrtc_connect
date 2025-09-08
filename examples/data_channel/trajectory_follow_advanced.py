"""
Go2 Robot Trajectory Follow - Advanced Example
=============================================

An advanced example demonstrating TrajectoryFollow command in sports mode
with proper trajectory data structure based on Unitree's C++ SDK examples.

This example includes:
- Proper sports mode sequence (StandDown -> Sports Mode -> TrajectoryFollow -> Stand)
- Multiple trajectory shapes (square, circle, figure-8)
- Configurable trajectory parameters
- Error handling and status monitoring

Usage:
    python examples/data_channel/trajectory_follow_advanced.py
    python examples/data_channel/trajectory_follow_advanced.py --shape circle --scale 0.5
    python examples/data_channel/trajectory_follow_advanced.py --ip 192.168.8.181 --shape figure8

Notes:
- Robot must be in sports mode for TrajectoryFollow to work
- Trajectory data structure based on Unitree SDK2 C++ examples
- Minimal console output as per user preferences
"""

import argparse
import asyncio
import logging
import math
from typing import List, Dict, Any

from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import WebRTCConnectionMethod


def generate_trajectory_data(shape: str, scale: float = 1.0, duration: float = 10.0) -> Dict[str, Any]:
    """
    Generate trajectory data in the format expected by TrajectoryFollow command
    
    Args:
        shape: Trajectory shape ('square', 'circle', 'figure8', 'line')
        scale: Scale factor for trajectory size
        duration: Total trajectory duration in seconds
        
    Returns:
        Dictionary containing trajectory data for TrajectoryFollow command
    """
    num_points = 50
    points = []
    
    if shape == "square":
        # Square trajectory
        side_length = 0.4 * scale
        time_per_side = duration / 4
        
        # Forward
        for i in range(num_points // 4):
            t = i / (num_points // 4) * time_per_side
            points.append({
                "x": side_length * (i / (num_points // 4)),
                "y": 0.0,
                "z": 0.0,
                "time": t
            })
        
        # Right
        for i in range(num_points // 4):
            t = time_per_side + i / (num_points // 4) * time_per_side
            points.append({
                "x": side_length,
                "y": side_length * (i / (num_points // 4)),
                "z": 0.0,
                "time": t
            })
        
        # Back
        for i in range(num_points // 4):
            t = 2 * time_per_side + i / (num_points // 4) * time_per_side
            points.append({
                "x": side_length * (1 - i / (num_points // 4)),
                "y": side_length,
                "z": 0.0,
                "time": t
            })
        
        # Left
        for i in range(num_points // 4):
            t = 3 * time_per_side + i / (num_points // 4) * time_per_side
            points.append({
                "x": 0.0,
                "y": side_length * (1 - i / (num_points // 4)),
                "z": 0.0,
                "time": t
            })
    
    elif shape == "circle":
        # Circular trajectory
        radius = 0.3 * scale
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            t = i / num_points * duration
            points.append({
                "x": radius * math.cos(angle),
                "y": radius * math.sin(angle),
                "z": 0.0,
                "time": t
            })
    
    elif shape == "figure8":
        # Figure-8 trajectory
        radius = 0.2 * scale
        for i in range(num_points):
            angle = 4 * math.pi * i / num_points
            t = i / num_points * duration
            x = radius * math.sin(angle)
            y = radius * math.sin(2 * angle) / 2
            points.append({
                "x": x,
                "y": y,
                "z": 0.0,
                "time": t
            })
    
    elif shape == "line":
        # Simple forward line
        distance = 0.8 * scale
        for i in range(num_points):
            t = i / num_points * duration
            points.append({
                "x": distance * i / num_points,
                "y": 0.0,
                "z": 0.0,
                "time": t
            })
    
    else:
        raise ValueError(f"Unknown shape: {shape}. Available: square, circle, figure8, line")
    
    # Return trajectory data in the expected format
    return {
        "trajectory": points,
        "duration": duration,
        "loop": False,
        "interpolation": "linear"  # Linear interpolation between points
    }


async def ensure_sports_mode_sequence(robot: Go2RobotHelper) -> None:
    """
    Ensure proper sports mode sequence: StandDown -> Sports Mode -> Stand
    
    Args:
        robot: Go2RobotHelper instance
    """
    print("🔄 Preparing for sports mode...")
    
    # Ensure normal mode and stand up
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


async def execute_trajectory_follow(robot: Go2RobotHelper, trajectory_data: Dict[str, Any]) -> bool:
    """
    Execute TrajectoryFollow command with the given trajectory data
    
    Args:
        robot: Go2RobotHelper instance
        trajectory_data: Trajectory data dictionary
        
    Returns:
        True if command was successful, False otherwise
    """
    print(f"🎯 Executing TrajectoryFollow with {len(trajectory_data['trajectory'])} points")
    print(f"   Duration: {trajectory_data['duration']:.1f}s")
    print(f"   Shape: {trajectory_data.get('interpolation', 'unknown')} interpolation")
    
    try:
        # Execute the TrajectoryFollow command
        response = await robot.execute_command(
            "TrajectoryFollow", 
            parameter=trajectory_data,
            wait_time=0.1
        )
        
        # Check response status
        if response and "data" in response:
            status = response["data"].get("header", {}).get("status", {})
            code = status.get("code", 0)
            msg = status.get("msg", "Unknown error")
            
            if code == 0:
                print("✅ TrajectoryFollow command accepted")
                return True
            else:
                print(f"❌ TrajectoryFollow failed: code={code}, msg={msg}")
                return False
        else:
            print("⚠️ No response received from TrajectoryFollow command")
            return False
            
    except Exception as e:
        print(f"❌ Error executing TrajectoryFollow: {e}")
        return False


async def run_advanced_trajectory_demo(robot: Go2RobotHelper, shape: str, scale: float, duration: float) -> None:
    """
    Run the advanced trajectory follow demonstration
    
    Args:
        robot: Go2RobotHelper instance
        shape: Trajectory shape type
        scale: Scale factor for trajectory size
        duration: Trajectory duration in seconds
    """
    print(f"🎯 Starting advanced trajectory follow demo")
    print(f"   Shape: {shape}, Scale: {scale}, Duration: {duration}s")
    
    # Generate trajectory data
    trajectory_data = generate_trajectory_data(shape, scale, duration)
    
    # Ensure proper sports mode sequence
    await ensure_sports_mode_sequence(robot)
    
    # Execute trajectory follow
    success = await execute_trajectory_follow(robot, trajectory_data)
    
    if success:
        # Wait for trajectory to complete
        print(f"⏳ Waiting for trajectory to complete ({duration:.1f}s)...")
        await asyncio.sleep(duration + 1.0)  # Extra buffer time
        
        # Cleanup
        print("🧹 Cleaning up...")
        try:
            await robot.execute_command("StopMove", wait_time=0.5)
            await robot.execute_command("StandUp", wait_time=1.0)
        except Exception:
            pass
        
        print("✅ Advanced trajectory follow demo completed!")
    else:
        print("❌ TrajectoryFollow command failed - demo aborted")


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
        await run_advanced_trajectory_demo(robot, args.shape, args.scale, args.duration)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Go2 Robot Advanced TrajectoryFollow Demo")
    parser.add_argument("--method", choices=["ap", "sta", "remote"], default="sta")
    parser.add_argument("--ip", type=str, default=None, help="Robot IP for STA mode")
    parser.add_argument("--serial", type=str, default=None, help="Robot serial number")
    parser.add_argument("--username", type=str, default=None, help="Username for remote mode")
    parser.add_argument("--password", type=str, default=None, help="Password for remote mode")
    
    # Trajectory parameters
    parser.add_argument("--shape", choices=["square", "circle", "figure8", "line"], 
                       default="square", help="Trajectory shape")
    parser.add_argument("--scale", type=float, default=1.0, 
                       help="Scale factor for trajectory size")
    parser.add_argument("--duration", type=float, default=10.0, 
                       help="Trajectory duration in seconds")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\n⚠️ Demo interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
