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
LibVoxel WebAssembly-based LiDAR Data Decoder for Unitree Go2 Robot

This module provides a WebAssembly-based implementation for decoding compressed LiDAR point cloud data
from the Unitree Go2 robot. It uses the libvoxel.wasm module for high-performance voxel processing,
mesh generation, and point cloud reconstruction.

The LibVoxel decoder offers advanced features:
- WebAssembly-based high-performance processing
- Comprehensive mesh generation (vertices, UVs, indices)
- Advanced decompression and voxel-to-mesh conversion
- Memory-efficient processing with pre-allocated buffers
- Support for complex 3D reconstruction algorithms

Key Components:
- WebAssembly runtime using wasmtime
- Memory management with ctypes arrays
- Mesh generation with positions, UVs, and indices
- Advanced voxel processing algorithms
- Optimized memory allocation and buffer management

Technical Features:
- Uses libvoxel.wasm for core processing
- Generates mesh data including vertices, texture coordinates, and face indices
- Supports complex 3D reconstruction from voxel data
- Provides callbacks for memory management
- Handles large point clouds efficiently

Usage Example:
    ```python
    from go2_webrtc_driver.lidar.lidar_decoder_libvoxel import LidarDecoder
    
    # Initialize decoder (loads WebAssembly module)
    decoder = LidarDecoder()
    
    # Decode compressed LiDAR data
    result = decoder.decode(compressed_data, {
        "origin": [0.0, 0.0, 0.0],
        "resolution": 0.05
    })
    
    # Access decoded mesh data
    print(f"Generated {result['point_count']} points")
    print(f"Generated {result['face_count']} faces")
    positions = result['positions']
    indices = result['indices']
    ```

Performance Considerations:
- WebAssembly provides near-native performance
- Pre-allocated memory buffers reduce allocation overhead
- Optimized for large-scale point cloud processing
- Memory-efficient handling of mesh data

Requirements:
- wasmtime Python package
- libvoxel.wasm file in the same directory
- numpy for array processing
- ctypes for memory management

Author: Unitree Robotics
Version: 1.0
"""

import math
import ctypes
import numpy as np
import os
from typing import Dict, Any, List, Union

from wasmtime import Config, Engine, Store, Module, Instance, Func, FuncType
from wasmtime import ValType


class LidarDecoder:
    """
    WebAssembly-based LiDAR Data Decoder using LibVoxel
    
    This class provides a high-performance WebAssembly-based decoder for processing
    compressed LiDAR point cloud data from the Unitree Go2 robot. It uses the
    libvoxel.wasm module for advanced voxel processing and mesh generation.
    
    The decoder handles:
    - WebAssembly module loading and initialization
    - Memory management with pre-allocated buffers
    - Voxel decompression and mesh generation
    - Advanced 3D reconstruction algorithms
    - Efficient data transfer between Python and WebAssembly
    
    Key Features:
    - High-performance WebAssembly processing
    - Mesh generation with vertices, UVs, and indices
    - Memory-efficient buffer management
    - Callback-based memory operations
    - Support for complex point cloud reconstruction
    
    Memory Layout:
    - input: 61440 bytes (60KB) - Input compressed data
    - decompressBuffer: 80000 bytes (80KB) - Decompression buffer
    - positions: 2880000 bytes (2.8MB) - Vertex positions
    - uvs: 1920000 bytes (1.9MB) - Texture coordinates
    - indices: 5760000 bytes (5.7MB) - Face indices
    
    Example:
        ```python
        # Initialize decoder
        decoder = LidarDecoder()
        
        # Decode LiDAR data
        result = decoder.decode(compressed_data, {
            "origin": [0.0, 0.0, 0.0],
            "resolution": 0.05
        })
        
        # Process mesh data
        positions = result['positions']
        indices = result['indices']
        face_count = result['face_count']
        ```
    """
    
    def __init__(self) -> None:
        """
        Initialize the LibVoxel WebAssembly decoder
        
        This method sets up the WebAssembly runtime, loads the libvoxel.wasm module,
        and initializes memory buffers for processing. It creates callback functions
        for memory management and sets up typed arrays for efficient data access.
        
        The initialization process:
        1. Configures WebAssembly engine with multi-value support
        2. Loads libvoxel.wasm module from the same directory
        3. Creates callback functions for memory operations
        4. Instantiates the WebAssembly module
        5. Maps WebAssembly memory to Python arrays
        6. Allocates buffers for input, decompression, and output data
        
        Raises:
            FileNotFoundError: If libvoxel.wasm is not found
            wasmtime.WasmtimeError: If WebAssembly initialization fails
            MemoryError: If memory allocation fails
            
        Example:
            ```python
            # Initialize decoder
            decoder = LidarDecoder()
            print("LibVoxel decoder initialized successfully")
            ```
            
        Note:
            This initialization is relatively expensive due to WebAssembly module loading.
            Consider reusing the decoder instance for multiple decode operations.
        """
        config = Config()
        config.wasm_multi_value = True
        config.debug_info = True
        self.store = Store(Engine(config))

        wasm_path = os.path.join(os.path.dirname(__file__), "libvoxel.wasm")
        self.module = Module.from_file(self.store.engine, wasm_path)

        # Define callback function types for memory management
        self.a_callback_type = FuncType([ValType.i32()], [ValType.i32()])
        self.b_callback_type = FuncType([ValType.i32(), ValType.i32(), ValType.i32()], [])

        # Create callback functions
        a = Func(self.store, self.a_callback_type, self.adjust_memory_size)
        b = Func(self.store, self.b_callback_type, self.copy_memory_region)

        # Instantiate WebAssembly module with callbacks
        self.instance = Instance(self.store, self.module, [a, b])

        # Get exported functions from WebAssembly module
        self.generate = self.instance.exports(self.store)["e"]  # Main processing function
        self.malloc = self.instance.exports(self.store)["f"]    # Memory allocation
        self.free = self.instance.exports(self.store)["g"]      # Memory deallocation
        self.wasm_memory = self.instance.exports(self.store)["c"]  # Memory object

        # Map WebAssembly memory to Python
        self.buffer = self.wasm_memory.data_ptr(self.store)
        self.memory_size = self.wasm_memory.data_len(self.store)
        self.buffer_ptr = int.from_bytes(self.buffer, "little")

        # Create typed arrays for efficient memory access
        self.HEAP8 = (ctypes.c_int8 * self.memory_size).from_address(self.buffer_ptr)
        self.HEAP16 = (ctypes.c_int16 * (self.memory_size // 2)).from_address(self.buffer_ptr)
        self.HEAP32 = (ctypes.c_int32 * (self.memory_size // 4)).from_address(self.buffer_ptr)
        self.HEAPU8 = (ctypes.c_uint8 * self.memory_size).from_address(self.buffer_ptr)
        self.HEAPU16 = (ctypes.c_uint16 * (self.memory_size // 2)).from_address(self.buffer_ptr)
        self.HEAPU32 = (ctypes.c_uint32 * (self.memory_size // 4)).from_address(self.buffer_ptr)
        self.HEAPF32 = (ctypes.c_float * (self.memory_size // 4)).from_address(self.buffer_ptr)
        self.HEAPF64 = (ctypes.c_double * (self.memory_size // 8)).from_address(self.buffer_ptr)

        # Allocate memory buffers for processing
        self.input = self.malloc(self.store, 61440)              # 60KB input buffer
        self.decompressBuffer = self.malloc(self.store, 80000)   # 80KB decompression buffer
        self.positions = self.malloc(self.store, 2880000)        # 2.8MB positions buffer
        self.uvs = self.malloc(self.store, 1920000)              # 1.9MB UVs buffer
        self.indices = self.malloc(self.store, 5760000)          # 5.7MB indices buffer
        self.decompressedSize = self.malloc(self.store, 4)       # 4B size storage
        self.faceCount = self.malloc(self.store, 4)              # 4B face count storage
        self.pointCount = self.malloc(self.store, 4)             # 4B point count storage
        self.decompressBufferSize = 80000

    def adjust_memory_size(self, t: int) -> int:
        """
        Callback function for WebAssembly memory size adjustment
        
        This callback is called by the WebAssembly module when it needs to
        query the current memory size. It returns the size of the HEAPU8 array.
        
        Args:
            t (int): Parameter from WebAssembly (unused)
            
        Returns:
            int: Current memory size in bytes
            
        Note:
            This is a callback function used by the WebAssembly runtime.
            It should not be called directly from Python code.
        """
        return len(self.HEAPU8)

    def copy_within(self, target: int, start: int, end: int) -> None:
        """
        Copy memory region within the WebAssembly heap
        
        This method copies a region of memory from [start:end] to the target location
        within the WebAssembly heap. It's used for efficient memory operations.
        
        Args:
            target (int): Target memory address to copy to
            start (int): Start address of source region
            end (int): End address of source region (exclusive)
            
        Raises:
            IndexError: If memory addresses are out of bounds
            
        Example:
            ```python
            # Copy 100 bytes from address 1000 to address 2000
            decoder.copy_within(2000, 1000, 1100)
            ```
            
        Note:
            This method operates on the WebAssembly heap memory directly.
            All addresses are byte offsets within the heap.
        """
        # Copy the sublist for the specified range [start:end]
        sublist = self.HEAPU8[start:end]

        # Replace elements in the list starting from index 'target'
        for i in range(len(sublist)):
            if target + i < len(self.HEAPU8):
                self.HEAPU8[target + i] = sublist[i]
    
    def copy_memory_region(self, t: int, n: int, a: int) -> None:
        """
        Callback function for WebAssembly memory region copying
        
        This callback is called by the WebAssembly module to copy memory regions.
        It uses the copy_within method to perform the actual memory copy.
        
        Args:
            t (int): Target memory address
            n (int): Source memory address
            a (int): Number of bytes to copy
            
        Note:
            This is a callback function used by the WebAssembly runtime.
            It should not be called directly from Python code.
        """
        self.copy_within(t, n, n + a)

    def get_value(self, t: int, n: str = "i8") -> Union[int, float]:
        """
        Get a value from WebAssembly memory with type conversion
        
        This method reads a value from the WebAssembly heap at the specified
        address and converts it to the appropriate Python type based on the
        type specifier.
        
        Args:
            t (int): Memory address to read from
            n (str): Type specifier. Options:
                - "i1", "i8": 8-bit signed integer
                - "i16": 16-bit signed integer
                - "i32", "i64": 32-bit signed integer
                - "float": 32-bit floating point
                - "double": 64-bit floating point
                - "*": Pointer (32-bit unsigned integer)
                
        Returns:
            Union[int, float]: Value read from memory, converted to appropriate type
            
        Raises:
            ValueError: If type specifier is invalid
            IndexError: If memory address is out of bounds
            
        Example:
            ```python
            # Read a 32-bit integer from address 1000
            value = decoder.get_value(1000, "i32")
            
            # Read a float from address 2000
            float_value = decoder.get_value(2000, "float")
            ```
            
        Note:
            Addresses are automatically adjusted based on type size for alignment.
            For example, 16-bit values use (address >> 1) for proper alignment.
        """
        if n.endswith("*"):
            n = "*"
        if n == "i1" or n == "i8":
            return self.HEAP8[t]
        elif n == "i16":
            return self.HEAP16[t >> 1]
        elif n == "i32" or n == "i64":
            return self.HEAP32[t >> 2]
        elif n == "float":
            return self.HEAPF32[t >> 2]
        elif n == "double":
            return self.HEAPF64[t >> 3]
        elif n == "*":
            return self.HEAPU32[t >> 2]
        else:
            raise ValueError(f"invalid type for getValue: {n}")
        
    def add_value_arr(self, start: int, value: bytes) -> None:
        """
        Add byte array to WebAssembly memory at specified address
        
        This method copies a byte array to the WebAssembly heap at the specified
        starting address. It's used to transfer data from Python to WebAssembly.
        
        Args:
            start (int): Starting memory address to write to
            value (bytes): Byte array to copy to memory
            
        Raises:
            ValueError: If there's not enough space at the specified address
            IndexError: If memory address is out of bounds
            
        Example:
            ```python
            # Copy compressed data to input buffer
            decoder.add_value_arr(decoder.input, compressed_data)
            ```
            
        Note:
            This method performs bounds checking to ensure the data fits
            within the available WebAssembly memory.
        """
        if start + len(value) <= len(self.HEAPU8):
            for i, byte in enumerate(value):
                self.HEAPU8[start + i] = byte
        else:
            raise ValueError("Not enough space to insert bytes at the specified index.")

    def decode(self, compressed_data: bytes, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decode compressed LiDAR voxel data to mesh representation
        
        This method processes compressed LiDAR data using the WebAssembly libvoxel
        module to generate a complete mesh representation including vertices, texture
        coordinates, and face indices.
        
        Args:
            compressed_data (bytes): Compressed voxel data from LiDAR sensor
            data (Dict[str, Any]): Metadata dictionary containing:
                - origin (List[float]): 3D origin coordinates [x, y, z] in meters
                - resolution (float): Voxel resolution in meters per voxel
                
        Returns:
            Dict[str, Any]: Dictionary containing decoded mesh data:
                - point_count (int): Number of generated points
                - face_count (int): Number of generated faces
                - positions (np.ndarray): Vertex positions as uint8 array
                - uvs (np.ndarray): Texture coordinates as uint8 array
                - indices (np.ndarray): Face indices as uint32 array
                
        Raises:
            ValueError: If input data is invalid or processing fails
            MemoryError: If WebAssembly memory operations fail
            KeyError: If required metadata fields are missing
            
        Example:
            ```python
            decoder = LidarDecoder()
            
            # Prepare metadata
            metadata = {
                "origin": [0.0, 0.0, 0.0],
                "resolution": 0.05
            }
            
            # Decode compressed data
            result = decoder.decode(compressed_data, metadata)
            
            # Access mesh data
            print(f"Generated {result['point_count']} points")
            print(f"Generated {result['face_count']} faces")
            
            # Process mesh components
            positions = result['positions']  # Vertex positions
            uvs = result['uvs']              # Texture coordinates
            indices = result['indices']      # Face indices
            ```
            
        Processing Pipeline:
        1. Copy compressed data to WebAssembly input buffer
        2. Calculate z-offset from origin and resolution
        3. Call WebAssembly generate function with all parameters
        4. Extract processing results (counts and arrays)
        5. Copy mesh data from WebAssembly to Python arrays
        6. Return structured mesh data
        
        Note:
            The WebAssembly module performs complex voxel-to-mesh conversion
            including decompression, voxel processing, and mesh generation.
            The returned arrays are in raw byte format and may need further
            processing for specific applications.
        """
        # Copy compressed data to WebAssembly input buffer
        self.add_value_arr(self.input, compressed_data)

        # Calculate z-offset based on origin and resolution
        some_v = math.floor(data["origin"][2] / data["resolution"])

        # Call WebAssembly generate function with all parameters
        self.generate(
            self.store,
            self.input,                    # Input compressed data
            len(compressed_data),          # Input data size
            self.decompressBufferSize,     # Decompression buffer size
            self.decompressBuffer,         # Decompression buffer
            self.decompressedSize,         # Output: decompressed size
            self.positions,                # Output: vertex positions
            self.uvs,                      # Output: texture coordinates
            self.indices,                  # Output: face indices
            self.faceCount,                # Output: face count
            self.pointCount,               # Output: point count
            some_v                         # Z-offset parameter
        )

        # Extract processing results
        self.get_value(self.decompressedSize, "i32")  # Decompressed size (unused)
        c = self.get_value(self.pointCount, "i32")    # Point count
        u = self.get_value(self.faceCount, "i32")     # Face count

        # Copy mesh data from WebAssembly to Python arrays
        positions_slice = self.HEAPU8[self.positions:self.positions + u * 12]
        positions_copy = bytearray(positions_slice)
        p = np.frombuffer(positions_copy, dtype=np.uint8)

        uvs_slice = self.HEAPU8[self.uvs:self.uvs + u * 8]
        uvs_copy = bytearray(uvs_slice)
        r = np.frombuffer(uvs_copy, dtype=np.uint8)

        indices_slice = self.HEAPU8[self.indices:self.indices + u * 24]
        indices_copy = bytearray(indices_slice)
        o = np.frombuffer(indices_copy, dtype=np.uint32)

        return {
            "point_count": c,
            "face_count": u,
            "positions": p,
            "uvs": r,
            "indices": o
        }
