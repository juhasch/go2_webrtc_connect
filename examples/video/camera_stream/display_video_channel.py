import cv2
import numpy as np

import asyncio
import logging
import threading
import time
from queue import Queue
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from aiortc import MediaStreamTrack

# Enable logging for debugging
logging.basicConfig(level=logging.FATAL)

# Suppress aiortc H264 decoder warnings
logging.getLogger('aiortc.codecs.h264').setLevel(logging.ERROR)

def main():
    frame_queue = Queue()
    stop_flag = threading.Event()  # Flag to signal when to stop

    # Choose a connection method (uncomment the correct one)
    conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)

    # Preflight: exit early if ROBOT_IP is missing for LocalSTA
    if conn.connectionMethod == WebRTCConnectionMethod.LocalSTA and not conn.ip:
        logging.error("ROBOT_IP is not set. Please export ROBOT_IP or pass an IP.")
        stop_flag.set()
        return

    # Create an OpenCV window and display a blank image
    height, width = 720, 1280  # Adjust the size as needed
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.imshow('Video', img)
    cv2.waitKey(1)  # Ensure the window is created

    # Async function to receive video frames and put them in the queue
    async def recv_camera_stream(track: MediaStreamTrack):
        try:
            while not stop_flag.is_set():
                frame = await track.recv()
                # Convert the frame to a NumPy array
                img = frame.to_ndarray(format="bgr24")
                frame_queue.put(img)
        except asyncio.CancelledError:
            print("Video stream cancelled")
            return
        except Exception as e:
            logging.error(f"Error receiving video frame: {e}")
            return

    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)
        async def setup_and_run():
            try:
                # Connect to the device
                await conn.connect()

                # Switch video channel on and start receiving video frames
                conn.video.switchVideoChannel(True)

                # Add callback to handle received video frames
                conn.video.add_track_callback(recv_camera_stream)
                
                # Keep the loop running until stop is requested
                while not stop_flag.is_set():
                    await asyncio.sleep(0.1)
                
                # Disconnect when stopping
                print("Disconnecting WebRTC...")
                await conn.disconnect()
                print("WebRTC disconnected")
                    
            except Exception as e:
                logging.error(f"Error in WebRTC connection: {e}")
                # Try to disconnect even if there was an error
                try:
                    await conn.disconnect()
                except Exception:
                    pass
                # Signal main loop to stop on connection failure
                stop_flag.set()

        # Run the setup coroutine and then start the event loop
        try:
            loop.run_until_complete(setup_and_run())
        except Exception as e:
            logging.error(f"Event loop error: {e}")
            # Ensure main loop exits on event loop errors
            stop_flag.set()
        finally:
            loop.close()

    # Create a new event loop for the asyncio code
    loop = asyncio.new_event_loop()

    # Start the asyncio event loop in a separate thread
    asyncio_thread = threading.Thread(target=run_asyncio_loop, args=(loop,))
    asyncio_thread.start()

    try:
        while not stop_flag.is_set():
            if not frame_queue.empty():
                img = frame_queue.get()
                # Display the frame
                cv2.imshow('Video', img)
            
            # Check for 'q' key press regardless of frame availability
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Exiting...")
                stop_flag.set()  # Signal async tasks to stop
                break
            
            if frame_queue.empty():
                # Sleep briefly to prevent high CPU usage when no frames
                time.sleep(0.01)
    finally:
        cv2.destroyAllWindows()
        
        # Signal stop and wait for asyncio thread to finish
        print("Shutting down...")
        stop_flag.set()
        
        # Wait for thread to finish gracefully
        if asyncio_thread.is_alive():
            asyncio_thread.join(timeout=3.0)
            if asyncio_thread.is_alive():
                print("Warning: AsyncIO thread did not stop cleanly")
        
        print("Cleanup complete")

if __name__ == "__main__":
    main()
