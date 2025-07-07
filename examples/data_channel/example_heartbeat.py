import asyncio
import logging
import sys
import time

from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

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

        # Use the existing heartbeat instance from the data channel
        # (Don't create a new one - responses go to the original instance)
        heartbeat = conn.datachannel.heartbeat

        # Start sending heartbeats
        print("Starting heartbeat transmission...")
        heartbeat.start_heartbeat()

        # Run for 10 seconds to demonstrate heartbeat functionality
        print("Running heartbeat for 10 seconds...")
        print("Monitoring heartbeat responses (checking every 2.5 seconds to align with heartbeat frequency)...")
        
        start_time = time.time()
        
        for i in range(10):  # 4 checks over ~10 seconds
            await asyncio.sleep(1)
            
            # Check for new responses using the flag-based method
            has_new_response = heartbeat.check_and_reset_new_response_flag()
            response_info = heartbeat.get_response_info()
            
            current_time = time.time()
            elapsed = current_time - start_time
            
            if has_new_response:
                print(f"[{elapsed:.1f}s] ✓ NEW heartbeat response received! (Total: {response_info['total_responses']})")
        
        # Final summary
        final_info = heartbeat.get_response_info()
        total_time = time.time() - start_time
        print(f"\n📈 Final Summary:")
        print(f"   Total responses: {final_info['total_responses']}")
        print(f"   Test duration: {total_time:.1f}s")
        if final_info['total_responses'] > 0:
            print(f"   Average response rate: {final_info['total_responses']/total_time:.2f} responses/sec")
            print(f"   Last response: {final_info['response_age_seconds']:.1f}s ago")

        # Stop heartbeats when done
        print("\nStopping heartbeat transmission...")
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