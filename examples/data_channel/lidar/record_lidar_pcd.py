""" @MrRobotoW at The RoboVerse Discord """
""" robert.wagoner@gmail.com """
""" 01/30/2025 """
""" LIDAR recording script using pypcd for PCD file output """

import numpy as np
import argparse
import sys
import logging
import asyncio
import os
from datetime import datetime
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.lidar.point_cloud_accumulator import (
    create_accumulator_from_args,
    add_accumulation_args,
    process_points_with_accumulation,
)

# Try to import pypcd, provide helpful error if not available
try:
    import pypcd
except ImportError:
    print("Error: pypcd library not found.")
    print("Install it with: pip install pypcd")
    print("For compressed PCD support, also install: pip install python-lzf")
    sys.exit(1)

logging.basicConfig(level=logging.FATAL)

VERSION = "1.0.0"

# Constants
MAX_RETRY_ATTEMPTS = 10
ENABLE_POINT_CLOUD = True

# Global variables
minYValue = -1000  # Much wider default range
maxYValue = 1000
message_count = 0
reconnect_interval = 5  # Time (seconds) before retrying connection

# File paths for PCD output
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LIDAR_PCD_DIR = f"lidar_recordings_{timestamp}"
LIDAR_PCD_FILE = f"lidar_frame_{timestamp}.pcd"

# Global variables
pcd_dir = None
frame_count = 0
accumulator = None

# Parse command-line arguments
parser = argparse.ArgumentParser(description=f"LIDAR PCD Recorder v{VERSION}")
parser.add_argument("--version", action="version", version=f"LIDAR PCD Recorder v{VERSION}")
parser.add_argument("--output-dir", type=str, default=LIDAR_PCD_DIR, help="Output directory for PCD files")
parser.add_argument("--skip-mod", type=int, default=1, help="Skip messages using modulus (default: 1, no skipping)")
parser.add_argument('--minYValue', type=int, default=-1000, help='Minimum Y value for the plot (default: -1000)')
parser.add_argument('--maxYValue', type=int, default=1000, help='Maximum Y value for the plot (default: 1000)')
parser.add_argument('--no-y-filter', action="store_true", help='Disable Y-value filtering to see full field of view')
parser.add_argument('--compression', type=str, default='binary_compressed', 
                   choices=['ascii', 'binary', 'binary_compressed'], 
                   help='PCD compression format (default: binary_compressed)')
parser.add_argument('--save-every', type=int, default=1, 
                   help='Save PCD file every N frames (default: 1, save every frame)')
parser.add_argument('--accumulate-frames', type=int, default=0,
                   help='Accumulate N frames before saving (0 = no accumulation, default: 0)')

# Add accumulation arguments
add_accumulation_args(parser)

args = parser.parse_args()

minYValue = args.minYValue
maxYValue = args.maxYValue

def setup_pcd_output():
    """Set up output directory for PCD files."""
    global pcd_dir
    
    pcd_dir = args.output_dir
    if not os.path.exists(pcd_dir):
        os.makedirs(pcd_dir)
        print(f"Created output directory: {pcd_dir}")
    else:
        print(f"Using existing output directory: {pcd_dir}")

def save_points_to_pcd(points: np.ndarray, filename: str) -> None:
    """Save points to PCD file using pypcd."""
    if points.size == 0:
        print(f"Warning: No points to save for {filename}")
        return
    
    try:
        # Create structured array for pypcd
        # pypcd expects points with x, y, z fields
        dtype = np.dtype([('x', np.float32), ('y', np.float32), ('z', np.float32)])
        structured_points = np.zeros(len(points), dtype=dtype)
        structured_points['x'] = points[:, 0]
        structured_points['y'] = points[:, 1]
        structured_points['z'] = points[:, 2]
        
        # Use pypcd's from_array method which handles metadata automatically
        pc = pypcd.PointCloud.from_array(structured_points)
        
        # Save PCD file
        filepath = os.path.join(pcd_dir, filename)
        pc.save_pcd(filepath, compression=args.compression)
        print(f"Saved PCD file: {filepath} ({len(points)} points)")
        
    except Exception as e:
        print(f"Error saving PCD file {filename}: {e}")

def process_single_frame(points: np.ndarray, message_data: dict, csv_writer=None, csv_file=None) -> None:
    """Process a single frame and save to PCD if needed."""
    global message_count, frame_count
    
    total_points = len(points)
    unique_points = np.unique(points, axis=0)

    if unique_points.size > 0:
        # Apply Y-value filtering only if not disabled
        if not args.no_y_filter:
            filtered_points = unique_points[(unique_points[:, 1] >= minYValue) & 
                                         (unique_points[:, 1] <= maxYValue)]
        else:
            filtered_points = unique_points
        
        if filtered_points.size > 0:
            # Save PCD file if we've reached the save interval
            if frame_count % args.save_every == 0:
                timestamp_str = datetime.now().strftime("%H%M%S_%f")[:-3]  # Include milliseconds
                filename = f"lidar_frame_{timestamp_str}.pcd"
                save_points_to_pcd(filtered_points, filename)
            
            frame_count += 1

    message_count += 1
    print(f"LIDAR Message {message_count}: Total points={total_points}, Unique points={len(unique_points)}, Frame count={frame_count}")

def process_accumulated_cloud(accumulated_points: np.ndarray) -> None:
    """Process accumulated point cloud and save to PCD."""
    # Apply Y-value filtering only if not disabled
    if not args.no_y_filter:
        filtered_points = accumulated_points[(accumulated_points[:, 1] >= minYValue) & 
                                           (accumulated_points[:, 1] <= maxYValue)]
    else:
        filtered_points = accumulated_points
    
    if filtered_points.size == 0:
        return
    
    # Save accumulated cloud to PCD
    timestamp_str = datetime.now().strftime("%H%M%S_%f")[:-3]
    filename = f"lidar_accumulated_{timestamp_str}.pcd"
    save_points_to_pcd(filtered_points, filename)
    
    print(f"Published accumulated cloud: {len(filtered_points)} points")

async def lidar_webrtc_connection():
    """Connect to WebRTC and process LIDAR data."""
    global message_count, accumulator
    retry_attempts = 0
    conn = None

    while retry_attempts < MAX_RETRY_ATTEMPTS:
        try:
            conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)  # WebRTC IP
     
            # Connect to WebRTC
            logging.info("Connecting to WebRTC...")
            await conn.connect()
            logging.info("Connected to WebRTC.")
            print("Connected to WebRTC for live LIDAR data...")
            retry_attempts = 0  # Reset retry attempts on successful connection

            # Disable traffic saving mode
            await conn.datachannel.disableTrafficSaving(True)

            # Set the decoder type to native
            conn.datachannel.set_decoder(decoder_type='native')

            # Turn LIDAR sensor on
            conn.datachannel.pub_sub.publish_without_callback("rt/utlidar/switch", "on")

            # Set up PCD output directory
            setup_pcd_output()

            async def lidar_callback_task(message):
                """Task to process incoming LIDAR data."""
                if not ENABLE_POINT_CLOUD:
                    return

                try:
                    global message_count
                    if message_count % args.skip_mod != 0:
                        message_count += 1
                        return

                    # Handle both libvoxel and native decoder formats
                    data = message["data"]["data"]
                    
                    # Check if using native decoder (returns "points") or libvoxel decoder (returns "positions")
                    if "points" in data:
                        # Native decoder format
                        points = data["points"]
                        if callable(points):
                            points = points()  # Call the function to get the actual points
                        points = np.array(points, dtype=np.float32)
                    else:
                        # Libvoxel decoder format
                        positions = data.get("positions", [])
                        points = np.array([positions[i:i+3] for i in range(0, len(positions), 3)], dtype=np.float32)
                    
                    # Process points with accumulation if enabled
                    process_points_with_accumulation(
                        points=points,
                        message_data=message["data"],
                        accumulator=accumulator,
                        single_frame_callback=process_single_frame,
                        accumulated_callback=process_accumulated_cloud,
                        csv_writer=None,
                        csv_file=None
                    )

                    message_count += 1

                except Exception as e:
                    logging.error(f"Error in LIDAR callback: {e}")

            # Subscribe to LIDAR voxel map messages
            conn.datachannel.pub_sub.subscribe(
                "rt/utlidar/voxel_map_compressed",
                lambda message: asyncio.create_task(lidar_callback_task(message))
            )

            # Keep the connection active
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            # Handle Ctrl+C to exit gracefully within the async context
            print("\nProgram interrupted by user")
            break
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            logging.info(f"Reconnecting in {reconnect_interval} seconds... (Attempt {retry_attempts + 1}/{MAX_RETRY_ATTEMPTS})")
            retry_attempts += 1
        finally:
            # Ensure proper cleanup
            if conn:
                try:
                    await conn.disconnect()
                    print("WebRTC connection closed successfully")
                except Exception as e:
                    logging.error(f"Error during disconnect: {e}")
            
            if retry_attempts >= MAX_RETRY_ATTEMPTS:
                break
                
            if retry_attempts > 0:
                await asyncio.sleep(reconnect_interval)

    if retry_attempts >= MAX_RETRY_ATTEMPTS:
        logging.error("Max retry attempts reached. Exiting.")

def start_webrtc():
    """Run WebRTC connection in a separate asyncio loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(lidar_webrtc_connection())

if __name__ == "__main__":
    import threading
    
    # Create accumulator if accumulation is enabled
    accumulator = create_accumulator_from_args(args)
    
    # Override accumulator settings if --accumulate-frames is specified
    if args.accumulate_frames > 0:
        if accumulator:
            accumulator.max_frames = args.accumulate_frames
            print(f"Accumulating {args.accumulate_frames} frames before saving")
        else:
            print("Warning: --accumulate-frames specified but no accumulator created")
    
    try:
        print("Starting LIDAR PCD recording...")
        print(f"Output directory: {args.output_dir}")
        print(f"Compression format: {args.compression}")
        print(f"Save every {args.save_every} frame(s)")
        if args.accumulate_frames > 0:
            print(f"Accumulate {args.accumulate_frames} frames before saving")
        
        webrtc_thread = threading.Thread(target=start_webrtc, daemon=True)
        webrtc_thread.start()
        
        # Keep main thread alive
        try:
            while True:
                asyncio.run(asyncio.sleep(1))
        except KeyboardInterrupt:
            print("\nProgram interrupted by user")
            
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    finally:
        print(f"\nLIDAR recording complete. PCD files saved to: {args.output_dir}")
        print(f"Total frames processed: {frame_count}")
        print(f"Total messages received: {message_count}")
