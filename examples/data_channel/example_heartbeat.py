import asyncio
import logging
import sys
import time
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.msgs.heartbeat import WebRTCDataChannelHeartBeat

# Enable logging for debugging
logging.basicConfig(level=logging.INFO)

def response_message(message):
    """Handle incoming heartbeat response messages"""
    print(f"Heartbeat response received: {message}")

async def main():
    try:
        # Choose a connection method (uncomment the correct one)
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        # conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip="192.168.8.181")
        # conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, serialNumber="B42D2000XXXXXXXX")
        # conn = Go2WebRTCConnection(WebRTCConnectionMethod.Remote, serialNumber="B42D2000XXXXXXXX", username="email@gmail.com", password="pass")
        # conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

        # Connect to the WebRTC service
        print("Connecting to WebRTC...")
        await conn.connect()
        print("Connected to WebRTC successfully!")

        # Initialize heartbeat with channel and pub-sub
        heartbeat = WebRTCDataChannelHeartBeat(conn.datachannel, conn.datachannel.pub_sub)

        # Start sending heartbeats
        print("Starting heartbeat transmission...")
        heartbeat.start_heartbeat()

        # Handle incoming heartbeat responses
        heartbeat.handle_response(response_message)

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

    except ValueError as e:
        # Log any value errors that occur during the process
        logging.error(f"An error occurred: {e}")
    except Exception as e:
        # Log any other errors
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C to exit gracefully
        print("\nProgram interrupted by user")
        sys.exit(0)