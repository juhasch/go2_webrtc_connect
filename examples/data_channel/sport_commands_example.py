"""
Sport Commands Example using Go2RobotHelper
==========================================

This example demonstrates various sport commands using the Go2RobotHelper
and the create_example_main factory function for even more concise code.

The create_example_main function automatically handles:
- Connection management
- Exception handling
- Keyboard interrupts
- Resource cleanup
- Standard error messages

Usage:
    python sport_commands_example.py
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper, create_example_main


async def sport_demo(robot: Go2RobotHelper):
    """
    Demonstrate various sport commands
    
    This function contains only the core robot logic - everything else
    is handled by the helper and factory function.
    """
    print("🎯 Starting sport commands demonstration...")
    
    # Ensure robot is in normal mode for basic commands
    await robot.ensure_mode("normal")
    
    # Basic greeting
    await robot.execute_command("Hello")
    
    # Movement commands
    print("📍 Testing movement commands...")
    await robot.execute_command("Move", {"x": 0.5, "y": 0, "z": 0})  # Forward
    await robot.execute_command("Move", {"x": -0.5, "y": 0, "z": 0})  # Backward
    await robot.execute_command("Move", {"x": 0, "y": 0.3, "z": 0})   # Left
    await robot.execute_command("Move", {"x": 0, "y": -0.3, "z": 0})  # Right
    
    # Gestures
    print("🎭 Testing gesture commands...")
    await robot.execute_command("Stretch", wait_time=4)
    await robot.execute_command("FingerHeart", wait_time=4)
    
    # Switch to AI mode for advanced commands
    await robot.ensure_mode("ai")
    
    # Dance commands
    print("💃 Testing dance commands...")
    await robot.execute_command("Dance1", wait_time=6)
    await robot.execute_command("Dance2", wait_time=6)
    
    # Try handstand sequence
    print("🤸 Testing handstand sequence...")
    success = await robot.handstand_sequence(duration=8.0)
    
    if success:
        print("🎉 All sport commands demonstration completed successfully!")
    else:
        print("⚠️  Handstand failed, but other commands worked")
    
    # Return to normal mode
    await robot.ensure_mode("normal")
    await robot.execute_command("Hello")  # Final greeting


# Create the main function using the factory
# This automatically handles all boilerplate: connection, exceptions, cleanup
main = create_example_main(sport_demo)

if __name__ == "__main__":
    """
    Entry point with minimal boilerplate
    """
    print("Starting Go2 Robot Sport Commands Example...")
    print("This demonstrates the Go2RobotHelper with various sport commands")
    print("Press Ctrl+C to stop the program at any time")
    print("=" * 60)
    
    # Run with automatic error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        exit(1) 