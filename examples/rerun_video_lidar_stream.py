#!/usr/bin/env python3
"""
Combined Video and LIDAR Visualization with Rerun
Combines functionality from rerun_lidar_stream.py and display_video_channel.py
"""

import numpy as np
import argparse
import csv
import ast
import sys
import logging
import rerun as rr
import asyncio
import threading
import time
from queue import Queue
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.lidar.point_cloud_accumulator import (
    create_accumulator_from_args,
    add_accumulation_args,
    process_points_with_accumulation,
)
from aiortc import MediaStreamTrack
from datetime import datetime

# Logging configuration
logging.basicConfig(level=logging.FATAL)
logging.getLogger('aiortc.codecs.h264').setLevel(logging.ERROR)

# Increase the field size limit for CSV reading
csv.field_size_limit(sys.maxsize)

# Initialize Rerun
rr.init("go2_video_lidar_realtime", spawn=True)

VERSION = "1.0.3"

# LIDAR Constants
ROTATE_X_ANGLE = 0.0  # No rotation around X
ROTATE_Z_ANGLE = 0.0  # No rotation around Z
MAX_RETRY_ATTEMPTS = 10
ENABLE_POINT_CLOUD = True
ENABLE_VIDEO = True
RADII_FUDGE_FACTOR = 10.0  # Adjust this factor to change point size in Rerun

# Global variables
minYValue = -1000  # Much wider default range
maxYValue = 1000
lidar_message_count = 0
video_frame_count = 0
reconnect_interval = 5  # Time (seconds) before retrying connection

# Rate calculation variables
lidar_start_time = None
video_start_time = None
last_lidar_rate_log = None
last_video_rate_log = None
RATE_LOG_INTERVAL = 5.0  # Log rates every 5 seconds

# File paths for CSV writing
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LIDAR_CSV_FILE = f"lidar_data_{timestamp}.csv"

# Global CSV variables
lidar_csv_file = None
lidar_csv_writer = None

# Global queues and flags
frame_queue = Queue()
stop_flag = threading.Event()

# Global accumulator
accumulator = None

# Parse command-line arguments
parser = argparse.ArgumentParser(description=f"Combined Video+LIDAR Viz v{VERSION}")
parser.add_argument("--version", action="version", version=f"Combined Video+LIDAR Viz v{VERSION}")
parser.add_argument("--csv-read", type=str, help="Read from CSV files instead of WebRTC")
parser.add_argument("--csv-write", action="store_true", help="Write CSV data file when using WebRTC")
parser.add_argument("--skip-mod", type=int, default=1, help="Skip LIDAR messages using modulus (default: 1, no skipping)")
parser.add_argument('--minYValue', type=int, default=-1000, help='Minimum Y value for LIDAR filtering (default: -1000)')
parser.add_argument('--maxYValue', type=int, default=1000, help='Maximum Y value for LIDAR filtering (default: 1000)')
parser.add_argument('--disable-video', action="store_true", help='Disable video stream')
parser.add_argument('--disable-lidar', action="store_true", help='Disable LIDAR stream')
parser.add_argument('--no-y-filter', action="store_true", help='Disable Y-value filtering to see full field of view')

# Add accumulation arguments
add_accumulation_args(parser)

args = parser.parse_args()

minYValue = args.minYValue
maxYValue = args.maxYValue

if args.disable_video:
    ENABLE_VIDEO = False
if args.disable_lidar:
    ENABLE_POINT_CLOUD = False

def setup_csv_output():
    """Set up CSV files for LIDAR output."""
    global lidar_csv_file, lidar_csv_writer

    if args.csv_write and ENABLE_POINT_CLOUD:
        lidar_csv_file = open(LIDAR_CSV_FILE, mode='w', newline='', encoding='utf-8')
        lidar_csv_writer = csv.writer(lidar_csv_file)
        lidar_csv_writer.writerow(['stamp', 'frame_id', 'resolution', 'src_size', 'origin', 'width', 
                                   'point_count', 'positions'])
        lidar_csv_file.flush()
        print(f"CSV output enabled: {LIDAR_CSV_FILE}")

def close_csv_output():
    """Close CSV files."""
    global lidar_csv_file

    if lidar_csv_file:
        lidar_csv_file.close()
        lidar_csv_file = None

def rotate_points(points, x_angle, z_angle):
    """Rotate points around X and Z axes."""
    rotation_matrix_x = np.array([
        [1, 0, 0],
        [0, np.cos(x_angle), -np.sin(x_angle)],
        [0, np.sin(x_angle), np.cos(x_angle)]
    ])
    rotation_matrix_z = np.array([
        [np.cos(z_angle), -np.sin(z_angle), 0],
        [np.sin(z_angle), np.cos(z_angle), 0],
        [0, 0, 1]
    ])
    points = points @ rotation_matrix_x.T
    points = points @ rotation_matrix_z.T
    return points

def process_single_frame(points: np.ndarray, message_data: dict, csv_writer=None, csv_file=None) -> None:
    """Process a single frame without accumulation (original behavior)."""
    global lidar_message_count
    
    total_points = len(points)
    unique_points = np.unique(points, axis=0)

    # Save to CSV if requested
    if csv_writer:
        csv_writer.writerow([
            message_data.get("stamp", ""),
            message_data.get("frame_id", ""),
            message_data.get("resolution", ""),
            message_data.get("src_size", ""),
            message_data.get("origin", ""),
            message_data.get("width", ""),
            len(unique_points),
            unique_points.tolist()
        ])
        if csv_file:
            csv_file.flush()

    if unique_points.size > 0:
        points = rotate_points(unique_points, ROTATE_X_ANGLE, ROTATE_Z_ANGLE)
        
        # Apply Y-value filtering only if not disabled
        if not args.no_y_filter:
            points = points[(points[:, 1] >= minYValue) & (points[:, 1] <= maxYValue)]
            unique_points = np.unique(points, axis=0)
        
        if unique_points.size > 0:
            center_x = float(np.mean(unique_points[:, 0]))
            center_y = float(np.mean(unique_points[:, 1]))
            center_z = float(np.mean(unique_points[:, 2]))
            offset_points = unique_points - np.array([center_x, center_y, center_z])
        else:
            offset_points = np.empty((0, 3), dtype=np.float32)
    else:
        unique_points = np.empty((0, 3), dtype=np.float32)
        offset_points = unique_points

    # Color by height (z) and log to Rerun
    if offset_points.shape[0] > 0:
        z = offset_points[:, 2]
        z_min, z_max = z.min(), z.max()
        norm_z = (z - z_min) / (z_max - z_min + 1e-6)

        # Vivid rainbow colormap (HSV hue from blue->red)
        hue = (2.0 / 3.0) * (1.0 - norm_z)
        saturation = np.ones_like(hue)
        value = np.ones_like(hue)

        hh = hue * 6.0
        c = value * saturation
        x = c * (1.0 - np.abs((hh % 2.0) - 1.0))
        m = value - c

        sextant = np.floor(hh).astype(int) % 6
        r_prime = np.zeros_like(hue)
        g_prime = np.zeros_like(hue)
        b_prime = np.zeros_like(hue)

        mask0 = sextant == 0
        r_prime[mask0], g_prime[mask0], b_prime[mask0] = c[mask0], x[mask0], 0
        mask1 = sextant == 1
        r_prime[mask1], g_prime[mask1], b_prime[mask1] = x[mask1], c[mask1], 0
        mask2 = sextant == 2
        r_prime[mask2], g_prime[mask2], b_prime[mask2] = 0, c[mask2], x[mask2]
        mask3 = sextant == 3
        r_prime[mask3], g_prime[mask3], b_prime[mask3] = 0, x[mask3], c[mask3]
        mask4 = sextant == 4
        r_prime[mask4], g_prime[mask4], b_prime[mask4] = x[mask4], 0, c[mask4]
        mask5 = sextant == 5
        r_prime[mask5], g_prime[mask5], b_prime[mask5] = c[mask5], 0, x[mask5]

        r = ((r_prime + m) * 255.0).clip(0, 255).astype(np.uint8)
        g = ((g_prime + m) * 255.0).clip(0, 255).astype(np.uint8)
        b = ((b_prime + m) * 255.0).clip(0, 255).astype(np.uint8)
        colors = np.stack([r, g, b], axis=1)
        radii = np.full(offset_points.shape[0], 0.05, dtype=np.float32) * RADII_FUDGE_FACTOR
        rr.log("lidar/points", rr.Points3D(offset_points, colors=colors, radii=radii))

    lidar_message_count += 1
    print(f"LIDAR Message {lidar_message_count}: Total points={total_points}, Unique points={len(unique_points)}")

def process_accumulated_cloud(accumulated_points: np.ndarray) -> None:
    """Process accumulated point cloud."""
    # Apply Y-value filtering only if not disabled
    if not args.no_y_filter:
        filtered_points = accumulated_points[(accumulated_points[:, 1] >= minYValue) & 
                                           (accumulated_points[:, 1] <= maxYValue)]
    else:
        filtered_points = accumulated_points
    
    if filtered_points.size == 0:
        return
    
    # Center the points
    center_x = float(np.mean(filtered_points[:, 0]))
    center_y = float(np.mean(filtered_points[:, 1]))
    center_z = float(np.mean(filtered_points[:, 2]))
    offset_points = filtered_points - np.array([center_x, center_y, center_z])
    
    # Color by height (z) and log to Rerun
    z = offset_points[:, 2]
    z_min, z_max = z.min(), z.max()
    norm_z = (z - z_min) / (z_max - z_min + 1e-6)

    # Vivid rainbow colormap (HSV hue from blue->red)
    hue = (2.0 / 3.0) * (1.0 - norm_z)
    saturation = np.ones_like(hue)
    value = np.ones_like(hue)

    hh = hue * 6.0
    c = value * saturation
    x = c * (1.0 - np.abs((hh % 2.0) - 1.0))
    m = value - c

    sextant = np.floor(hh).astype(int) % 6
    r_prime = np.zeros_like(hue)
    g_prime = np.zeros_like(hue)
    b_prime = np.zeros_like(hue)

    mask0 = sextant == 0
    r_prime[mask0], g_prime[mask0], b_prime[mask0] = c[mask0], x[mask0], 0
    mask1 = sextant == 1
    r_prime[mask1], g_prime[mask1], b_prime[mask1] = x[mask1], c[mask1], 0
    mask2 = sextant == 2
    r_prime[mask2], g_prime[mask2], b_prime[mask2] = 0, c[mask2], x[mask2]
    mask3 = sextant == 3
    r_prime[mask3], g_prime[mask3], b_prime[mask3] = 0, x[mask3], c[mask3]
    mask4 = sextant == 4
    r_prime[mask4], g_prime[mask4], b_prime[mask4] = x[mask4], 0, c[mask4]
    mask5 = sextant == 5
    r_prime[mask5], g_prime[mask5], b_prime[mask5] = c[mask5], 0, x[mask5]

    r = ((r_prime + m) * 255.0).clip(0, 255).astype(np.uint8)
    g = ((g_prime + m) * 255.0).clip(0, 255).astype(np.uint8)
    b = ((b_prime + m) * 255.0).clip(0, 255).astype(np.uint8)
    colors = np.stack([r, g, b], axis=1)
    radii = np.full(offset_points.shape[0], 0.05, dtype=np.float32) * RADII_FUDGE_FACTOR
    
    rr.log("lidar/accumulated_points", rr.Points3D(offset_points, colors=colors, radii=radii))
    
    print(f"Published accumulated cloud: {len(filtered_points)} points")

async def recv_camera_stream(track: MediaStreamTrack):
    """Receive video frames and log them to Rerun."""
    global video_frame_count, video_start_time, last_video_rate_log
    try:
        while not stop_flag.is_set():
            frame = await track.recv()
            # Convert the frame to a NumPy array
            img = frame.to_ndarray(format="rgb24")  # Use RGB for Rerun
            
            # Log the video frame to Rerun
            rr.log("camera/image", rr.Image(img))
            
            video_frame_count += 1
            current_time = time.time()
            
            # Initialize timing on first frame
            if video_start_time is None:
                video_start_time = current_time
                last_video_rate_log = current_time
            
            # Calculate and log video rate periodically
            if current_time - last_video_rate_log >= RATE_LOG_INTERVAL:
                elapsed_time = current_time - video_start_time
                if elapsed_time > 0:
                    video_rate = video_frame_count / elapsed_time
                    print(f"[DEBUG] Video rate: {video_rate:.2f} fps (frames: {video_frame_count}, elapsed: {elapsed_time:.2f}s)")
                last_video_rate_log = current_time
            
            if video_frame_count % 30 == 0:  # Print every 30 frames
                print(f"Video Frame {video_frame_count}: {img.shape}")
                
    except asyncio.CancelledError:
        print("Video stream cancelled")
        return
    except Exception as e:
        logging.error(f"Error receiving video frame: {e}")
        return

async def lidar_callback_task(message):
    """Task to process incoming LIDAR data."""
    if not ENABLE_POINT_CLOUD:
        return

    try:
        global lidar_message_count, lidar_start_time, last_lidar_rate_log
        
        print(f"[DEBUG] LIDAR callback called - message_count: {lidar_message_count}")
        
        current_time = time.time()
        
        # Initialize timing on first message
        if lidar_start_time is None:
            lidar_start_time = current_time
            last_lidar_rate_log = current_time
        
        if lidar_message_count % args.skip_mod != 0:
            lidar_message_count += 1
            print(f"[DEBUG] Skipping message {lidar_message_count} due to skip_mod={args.skip_mod}")
            return

        # Calculate and log LIDAR rate periodically
        if current_time - last_lidar_rate_log >= RATE_LOG_INTERVAL:
            elapsed_time = current_time - lidar_start_time
            if elapsed_time > 0:
                # Calculate effective rate (accounting for skip_mod)
                effective_messages = lidar_message_count // args.skip_mod
                lidar_rate = effective_messages / elapsed_time
                total_rate = lidar_message_count / elapsed_time
                print(f"[DEBUG] LIDAR rate: {lidar_rate:.2f} processed/s, {total_rate:.2f} total/s (processed: {effective_messages}, total: {lidar_message_count}, elapsed: {elapsed_time:.2f}s)")
            last_lidar_rate_log = current_time

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
        
        print(f"[DEBUG] Raw points length: {len(points)}")
        
        # Process points with accumulation if enabled
        process_points_with_accumulation(
            points=points,
            message_data=message["data"],
            accumulator=accumulator,
            single_frame_callback=process_single_frame,
            accumulated_callback=process_accumulated_cloud,
            csv_writer=lidar_csv_writer,
            csv_file=lidar_csv_file
        )

    except Exception as e:
        logging.error(f"Error in LIDAR callback: {e}")
        import traceback
        traceback.print_exc()

async def webrtc_connection():
    """Connect to WebRTC and process both video and LIDAR data."""
    retry_attempts = 0
    conn = None

    while retry_attempts < MAX_RETRY_ATTEMPTS and not stop_flag.is_set():
        try:
            conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
     
            # Connect to WebRTC
            logging.info("Connecting to WebRTC...")
            await conn.connect()
            logging.info("Connected to WebRTC.")
            print("Connected to WebRTC for live video and LIDAR data...")
            retry_attempts = 0

            # Set up video stream
            if ENABLE_VIDEO:
                conn.video.switchVideoChannel(True)
                conn.video.add_track_callback(recv_camera_stream)
                print("Video stream enabled")

            # Set up LIDAR stream
            if ENABLE_POINT_CLOUD:
                # Disable traffic saving mode
                await conn.datachannel.disableTrafficSaving(True)
                
                # Set the decoder type (this was missing!)
                conn.datachannel.set_decoder(decoder_type='libvoxel')
                
                # Turn LIDAR sensor on
                conn.datachannel.pub_sub.publish_without_callback("rt/utlidar/switch", "on")
                
                # Subscribe to LIDAR voxel map messages
                conn.datachannel.pub_sub.subscribe(
                    "rt/utlidar/voxel_map_compressed",
                    lambda message: asyncio.create_task(lidar_callback_task(message))
                )
                print("LIDAR stream enabled")

            # Set up CSV outputs if requested
            setup_csv_output()

            # Keep the connection active
            while not stop_flag.is_set():
                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print("\nProgram interrupted by user")
            break
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            logging.info(f"Reconnecting in {reconnect_interval} seconds... (Attempt {retry_attempts + 1}/{MAX_RETRY_ATTEMPTS})")
            retry_attempts += 1
        finally:
            # Ensure proper cleanup
            close_csv_output()
            if conn:
                try:
                    await conn.disconnect()
                    print("WebRTC connection closed successfully")
                except Exception as e:
                    logging.error(f"Error during disconnect: {e}")
            
            if retry_attempts >= MAX_RETRY_ATTEMPTS:
                break
                
            if retry_attempts > 0 and not stop_flag.is_set():
                await asyncio.sleep(reconnect_interval)

    if retry_attempts >= MAX_RETRY_ATTEMPTS:
        logging.error("Max retry attempts reached. Exiting.")

async def read_csv_and_emit(csv_file):
    """Read LIDAR data from CSV file and emit to Rerun."""
    global lidar_message_count, lidar_start_time, last_lidar_rate_log
    print(f"Reading CSV file: {csv_file}")
    try:
        with open(csv_file, mode='r', newline='', encoding='utf-8') as lidar_file:
            lidar_reader = csv.DictReader(lidar_file)
            for lidar_row in lidar_reader:
                if stop_flag.is_set():
                    break
                
                current_time = time.time()
                
                # Initialize timing on first message
                if lidar_start_time is None:
                    lidar_start_time = current_time
                    last_lidar_rate_log = current_time
                    
                if lidar_message_count % args.skip_mod == 0:
                    # Calculate and log LIDAR rate periodically
                    if current_time - last_lidar_rate_log >= RATE_LOG_INTERVAL:
                        elapsed_time = current_time - lidar_start_time
                        if elapsed_time > 0:
                            # Calculate effective rate (accounting for skip_mod)
                            effective_messages = lidar_message_count // args.skip_mod
                            lidar_rate = effective_messages / elapsed_time
                            total_rate = lidar_message_count / elapsed_time
                            print(f"[DEBUG] CSV LIDAR rate: {lidar_rate:.2f} processed/s, {total_rate:.2f} total/s (processed: {effective_messages}, total: {lidar_message_count}, elapsed: {elapsed_time:.2f}s)")
                        last_lidar_rate_log = current_time
                        
                    try:
                        positions = ast.literal_eval(lidar_row.get("positions", "[]"))
                        if isinstance(positions, list) and all(isinstance(item, list) and len(item) == 3 for item in positions):
                            points = np.array(positions, dtype=np.float32)
                        else:
                            points = np.array([item for item in positions if isinstance(item, list) and len(item) == 3], dtype=np.float32)
                        
                        # Process points with accumulation if enabled
                        process_points_with_accumulation(
                            points=points,
                            message_data=lidar_row,
                            accumulator=accumulator,
                            single_frame_callback=process_single_frame,
                            accumulated_callback=process_accumulated_cloud,
                            csv_writer=None,
                            csv_file=None
                        )
                        
                        # Add a small delay for visualization
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        logging.error(f"Exception during processing: {e}")
                        
                lidar_message_count += 1
                
    except Exception as e:
        logging.error(f"Error reading CSV file: {e}")

def run_asyncio_loop(loop):
    """Run the asyncio event loop in a separate thread."""
    asyncio.set_event_loop(loop)
    
    async def setup_and_run():
        try:
            if args.csv_read:
                # Offline mode: Read from CSV file
                await read_csv_and_emit(args.csv_read)
            else:
                # Online mode: Connect to WebRTC
                await webrtc_connection()
        except Exception as e:
            logging.error(f"Error in async setup: {e}")

    try:
        loop.run_until_complete(setup_and_run())
    except Exception as e:
        logging.error(f"Event loop error: {e}")
    finally:
        loop.close()

def main():
    """Main function to coordinate video and LIDAR streaming."""
    global stop_flag, accumulator
    
    print(f"Combined Video+LIDAR Visualization v{VERSION}")
    print(f"Video enabled: {ENABLE_VIDEO}")
    print(f"LIDAR enabled: {ENABLE_POINT_CLOUD}")
    
    # Create accumulator if accumulation is enabled
    accumulator = create_accumulator_from_args(args)
    if accumulator:
        print(f"Point cloud accumulation enabled: max_clouds={accumulator.max_clouds}, "
              f"max_age={accumulator.max_age_seconds}s, voxel_size={accumulator.voxel_size}m")
    
    if args.csv_read:
        print(f"Reading from CSV: {args.csv_read}")
    else:
        print("Starting live WebRTC streaming...")

    # Create a new event loop for the asyncio code
    loop = asyncio.new_event_loop()

    # Start the asyncio event loop in a separate thread
    asyncio_thread = threading.Thread(target=run_asyncio_loop, args=(loop,))
    asyncio_thread.start()

    try:
        # Main thread just waits for keyboard interrupt
        print("Press Ctrl+C to exit...")
        while not stop_flag.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_flag.set()
    finally:
        # Signal stop and wait for asyncio thread to finish
        stop_flag.set()
        
        # Wait for thread to finish gracefully
        if asyncio_thread.is_alive():
            asyncio_thread.join(timeout=5.0)
            if asyncio_thread.is_alive():
                print("Warning: AsyncIO thread did not stop cleanly")
        
        # Cleanup CSV files if still open
        close_csv_output()
        print("Cleanup complete")

if __name__ == "__main__":
    main() 