import asyncio
import logging
import sys
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC

# Enable logging for debugging
logging.basicConfig(level=logging.INFO)

def display_data(message):
    """
    Display robot odometry data in a formatted manner.
    
    Args:
        message: Odometry data containing position, orientation, and velocity information
    """
    try:
        print(message)
        header = message.get('header', {})
        timestamp = header.get('stamp', {})
        
        # Alternative field names (adapt based on actual message structure)
        position = message.get('pose', {}).get('position', {})
        orientation = message.get('pose', {}).get('orientation', {})

        # Clear the entire screen and reset cursor position to top
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


async def main():
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

        # Define a callback function to handle robot odometry when received
        def odometry_callback(message):
            current_message = message['data']
            display_data(current_message)

        print("Subscribing to robot odometry data...")
        print("Press Ctrl+C to stop\n")

        # Subscribe to the robot odometry data and use the callback function to process incoming messages
        conn.datachannel.pub_sub.subscribe(RTC_TOPIC['ROBOTODOM'], odometry_callback)

        # Keep the program running to allow event handling for 1 hour
        await asyncio.sleep(3600)

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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass 