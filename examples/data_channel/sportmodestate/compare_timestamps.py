import asyncio
import logging
import sys
import time
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC

# Enable logging for debugging
logging.basicConfig(level=logging.INFO)

# Global variables to track timestamp differences
differences = []
sample_count = 0

def compare_timestamps(message):
    global differences, sample_count
    
    timestamp = message['stamp']
    
    # Convert received timestamp to seconds (float)
    received_time = timestamp['sec'] + timestamp['nanosec'] / 1e9
    
    # Get current system time
    system_time = time.time()
    
    # Calculate the difference (system time - received time)
    time_diff = system_time - received_time
    
    # Add to our list of differences
    differences.append(time_diff)
    sample_count += 1
    
    # Keep only the last 100 samples for rolling average
    if len(differences) > 100:
        differences.pop(0)
    
    # Calculate averaged deviation
    avg_deviation = sum(differences) / len(differences)
    
    # Calculate standard deviation for additional insight
    if len(differences) > 1:
        variance = sum((x - avg_deviation) ** 2 for x in differences) / len(differences)
        std_deviation = variance ** 0.5
    else:
        std_deviation = 0
    
    # Clear the screen and display timestamp comparison
    sys.stdout.write("\033[H\033[J")
    
    # Convert to milliseconds for display
    time_diff_ms = time_diff * 1000
    avg_deviation_ms = avg_deviation * 1000
    std_deviation_ms = std_deviation * 1000
    
    print("Timestamp Comparison Analysis")
    print("=============================")
    print(f"Sample Count: {sample_count}")
    print(f"Received Timestamp: {timestamp['sec']}.{timestamp['nanosec']:09d}")
    print(f"System Time: {system_time:.9f}")
    print(f"Time Difference: {time_diff_ms:.3f} ms")
    print(f"Averaged Deviation: {avg_deviation_ms:.3f} ms")
    print(f"Standard Deviation: {std_deviation_ms:.3f} ms")
    print(f"Samples in Average: {len(differences)}")
    
    if time_diff > 0:
        print("Status: Robot time is BEHIND system time")
    else:
        print("Status: Robot time is AHEAD of system time")
    
    # Show some recent differences for trend analysis
    if len(differences) >= 5:
        recent_diffs = differences[-5:]
        print(f"Last 5 differences: {[f'{d*1000:.3f}' for d in recent_diffs]} ms")
    
    # Optionally, flush to ensure immediate output
    sys.stdout.flush()

async def main():
    conn = None
    try:
        # Choose a connection method (uncomment the correct one)
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)

        # Connect to the WebRTC service.
        await conn.connect()

        print("Starting timestamp comparison...")
        print("Press Ctrl+C to stop and see final results")

        # Define a callback function to handle sportmode status when received.
        def sportmodestatus_callback(message):
            current_message = message['data']
            compare_timestamps(current_message)

        # Subscribe to the sportmode status data and use the callback function to process incoming messages.
        conn.datachannel.pub_sub.subscribe(RTC_TOPIC['LF_SPORT_MOD_STATE'], sportmodestatus_callback)

        # Keep the program running to allow event handling for 1 hour.
        await asyncio.sleep(3600)

    except KeyboardInterrupt:
        # Handle Ctrl+C to exit gracefully within the async context
        print("\n\nProgram interrupted by user")
        if differences:
            print("\nFinal Statistics:")
            print(f"Total samples: {sample_count}")
            final_avg = sum(differences) / len(differences)
            print(f"Final averaged deviation: {final_avg * 1000:.3f} ms")
            if len(differences) > 1:
                variance = sum((x - final_avg) ** 2 for x in differences) / len(differences)
                print(f"Final standard deviation: {(variance ** 0.5) * 1000:.3f} ms")
            print(f"Min difference: {min(differences) * 1000:.3f} ms")
            print(f"Max difference: {max(differences) * 1000:.3f} ms")
    except ValueError as e:
        # Log any value errors that occur during the process.
        logging.error(f"An error occurred: {e}")
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
