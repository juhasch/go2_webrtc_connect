"""
Go2 Robot Heartbeat Example - Updated with Go2RobotHelper
========================================================

This example demonstrates how to send heartbeat messages to maintain connection
with the Go2 robot, now simplified with Go2RobotHelper.

UPDATED: Converted to use Go2RobotHelper, reducing boilerplate code while
maintaining all heartbeat functionality and adding better connection management.

The helper automatically handles:
- Connection management and cleanup
- Exception handling and recovery
- Proper resource management

This example demonstrates:
- Sending periodic heartbeat messages
- Connection stability monitoring
- Graceful shutdown handling

Usage:
    python example_heartbeat.py
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper


async def heartbeat_demo(robot: Go2RobotHelper):
    """
    Demonstrate heartbeat functionality using the robot helper
    
    This sends periodic heartbeat messages to maintain connection
    with the robot and monitor connection stability.
    """
    print("=== Go2 Robot Heartbeat Example ===")
    print("📡 Starting heartbeat demonstration...")
    print("This will send periodic heartbeat messages to the robot")
    print("Press Ctrl+C to stop")
    
    # Get access to the underlying connection for heartbeat
    conn = robot.conn
    
    heartbeat_count = 0
    
    print(f"\n💓 Starting heartbeat loop...")
    print("Sending heartbeat every 5 seconds...")
    
    try:
        while True:
            heartbeat_count += 1
            
            # Send heartbeat message
            print(f"\n💓 Sending heartbeat #{heartbeat_count}...")
            
            # The datachannel has built-in heartbeat functionality
            # We can also send our own messages to test connectivity
            try:
                # Send a simple message to test connection
                conn.datachannel.pub_sub.publish_without_callback(
                    "", 
                    f"heartbeat_{heartbeat_count}",
                    "heartbeat"
                )
                
                print(f"✅ Heartbeat #{heartbeat_count} sent successfully")
                
            except Exception as e:
                print(f"❌ Heartbeat #{heartbeat_count} failed: {e}")
                break
            
            # Wait for next heartbeat
            print(f"⏳ Waiting 5 seconds for next heartbeat...")
            await asyncio.sleep(5)
            
    except asyncio.CancelledError:
        print(f"\n🛑 Heartbeat loop cancelled")
        raise
    except Exception as e:
        print(f"\n❌ Error in heartbeat loop: {e}")
        raise
    
    print(f"\n📊 Heartbeat session completed")
    print(f"Total heartbeats sent: {heartbeat_count}")


if __name__ == "__main__":
    """
    Main entry point with automatic error handling
    """
    print("Starting Go2 Robot Heartbeat Example...")
    print("This will demonstrate heartbeat communication with the robot")
    print("Press Ctrl+C to stop the program at any time")
    print("=" * 60)
    
    async def main():
        # Context manager handles all connection setup and cleanup
        async with Go2RobotHelper() as robot:
            await heartbeat_demo(robot)
    
    # Run with automatic error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
        print("Heartbeat demonstration stopped")
    except Exception as e:
        print(f"❌ Fatal error: {e}")