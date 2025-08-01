"""
Go2 Robot Sport Mode Example - Updated with Go2RobotHelper
==========================================================

This example demonstrates basic sport mode functionality including movement commands,
gestures, and mode switching, now simplified with Go2RobotHelper.

UPDATED: Converted to use Go2RobotHelper, reducing code from ~200 lines to ~50 lines
while maintaining all functionality and adding firmware 1.1.7 compatibility.

The helper automatically handles:
- Connection management and cleanup
- Mode switching with firmware 1.1.7 compatibility (sit-before-switch)
- State monitoring and display
- Exception handling and emergency cleanup
- Proper resource management

This example demonstrates:
- Basic sport commands (Hello, movement)
- Mode switching between normal and AI modes
- Movement commands with parameters
- Gesture commands in different modes

Usage:
    python sportmode.py
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper


async def sport_mode_demo(robot: Go2RobotHelper):
    """
    Demonstrate sport mode functionality using the robot helper
    
    This contains the core sport mode logic - all boilerplate
    is handled automatically by Go2RobotHelper.
    """
    print("=== Go2 Robot Sport Mode Example ===")
    print("🎯 Starting sport mode demonstration...")
    
    # Normal Mode Operations
    print("\n🏃 NORMAL MODE OPERATIONS")
    print("=" * 40)
    
    # Ensure we're in normal mode
    await robot.ensure_mode("normal")
    
    # Perform a "Hello" movement
    print("👋 Performing 'Hello' movement...")
    await robot.execute_command("Hello")
    
    # Movement commands
    print("\n🚶 Testing movement commands...")
    
    print("Moving forward...")
    await robot.execute_command("Move", {"x": 0.5, "y": 0, "z": 0}, wait_time=3)
    
    print("Moving backward...")
    await robot.execute_command("Move", {"x": -0.5, "y": 0, "z": 0}, wait_time=3)
    
    print("Moving left...")
    await robot.execute_command("Move", {"x": 0, "y": 0.3, "z": 0}, wait_time=3)
    
    print("Moving right...")
    await robot.execute_command("Move", {"x": 0, "y": -0.3, "z": 0}, wait_time=3)
    
    # AI Mode Operations
    print("\n🧠 AI MODE OPERATIONS")
    print("=" * 40)
    
    # Switch to AI mode
    await robot.ensure_mode("ai")
    
    # Perform gestures in AI mode
    print("🤸 Performing stretch movement...")
    await robot.execute_command("Stretch", wait_time=4)
    
    print("❤️  Performing heart gesture...")
    await robot.execute_command("FingerHeart", wait_time=4)
    
    # Try handstand sequence (if working in firmware 1.1.7)
    print("\n🤸 Testing handstand sequence...")
    print("Switching to Handstand Mode...")
    await robot.execute_command("StandOut", {"data": True}, wait_time=5)
    
    print("Switching back to StandUp Mode...")
    await robot.execute_command("StandOut", {"data": False}, wait_time=3)
    
    # Final demonstration
    print("\n🎉 FINAL DEMONSTRATION")
    print("=" * 40)
    
    print("Performing final Hello gesture...")
    await robot.execute_command("Hello", wait_time=2)
    
    print("\n✅ Sport mode demonstration completed successfully!")
    print("The robot performed Hello gesture and movement commands in multiple modes.")


if __name__ == "__main__":
    """
    Main entry point with automatic error handling
    """
    print("Starting Go2 Robot Sport Mode Example...")
    print("This will demonstrate basic sport commands and movement")
    print("Press Ctrl+C to stop the program at any time")
    print("=" * 50)
    
    async def main():
        # Context manager handles all connection setup and cleanup
        async with Go2RobotHelper() as robot:
            await sport_mode_demo(robot)
    
    # Run with automatic error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")