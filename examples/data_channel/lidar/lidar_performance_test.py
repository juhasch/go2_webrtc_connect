""" @MrRobotoW at The RoboVerse Discord """
""" robert.wagoner@gmail.com """
""" 01/30/2025 """
""" Minimal LIDAR decoding performance test fixture """

import asyncio
import argparse
import logging
import time
import statistics
import numpy as np
from typing import Dict, Any, List
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.lidar.lidar_decoder_unified import UnifiedLidarDecoder

# Configure logging for minimal output
logging.basicConfig(level=logging.FATAL)

VERSION = "1.0.0"

class TimedDecoderWrapper:
    """
    Wrapper around decoder to measure actual decoding time.
    """
    
    def __init__(self, decoder, timing_list):
        self.decoder = decoder
        self.timing_list = timing_list
    
    def decode(self, compressed_data, metadata):
        """Decode with timing measurement."""
        start_time = time.time()
        result = self.decoder.decode(compressed_data, metadata)
        decode_time = time.time() - start_time
        self.timing_list.append(decode_time)
        return result

class LidarPerformanceTest:
    """
    Minimal test fixture for LIDAR decoding performance optimization.
    
    This class focuses solely on decoding performance and data validation
    without any display or storage functionality.
    """
    
    def __init__(self, decoder_type: str = "libvoxel"):
        """
        Initialize the performance test fixture.
        
        Args:
            decoder_type: Type of decoder to use ("libvoxel" or "native")
        """
        self.decoder_type = decoder_type
        self.decoder = UnifiedLidarDecoder(decoder_type)
        self.message_count = 0
        self.decoding_times = []
        self.validation_errors = 0
        self.total_bytes_processed = 0
        self.start_time = None
        
        # Create a timed decoder wrapper
        self.timed_decoder = TimedDecoderWrapper(self.decoder, self.decoding_times)
        
    def validate_lidar_data(self, message: Dict[str, Any]) -> bool:
        """
        Validate received LIDAR data for correctness.
        
        Args:
            message: Decoded LIDAR message
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        try:
            # Check basic message structure
            if not isinstance(message, dict):
                print(f"❌ Invalid message type: {type(message)}")
                return False
                
            # Check for required top-level fields
            if "data" not in message:
                print(f"❌ Missing 'data' field in message")
                return False
                
            data = message["data"]
            
            # Check for required data fields
            required_fields = ["stamp", "frame_id", "resolution", "src_size", "origin", "width"]
            for field in required_fields:
                if field not in data:
                    print(f"❌ Missing required field '{field}' in data")
                    return False
            
            # Validate metadata types and ranges
            if not isinstance(data["stamp"], (int, float)):
                print(f"❌ Invalid stamp type: {type(data['stamp'])}")
                return False
                
            if not isinstance(data["frame_id"], str):
                print(f"❌ Invalid frame_id type: {type(data['frame_id'])}")
                return False
                
            if not isinstance(data["resolution"], (int, float)) or data["resolution"] <= 0:
                print(f"❌ Invalid resolution: {data['resolution']}")
                return False
                
            if not isinstance(data["src_size"], int) or data["src_size"] <= 0:
                print(f"❌ Invalid src_size: {data['src_size']}")
                return False
                
            if not isinstance(data["origin"], list) or len(data["origin"]) != 3:
                print(f"❌ Invalid origin format: {data['origin']}")
                return False
                
            if not isinstance(data["width"], list) or len(data["width"]) != 3:
                print(f"❌ Invalid width format: {data['width']}")
                return False
            
            # Check for decoded data
            if "data" not in data:
                print(f"❌ Missing decoded data field")
                print(f"   Available fields: {list(data.keys())}")
                return False
                
            decoded_data = data["data"]
            
            # Debug: Print the structure of decoded_data
            print(f"🔍 Decoded data structure: {type(decoded_data)}")
            if isinstance(decoded_data, dict):
                print(f"   Keys: {list(decoded_data.keys())}")
                for key, value in decoded_data.items():
                    print(f"   {key}: {type(value)} = {value if not hasattr(value, 'shape') else f'shape{value.shape}'}")
            else:
                print(f"   Value: {decoded_data}")
            
            # Validate decoded data based on decoder type
            if self.decoder_type == "libvoxel":
                # LibVoxel decoder returns mesh data
                required_decoded_fields = ["point_count", "face_count", "positions", "uvs", "indices"]
                for field in required_decoded_fields:
                    if field not in decoded_data:
                        print(f"❌ Missing decoded field '{field}' for libvoxel")
                        return False
                        
                # Validate point and face counts
                if not isinstance(decoded_data["point_count"], int) or decoded_data["point_count"] < 0:
                    print(f"❌ Invalid point_count: {decoded_data['point_count']}")
                    return False
                    
                if not isinstance(decoded_data["face_count"], int) or decoded_data["face_count"] < 0:
                    print(f"❌ Invalid face_count: {decoded_data['face_count']}")
                    return False
                    
                # Validate array data - positions is a numpy array of uint8
                if not isinstance(decoded_data["positions"], np.ndarray):
                    print(f"❌ Invalid positions type: {type(decoded_data['positions'])} (expected numpy.ndarray)")
                    return False
                    
                if decoded_data["positions"].size == 0:
                    print(f"❌ Empty positions array")
                    return False
                    
                # Validate uvs array
                if not isinstance(decoded_data["uvs"], np.ndarray):
                    print(f"❌ Invalid uvs type: {type(decoded_data['uvs'])} (expected numpy.ndarray)")
                    return False
                    
                # Validate indices array
                if not isinstance(decoded_data["indices"], np.ndarray):
                    print(f"❌ Invalid indices type: {type(decoded_data['indices'])} (expected numpy.ndarray)")
                    return False
                    
                # Print detailed info for debugging
                print(f"✅ LibVoxel data: points={decoded_data['point_count']}, faces={decoded_data['face_count']}, positions.shape={decoded_data['positions'].shape}, uvs.shape={decoded_data['uvs'].shape}, indices.shape={decoded_data['indices'].shape}")
                    
            elif self.decoder_type == "native":
                # Native decoder returns point cloud data
                if "points" not in decoded_data:
                    print(f"❌ Missing 'points' field for native decoder")
                    return False
                    
                points = decoded_data["points"]
                if not isinstance(points, (list, tuple, np.ndarray)) or len(points) == 0:
                    print(f"❌ Invalid points array type: {type(points)}")
                    return False
                    
                # Validate point structure (should be 3D coordinates)
                if isinstance(points, np.ndarray):
                    if points.ndim != 2 or points.shape[1] != 3:
                        print(f"❌ Invalid points array shape: {points.shape} (expected (N, 3))")
                        return False
                    print(f"✅ Native data: points.shape={points.shape}, dtype={points.dtype}")
                else:
                    # Check first 10 points for list/tuple format
                    for i, point in enumerate(points[:10]):
                        if not isinstance(point, (list, tuple)) or len(point) != 3:
                            print(f"❌ Invalid point structure at index {i}: {point}")
                            return False
                            
                        for coord in point:
                            if not isinstance(coord, (int, float)):
                                print(f"❌ Invalid coordinate type: {type(coord)}")
                                return False
                    print(f"✅ Native data: points count={len(points)}")
            
            # All validations passed
            return True
            
        except Exception as e:
            print(f"❌ Validation error: {e}")
            return False
    
    def print_performance_stats(self):
        """Print current performance statistics."""
        if not self.decoding_times:
            return
            
        avg_time = statistics.mean(self.decoding_times)
        min_time = min(self.decoding_times)
        max_time = max(self.decoding_times)
        median_time = statistics.median(self.decoding_times)
        
        if self.start_time:
            elapsed = time.time() - self.start_time
            throughput = self.total_bytes_processed / elapsed if elapsed > 0 else 0
            
            print(f"\n📊 Performance Statistics:")
            print(f"   Messages processed: {self.message_count}")
            print(f"   Total bytes: {self.total_bytes_processed:,}")
            print(f"   Elapsed time: {elapsed:.2f}s")
            print(f"   Throughput: {throughput/1024:.1f} KB/s")
            print(f"   Validation errors: {self.validation_errors}")
            print(f"   Decoding times (ms):")
            print(f"     Average: {avg_time*1000:.2f}")
            print(f"     Median:  {median_time*1000:.2f}")
            print(f"     Min:     {min_time*1000:.2f}")
            print(f"     Max:     {max_time*1000:.2f}")
            print(f"     Std Dev: {statistics.stdev(self.decoding_times)*1000:.2f}")
    
    async def lidar_callback(self, message: Dict[str, Any]):
        """
        Process incoming LIDAR data for performance testing.
        
        Args:
            message: Decoded LIDAR message
        """
        try:
            # Record message count
            self.message_count += 1
            
            # Validate the data (no timing for validation)
            is_valid = self.validate_lidar_data(message)
            
            # Track bytes processed (approximate)
            if "data" in message and "data" in message["data"]:
                decoded_data = message["data"]["data"]
                if self.decoder_type == "libvoxel":
                    # Estimate bytes from array sizes
                    if "positions" in decoded_data:
                        self.total_bytes_processed += len(decoded_data["positions"])
                    if "indices" in decoded_data:
                        self.total_bytes_processed += len(decoded_data["indices"]) * 4
                elif self.decoder_type == "native":
                    if "points" in decoded_data:
                        self.total_bytes_processed += len(decoded_data["points"]) * 12  # 3 floats * 4 bytes
            
            # Report validation errors
            if not is_valid:
                self.validation_errors += 1
                print(f"❌ Message {self.message_count} failed validation")
            else:
                # Print progress every 10 messages with latest decoding time
                if self.message_count % 10 == 0:
                    latest_decode_time = self.decoding_times[-1] if self.decoding_times else 0
                    print(f"✅ Message {self.message_count}: Valid data, decode: {latest_decode_time*1000:.2f}ms")
                    
        except Exception as e:
            print(f"❌ Error processing message {self.message_count}: {e}")
            self.validation_errors += 1

async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description=f"LIDAR Performance Test v{VERSION}")
    parser.add_argument("--decoder", choices=["libvoxel", "native"], default="libvoxel",
                       help="Decoder type to test (default: libvoxel)")
    parser.add_argument("--duration", type=int, default=60,
                       help="Test duration in seconds (default: 60)")
    args = parser.parse_args()
    
    print(f"🚀 Starting LIDAR Performance Test v{VERSION}")
    print(f"   Decoder: {args.decoder}")
    print(f"   Duration: {args.duration}s")
    print(f"   Press Ctrl+C to stop early\n")
    
    # Initialize test fixture
    test = LidarPerformanceTest(args.decoder)
    test.start_time = time.time()
    
    conn = None
    try:
        # Connect to WebRTC
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        await conn.connect()
        print("✅ Connected to WebRTC")
        
        # Disable traffic saving for full bandwidth
        await conn.datachannel.disableTrafficSaving(True)
        print("✅ Traffic saving disabled")
        
        # Set decoder type and inject timed decoder
        conn.datachannel.set_decoder(decoder_type=args.decoder)
        # Replace the decoder with our timed wrapper
        conn.datachannel.decoder = test.timed_decoder
        print(f"✅ Using {args.decoder} decoder with timing")
        
        # Turn LIDAR sensor on
        conn.datachannel.pub_sub.publish_without_callback("rt/utlidar/switch", "on")
        print("✅ LIDAR sensor enabled")
        
        # Subscribe to LIDAR data
        conn.datachannel.pub_sub.subscribe(
            "rt/utlidar/voxel_map_compressed",
            lambda message: asyncio.create_task(test.lidar_callback(message))
        )
        print("✅ Subscribed to LIDAR data")
        print(f"📡 Receiving data for {args.duration} seconds...\n")
        
        # Run for specified duration
        await asyncio.sleep(args.duration)
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
    finally:
        # Print final statistics
        test.print_performance_stats()
        
        # Cleanup
        if conn:
            try:
                await conn.disconnect()
                print("✅ WebRTC connection closed")
            except Exception as e:
                print(f"❌ Error closing connection: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Program interrupted by user")
    except Exception as e:
        print(f"\n❌ Program error: {e}") 