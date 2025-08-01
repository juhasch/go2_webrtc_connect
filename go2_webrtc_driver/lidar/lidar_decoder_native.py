# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Native LiDAR Data Decoder for Unitree Go2 Robot

This module provides a native Python implementation for decoding compressed LiDAR point cloud data
from the Unitree Go2 robot. The decoder handles LZ4-compressed voxel data and converts it to
3D point clouds using bit manipulation and coordinate transformation.

The native decoder is a pure Python implementation that:
- Decompresses LZ4-compressed voxel data
- Converts bit-packed voxel data to 3D points
- Applies coordinate transformations and scaling
- Provides efficient point cloud processing

Key Components:
- LZ4 decompression for compressed voxel data
- Bit-level parsing of voxel occupancy grid
- Coordinate transformation from voxel to world coordinates
- Configurable resolution and origin parameters

Usage Example:
    ```python
    from go2_webrtc_driver.lidar.lidar_decoder_native import LidarDecoder
    
    # Initialize decoder
    decoder = LidarDecoder()
    
    # Decode compressed LiDAR data
    result = decoder.decode(compressed_data, {
        "src_size": 12000,
        "origin": [0.0, 0.0, 0.0],
        "resolution": 0.05
    })
    
    # Access point cloud
    points = result["points"]
    print(f"Decoded {len(points)} points")
    ```

Technical Details:
- Uses LZ4 block decompression for efficient data decompression
- Voxel grid is represented as bit-packed bytes
- Each bit represents voxel occupancy (0=empty, 1=occupied)
- 3D coordinates are calculated using bit manipulation and indexing
- Default resolution is 0.05 meters (5cm voxels)

Author: Unitree Robotics
Version: 1.0
"""

import numpy as np
import lz4.block
from typing import Dict, Any, List, Tuple, Union


def decompress(compressed_data: bytes, decomp_size: int) -> bytes:
    """
    Decompress LZ4-compressed voxel data
    
    Args:
        compressed_data (bytes): LZ4-compressed voxel data from LiDAR
        decomp_size (int): Expected size of decompressed data in bytes
        
    Returns:
        bytes: Decompressed voxel data as raw bytes
        
    Raises:
        lz4.block.LZ4BlockError: If decompression fails
        ValueError: If decomp_size is invalid
        
    Example:
        ```python
        # Decompress LiDAR voxel data
        decompressed = decompress(compressed_bytes, 12000)
        print(f"Decompressed {len(decompressed)} bytes")
        ```
        
    Note:
        This function uses LZ4 block decompression which is optimized for speed.
        The decomp_size parameter must match the original uncompressed size.
    """
    decompressed = lz4.block.decompress(
        compressed_data,
        uncompressed_size=decomp_size
    )
    return decompressed


def bits_to_points(buf: bytes, origin: List[float], resolution: float = 0.05) -> np.ndarray:
    """
    Convert bit-packed voxel data to 3D point cloud
    
    This function processes a bit-packed voxel grid where each bit represents
    the occupancy of a voxel in 3D space. It extracts occupied voxels and
    converts their indices to world coordinates.
    
    Args:
        buf (bytes): Raw voxel data as bytes where each bit represents voxel occupancy
        origin (List[float]): 3D origin coordinates [x, y, z] in meters
        resolution (float): Voxel resolution in meters per voxel. Default: 0.05 (5cm)
        
    Returns:
        np.ndarray: Array of 3D points with shape (N, 3) where N is number of occupied voxels
        
    Example:
        ```python
        # Convert voxel data to points
        origin = [0.0, 0.0, 0.0]
        points = bits_to_points(voxel_data, origin, 0.05)
        print(f"Generated {len(points)} points")
        print(f"First point: {points[0]}")
        ```
        
    Technical Details:
        - Voxel grid layout: z-major, y-minor, x-minor bit ordering
        - Each byte contains 8 voxels in x-direction
        - Grid dimensions: 16x128x256 (x, y, z) = 0x800 slices
        - Bit 7 (MSB) represents lowest x-coordinate in the byte
        - Coordinates are transformed: voxel_coord * resolution + origin
        
    Note:
        The voxel indexing follows the pattern:
        - z = n // 0x800 (slice index)
        - y = (n % 0x800) // 0x10 (row within slice)
        - x = ((n % 0x800) % 0x10) * 8 + bit_position (column)
    """
    buf = np.frombuffer(bytearray(buf), dtype=np.uint8)
    nonzero_indices = np.nonzero(buf)[0]
    points = []

    for n in nonzero_indices:
        byte_value = buf[n]
        z = n // 0x800
        n_slice = n % 0x800
        y = n_slice // 0x10
        x_base = (n_slice % 0x10) * 8

        for bit_pos in range(8):
            if byte_value & (1 << (7 - bit_pos)):
                x = x_base + bit_pos
                points.append((x, y, z))

    return np.array(points) * resolution + origin


class LidarDecoder:
    """
    Native LiDAR Data Decoder for Unitree Go2 Robot
    
    This class provides a native Python implementation for decoding compressed
    LiDAR point cloud data from the Unitree Go2 robot. It handles LZ4-compressed
    voxel data and converts it to 3D point clouds.
    
    The decoder processes voxel occupancy grids that are:
    - Compressed using LZ4 block compression
    - Bit-packed with 8 voxels per byte
    - Organized in a 3D grid structure
    - Converted to world coordinates using resolution and origin
    
    Example:
        ```python
        # Initialize decoder
        decoder = LidarDecoder()
        
        # Decode LiDAR data
        metadata = {
            "src_size": 12000,
            "origin": [0.0, 0.0, 0.0],
            "resolution": 0.05
        }
        result = decoder.decode(compressed_data, metadata)
        
        # Access decoded points
        points = result["points"]
        print(f"Decoded {len(points)} points")
        ```
    """
    
    def decode(self, compressed_data: bytes, data: Dict[str, Any]) -> Dict[str, np.ndarray]:
        """
        Decode compressed LiDAR voxel data to 3D point cloud
        
        This method decompresses LZ4-compressed voxel data and converts it to
        a 3D point cloud using the provided metadata parameters.
        
        Args:
            compressed_data (bytes): LZ4-compressed voxel data from LiDAR sensor
            data (Dict[str, Any]): Metadata dictionary containing:
                - src_size (int): Size of decompressed data in bytes
                - origin (List[float]): 3D origin coordinates [x, y, z] in meters
                - resolution (float): Voxel resolution in meters per voxel
                
        Returns:
            Dict[str, np.ndarray]: Dictionary containing:
                - points (np.ndarray): 3D point cloud with shape (N, 3)
                
        Raises:
            KeyError: If required metadata fields are missing
            lz4.block.LZ4BlockError: If decompression fails
            ValueError: If metadata values are invalid
            
        Example:
            ```python
            decoder = LidarDecoder()
            
            # Prepare metadata
            metadata = {
                "src_size": 12000,
                "origin": [0.0, 0.0, 0.0],
                "resolution": 0.05
            }
            
            # Decode data
            result = decoder.decode(compressed_bytes, metadata)
            points = result["points"]
            
            # Process points
            print(f"Point cloud shape: {points.shape}")
            print(f"Min coordinates: {points.min(axis=0)}")
            print(f"Max coordinates: {points.max(axis=0)}")
            ```
            
        Note:
            The returned points are in world coordinates (meters) after applying
            the resolution scaling and origin translation.
        """
        def points():
            decompressed = decompress(compressed_data, data["src_size"])
            points = bits_to_points(decompressed, data["origin"], data["resolution"])
            return points

        return {
            "points": points(),
            # "raw": compressed_data,  # Commented out to save memory
        }
