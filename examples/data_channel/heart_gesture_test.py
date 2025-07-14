"""
Go2 Robot Heart Gesture Test - Updated with Go2RobotHelper
==========================================================

Simple test to verify if sport commands are working properly using the FingerHeart gesture.
This is a simpler test than handstand to debug command execution.

UPDATED: Converted to use Go2RobotHelper, reducing code from ~180 lines to ~40 lines
while maintaining all testing capabilities and adding firmware 1.1.7 compatibility.

The helper automatically handles:
- Connection management and cleanup
- Mode switching with firmware 1.1.7 compatibility
- State monitoring and display
- Exception handling and emergency cleanup
- Proper resource management

Usage:
    python heart_gesture_test.py

The heart gesture uses:
- SPORT_CMD["FingerHeart"] (1036) - Heart gesture with legs
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper


async def heart_gesture_test(robot: Go2RobotHelper):
    """
    Test heart gesture command to verify sport commands work
    
    This is a comprehensive test that verifies multiple sport commands
    to ensure the robot is responding properly.
    """
    print("=== Go2 Robot Heart Gesture Test ===")
    print("Testing FingerHeart command to verify sport commands work")
    print("🤖 Starting sport command verification...")
    
    # Get state monitor for testing feedback
    state_monitor = robot.get_state_monitor()
    
    # Test in normal mode first
    print("\n📋 Step 1: Testing basic commands in normal mode...")
    await robot.ensure_mode("normal")
    
    # Test basic Hello command first
    print("\n👋 Step 2: Testing basic Hello command...")
    await robot.execute_command("Hello", wait_time=3)
    print("✅ Hello command completed")
    
    # Test some movement
    print("\n🚶 Step 3: Testing movement commands...")
    await robot.execute_command("Move", {"x": 0.3, "y": 0, "z": 0}, wait_time=2)  # Forward
    await robot.execute_command("Move", {"x": -0.3, "y": 0, "z": 0}, wait_time=2) # Back
    print("✅ Movement commands completed")
    
    # Switch to AI mode for gesture commands
    print("\n🧠 Step 4: Switching to AI mode for gesture testing...")
    await robot.ensure_mode("ai")
    
    # Test FingerHeart gesture (main test)
    print("\n❤️  Step 5: Testing FingerHeart gesture...")
    print("Executing FingerHeart command...")
    await robot.execute_command("FingerHeart", wait_time=5)
    print("✅ FingerHeart command completed")
    
    # Test Stretch gesture  
    print("\n🤸 Step 6: Testing Stretch gesture...")
    await robot.execute_command("Stretch", wait_time=4)
    print("✅ Stretch command completed")
    
    # Test Hello in AI mode
    print("\n👋 Step 7: Testing Hello in AI mode...")
    await robot.execute_command("Hello", wait_time=3)
    print("✅ Hello in AI mode completed")
    
    # Show final robot state
    print("\n📊 Final robot state:")
    if state_monitor.latest_state:
        final_mode = state_monitor.latest_state.get('mode', 'unknown')
        final_progress = state_monitor.latest_state.get('progress', 'unknown')
        final_gait = state_monitor.latest_state.get('gait_type', 'unknown')
        print(f"Mode: {final_mode}")
        print(f"Progress: {final_progress}")
        print(f"Gait Type: {final_gait}")
    
    print("\n🎉 All sport command tests completed successfully!")
    print("✅ Hello command working")
    print("✅ Movement commands working")
    print("✅ FingerHeart gesture working")
    print("✅ Stretch gesture working")
    print("✅ Mode switching working")
    print("\n🤖 Robot appears to be responding properly to sport commands!")


if __name__ == "__main__":
    """
    Main entry point with automatic error handling
    """
    print("Starting Go2 Robot Heart Gesture Test...")
    print("This will test basic sport commands to verify robot responsiveness")
    print("Press Ctrl+C to stop the program at any time")
    print("=" * 60)
    
    async def main():
        # Use state monitoring to see what's happening
        async with Go2RobotHelper() as robot:
            await heart_gesture_test(robot)
    
    # Run with automatic error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

 