""" @MrRobotoW at The RoboVerse Discord """
""" robert.wagoner@gmail.com """
""" 01/30/2025 """
""" Inspired from lidar_stream.py by @legion1581 at The RoboVerse Discord """

import numpy as np
import argparse
import csv
import ast
import sys
import logging
import rerun as rr
import asyncio
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from datetime import datetime
import os

logging.basicConfig(level=logging.FATAL)

# Increase the field size limit for CSV reading
csv.field_size_limit(sys.maxsize)

rr.init("go2_lidar_points3d", spawn=True)

VERSION = "1.0.18"

ROTATE_X_ANGLE = 0.0  # No rotation around X
ROTATE_Z_ANGLE = 0.0  # No rotation around Z

# Constants
MAX_RETRY_ATTEMPTS = 10
ENABLE_POINT_CLOUD = True

# Global variables
minYValue = 0
maxYValue = 100
RADII_FUDGE_FACTOR = 10.0 # Adjust this factor to change point size in Rerun
message_count = 0
reconnect_interval = 5  # Time (seconds) before retrying connection

# File paths for CSV writing
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LIDAR_CSV_FILE = f"lidar_data_{timestamp}.csv"

# Global CSV variables
lidar_csv_file = None
lidar_csv_writer = None

# Parse command-line arguments
parser = argparse.ArgumentParser(description=f"LIDAR Viz v{VERSION}")
parser.add_argument("--version", action="version", version=f"LIDAR Viz v{VERSION}")
parser.add_argument("--csv-read", type=str, help="Read from CSV files instead of WebRTC")
parser.add_argument("--csv-write", action="store_true", help="Write CSV data file when using WebRTC")
parser.add_argument("--skip-mod", type=int, default=1, help="Skip messages using modulus (default: 1, no skipping)")
parser.add_argument('--minYValue', type=int, default=0, help='Minimum Y value for the plot')
parser.add_argument('--maxYValue', type=int, default=100, help='Maximum Y value for the plot')
args = parser.parse_args()

minYValue = args.minYValue
maxYValue = args.maxYValue

def setup_csv_output():
    """Set up CSV files for LIDAR output."""
    global lidar_csv_file, lidar_csv_writer

    if args.csv_write:
        lidar_csv_file = open(LIDAR_CSV_FILE, mode='w', newline='', encoding='utf-8')
        lidar_csv_writer = csv.writer(lidar_csv_file)
        lidar_csv_writer.writerow(['stamp', 'frame_id', 'resolution', 'src_size', 'origin', 'width', 
                                   'point_count', 'positions'])
        lidar_csv_file.flush()  # Ensure the header row is flushed to disk
        print(f"CSV output enabled: {LIDAR_CSV_FILE}")

def close_csv_output():
    """Close CSV files."""
    global lidar_csv_file

    if lidar_csv_file:
        lidar_csv_file.close()
        lidar_csv_file = None

def rotate_points(points, x_angle, z_angle):
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

async def lidar_webrtc_connection():
    """Connect to WebRTC and process LIDAR data."""
    global message_count
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

            # Turn LIDAR sensor on
            conn.datachannel.pub_sub.publish_without_callback("rt/utlidar/switch", "on")

            # Set up CSV outputs if requested
            setup_csv_output()

            async def lidar_callback_task(message):
                """Task to process incoming LIDAR data."""
                if not ENABLE_POINT_CLOUD:
                    return

                try:
                    global message_count
                    if message_count % args.skip_mod != 0:
                        message_count += 1
                        return

                    positions = message["data"]["data"].get("positions", [])
                    origin = message["data"].get("origin", [])
                    points = np.array([positions[i:i+3] for i in range(0, len(positions), 3)], dtype=np.float32)
                    total_points = len(points)
                    unique_points = np.unique(points, axis=0)

                    # Save to CSV if requested
                    if args.csv_write and lidar_csv_writer:
                        lidar_csv_writer.writerow([
                            message["data"]["stamp"],
                            message["data"]["frame_id"],
                            message["data"]["resolution"],
                            message["data"]["src_size"],
                            message["data"]["origin"],
                            message["data"]["width"],
                            len(unique_points),
                            unique_points.tolist()  # Save full data
                        ])
                        lidar_csv_file.flush()  # Flush data to disk

                    if unique_points.size > 0:
                        points = rotate_points(unique_points, ROTATE_X_ANGLE, ROTATE_Z_ANGLE)
                        # Apply Y-value filtering
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
                        colors = np.stack([
                            (norm_z * 255).astype(np.uint8),
                            np.full_like(norm_z, 128, dtype=np.uint8),
                            (255 - norm_z * 255).astype(np.uint8)
                        ], axis=1)
                        radii = np.full(offset_points.shape[0], 0.05, dtype=np.float32) * RADII_FUDGE_FACTOR
                        rr.log("lidar/points", rr.Points3D(offset_points, colors=colors, radii=radii))

                    message_count += 1
                    print(f"LIDAR Message {message_count}: Total points={total_points}, Unique points={len(unique_points)}")

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
            close_csv_output()
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

async def read_csv_and_emit(csv_file):
    global message_count
    print(f"Reading CSV file: {csv_file}")
    try:
        # Calculate total messages (count lines minus header)
        with open(csv_file, mode='r', newline='', encoding='utf-8') as f_count:
            total_messages = sum(1 for _ in f_count) -1
        
        with open(csv_file, mode='r', newline='', encoding='utf-8') as lidar_file:
            lidar_reader = csv.DictReader(lidar_file)
            for lidar_row in lidar_reader:
                if message_count % args.skip_mod == 0:
                    try:
                        positions = ast.literal_eval(lidar_row.get("positions", "[]"))
                        if isinstance(positions, list) and all(isinstance(item, list) and len(item) == 3 for item in positions):
                            points = np.array(positions, dtype=np.float32)
                        else:
                            points = np.array([item for item in positions if isinstance(item, list) and len(item) == 3], dtype=np.float32)
                        origin = np.array(eval(lidar_row.get("origin", "[]")), dtype=np.float32)
                        resolution = float(lidar_row.get("resolution", 0.05))
                        width = np.array(eval(lidar_row.get("width", "[128, 128, 38]")), dtype=np.float32)
                        center = origin + (width * resolution) / 2
                        if points.size > 0:
                            points = rotate_points(points, ROTATE_X_ANGLE, ROTATE_Z_ANGLE)
                            # Apply Y-value filtering
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
                        # Color by height (z)
                        if offset_points.shape[0] > 0:
                            z = offset_points[:, 2]
                            z_min, z_max = z.min(), z.max()
                            norm_z = (z - z_min) / (z_max - z_min + 1e-6)
                            colors = np.stack([
                                (norm_z * 255).astype(np.uint8),
                                np.full_like(norm_z, 128, dtype=np.uint8),
                                (255 - norm_z * 255).astype(np.uint8)
                            ], axis=1)
                            radii = np.full(offset_points.shape[0], 0.05, dtype=np.float32) * RADII_FUDGE_FACTOR
                            rr.log("lidar/points", rr.Points3D(offset_points, colors=colors, radii=radii))
                        print(f"LIDAR Message {message_count}/{total_messages}: Unique points={len(unique_points)}")
                    except Exception as e:
                        logging.error(f"Exception during processing: {e}")
                message_count += 1
    except Exception as e:
        logging.error(f"Error reading CSV file: {e}")

def start_webrtc():
    """Run WebRTC connection in a separate asyncio loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(lidar_webrtc_connection())

if __name__ == "__main__":
    import threading
    try:
        if args.csv_read:
            # Offline mode: Read from CSV file
            csv_thread = threading.Thread(target=lambda: asyncio.run(read_csv_and_emit(args.csv_read)), daemon=True)
            csv_thread.start()
            csv_thread.join()
        else:
            # Online mode: Connect to WebRTC
            print("Starting online WebRTC LIDAR streaming...")
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
        close_csv_output()
    finally:
        # Cleanup CSV files if still open
        close_csv_output()
