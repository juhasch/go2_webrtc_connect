import asyncio
import logging
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC

# Enable logging for debugging
logging.basicConfig(level=logging.INFO)

def odometry_callback(message):
    """Simple callback to print robot odometry data"""
    data = message['data']
    print(f"Robot Odometry: {data}")

async def main():
    conn = None
    try:
        # Connect to Go2 robot
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        await conn.connect()
        
        print("Connected to Go2 robot")
        print("Subscribing to robot odometry data...")
        print("Press Ctrl+C to stop\n")
        
        # Subscribe to robot odometry data
        conn.datachannel.pub_sub.subscribe(RTC_TOPIC['ROBOTODOM'], odometry_callback)
        
        # Keep running
        await asyncio.sleep(3600)
        
    except KeyboardInterrupt:
        print("\nProgram stopped by user")
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        if conn:
            await conn.disconnect()
            print("Disconnected from robot")

if __name__ == "__main__":
    asyncio.run(main()) 