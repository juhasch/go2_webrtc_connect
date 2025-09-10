"""
Go2 Robot Odometry Monitoring
============================

This example demonstrates monitoring of the robot's odometry data
using the WebRTC connection.

Usage:
    python robot_odometry.py [--once]

Options:
    --once   Fetch and display one odometry update, then exit
"""

import asyncio
import argparse
import logging
import sys
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC
from typing import Optional

# Enable logging for debugging
logging.basicConfig(level=logging.INFO)

def display_data(message, clear_screen: bool = True):
    """
    Display robot odometry data in a formatted manner.
    
    Args:
        message: Odometry data containing position, orientation, and velocity information
        clear_screen: Whether to clear the screen before displaying (default: True)
    """
    try:
        header = message.get('header', {})
        timestamp = header.get('stamp', {})
        
        position = message.get('pose', {}).get('position', {})
        orientation = message.get('pose', {}).get('orientation', {})

        if clear_screen:
            sys.stdout.write("\033[H\033[J")

        # Print robot odometry information
        print("Go2 Robot Odometry (ROBOTODOM)")
        print("==============================")
     
        if timestamp:
            if isinstance(timestamp, dict):
                if 'sec' in timestamp and 'nanosec' in timestamp:
                    print(f"Timestamp: {timestamp['sec']}.{timestamp['nanosec']:09d}")
                else:
                    print(f"Timestamp: {timestamp}")
            else:
                print(f"Timestamp: {timestamp}")
        
        # Position information
        print("\nPosition:")
        if isinstance(position, dict):
            x = position.get('x', 'N/A')
            y = position.get('y', 'N/A')
            z = position.get('z', 'N/A')
            print(f"  X: {x:.6f} m" if isinstance(x, (int, float)) else f"  X: {x}")
            print(f"  Y: {y:.6f} m" if isinstance(y, (int, float)) else f"  Y: {y}")
            print(f"  Z: {z:.6f} m" if isinstance(z, (int, float)) else f"  Z: {z}")
        else:
            print(f"  {position}")

        # Orientation information
        print("\nOrientation:")
        if isinstance(orientation, dict):
            # Check for quaternion representation
            if 'x' in orientation and 'y' in orientation and 'z' in orientation and 'w' in orientation:
                print(f"  Quaternion - X: {orientation['x']:.6f}")
                print(f"  Quaternion - Y: {orientation['y']:.6f}")
                print(f"  Quaternion - Z: {orientation['z']:.6f}")
                print(f"  Quaternion - W: {orientation['w']:.6f}")
            # Check for RPY (Roll, Pitch, Yaw) representation
            elif 'roll' in orientation or 'pitch' in orientation or 'yaw' in orientation:
                roll = orientation.get('roll', 'N/A')
                pitch = orientation.get('pitch', 'N/A')
                yaw = orientation.get('yaw', 'N/A')
                print(f"  Roll:  {roll:.6f} rad" if isinstance(roll, (int, float)) else f"  Roll: {roll}")
                print(f"  Pitch: {pitch:.6f} rad" if isinstance(pitch, (int, float)) else f"  Pitch: {pitch}")
                print(f"  Yaw:   {yaw:.6f} rad" if isinstance(yaw, (int, float)) else f"  Yaw: {yaw}")
            else:
                print(f"  {orientation}")
        else:
            print(f"  {orientation}")

        print("==============================")
        sys.stdout.flush()

    except Exception as e:
        print(f"Error displaying odometry data: {e}")
        print(f"Raw message: {message}")
        sys.stdout.flush()


async def odometry_monitoring_demo(conn: Go2WebRTCConnection, once: bool = False):
    """
    Demonstrate robot odometry monitoring using the WebRTC connection
    
    This subscribes to the robot's odometry data and displays
    real-time position and orientation information.
    """
    print("📡 Starting robot odometry monitoring...")
    
    # If running in once mode, use an event to release after first message
    first_message_event: Optional[asyncio.Event] = asyncio.Event() if once else None

    # Define callback function to handle odometry data when received
    def odometry_callback(message):
        current_message = message['data']
        display_data(current_message, clear_screen=(not once))
        if first_message_event is not None and not first_message_event.is_set():
            first_message_event.set()
    
    # Subscribe to the robot odometry data
    conn.datachannel.pub_sub.subscribe(RTC_TOPIC['ROBOTODOM'], odometry_callback)
    print("✅ Monitoring robot odometry data (Ctrl+C to stop)")
    print("=" * 50)

    # If only one message is requested, wait for it, then unsubscribe and return
    if once and first_message_event is not None:
        try:
            await first_message_event.wait()
        finally:
            try:
                conn.datachannel.pub_sub.unsubscribe(RTC_TOPIC['ROBOTODOM'])
            except Exception:
                pass
        return
    
    # Simple monitoring loop - allow cancellation to propagate cleanly
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        raise


async def main(once: bool = False):
    """
    Main function to establish WebRTC connection and subscribe to robot odometry data.
    """
    conn = None
    try:
        # Choose a connection method (uncomment the correct one)
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)

        # Connect to the WebRTC service
        print("Connecting to Go2 robot...")
        await conn.connect()
        print("Connected successfully!")

        print("Subscribing to robot odometry data...")
        if not once:
            print("Press Ctrl+C to stop\n")

        # Start odometry monitoring
        await odometry_monitoring_demo(conn, once=once)

    except KeyboardInterrupt:
        # Handle Ctrl+C to exit gracefully within the async context
        print("\nProgram interrupted by user")
    except ValueError as e:
        # Log any value errors that occur during the process
        logging.error(f"An error occurred: {e}")
    except Exception as e:
        # Log any other errors that occur during the process
        logging.error(f"Unexpected error: {e}")
    finally:
        # Ensure proper cleanup of the WebRTC connection
        if conn:
            try:
                await conn.disconnect()
                print("WebRTC connection closed successfully")
            except Exception as e:
                logging.error(f"Error closing WebRTC connection: {e}")


if __name__ == "__main__":
    """
    Main entry point with argument parsing for --once option
    """
    print("Go2 Robot Odometry Monitoring")
    print("Press Ctrl+C to stop")
    print("=" * 30)
    
    parser = argparse.ArgumentParser(description="Go2 Robot Odometry Monitoring")
    parser.add_argument("--once", action="store_true", help="Fetch one odometry update and exit")
    args = parser.parse_args()

    try:
        asyncio.run(main(once=args.once))
    except KeyboardInterrupt:
        print("\n✅ Stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        print("Done.") 