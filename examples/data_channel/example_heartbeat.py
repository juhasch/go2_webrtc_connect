import asyncio
import logging
import sys

from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.msgs.heartbeat import WebRTCDataChannelHeartBeat

# Enable logging for debugging
logging.basicConfig(level=logging.INFO)

def response_message(message):
    """Handle incoming heartbeat response messages"""
    print(f"Heartbeat response received: {message}")

async def main():
    conn = None
    try:
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)

        # Connect to the WebRTC service
        print("Connecting to WebRTC...")
        await conn.connect()
        print("Connected to WebRTC successfully!")

        # Initialize heartbeat with channel and pub-sub
        heartbeat = WebRTCDataChannelHeartBeat(conn.datachannel.channel, conn.datachannel.pub_sub)

        # Start sending heartbeats
        print("Starting heartbeat transmission...")
        heartbeat.start_heartbeat()

        # Run for 10 seconds to demonstrate heartbeat functionality
        print("Running heartbeat for 10 seconds...")
        for i in range(10):
            await asyncio.sleep(1)
            if heartbeat.heartbeat_response:
                print(f"Last heartbeat response: {heartbeat.heartbeat_response}")
            else:
                print("No heartbeat response received yet")

        # Stop heartbeats when done
        print("Stopping heartbeat transmission...")
        heartbeat.stop_heartbeat()
        print("Heartbeat stopped successfully!")

    except KeyboardInterrupt:
        # Handle Ctrl+C to exit gracefully within the async context
        print("\nProgram interrupted by user")
    except ValueError as e:
        # Log any value errors that occur during the process
        logging.error(f"An error occurred: {e}")
    except Exception as e:
        # Log any other errors
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
        # Handle Ctrl+C to exit gracefully
        pass