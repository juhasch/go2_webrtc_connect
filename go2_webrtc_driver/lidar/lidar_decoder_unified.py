"""
Unified LiDAR Decoder Module

This module provides a unified interface for LiDAR data decoding that can switch between
different decoder implementations. It supports both WebAssembly-based (libvoxel) and 
native Python decoders, allowing users to choose the most appropriate decoder for their
use case.

The unified decoder automatically handles initialization and provides a consistent API
regardless of the underlying decoder implementation.

Example:
    >>> # Use default native decoder
    >>> decoder = UnifiedLidarDecoder()
    >>> 
    >>> # Use libvoxel decoder instead
    >>> decoder = UnifiedLidarDecoder(decoder_type="libvoxel")
    >>> 
    >>> # Decode LiDAR data
    >>> result = decoder.decode(compressed_data, metadata)
    >>> print(f"Using {decoder.get_decoder_name()}")

Available Decoders:
    - native: Pure Python decoder (default; fast with Numba)
    - libvoxel: WebAssembly-based decoder
"""

from .lidar_decoder_libvoxel import LidarDecoder as LibVoxelDecoder
from .lidar_decoder_native import LidarDecoder as NativeDecoder


class UnifiedLidarDecoder:
    """
    Unified LiDAR decoder that provides a consistent interface for different decoder types.
    
    This class acts as a wrapper around different LiDAR decoder implementations, allowing
    users to switch between decoders without changing their code. It supports both
    WebAssembly-based and native Python decoders.
    
    Attributes:
        decoder: The underlying decoder instance
        decoder_name: Name of the currently selected decoder
    
    Supported Decoder Types:
        - "native": Pure Python decoder implementation
        - "libvoxel": WebAssembly-based decoder using libvoxel.wasm
    """
    
    def __init__(self, decoder_type="native"):
        """
        Initialize the UnifiedLidarDecoder with the specified decoder type.

        Args:
            decoder_type (str): The type of decoder to use. Must be either "native" 
                              or "libvoxel". Defaults to "native".
        
        Raises:
            ValueError: If decoder_type is not "libvoxel" or "native".
        
        Example:
            >>> # Use default native decoder
            >>> decoder = UnifiedLidarDecoder()
            >>> 
            >>> # Use libvoxel decoder
            >>> decoder = UnifiedLidarDecoder(decoder_type="libvoxel")
        """
        if decoder_type == "libvoxel":
            self.decoder = LibVoxelDecoder()
            self.decoder_name = "LibVoxelDecoder"
        elif decoder_type == "native":
            self.decoder = NativeDecoder()
            self.decoder_name = "NativeDecoder"
        else:
            raise ValueError(f"Invalid decoder type '{decoder_type}'. Choose 'libvoxel' or 'native'.")

    def decode(self, compressed_data, metadata):
        """
        Decode the compressed LiDAR data using the selected decoder.

        Args:
            compressed_data (bytes): The compressed LiDAR data to decode.
            metadata (dict): Metadata required for decoding, typically containing:
                           - origin: Origin coordinates [x, y, z]
                           - resolution: Voxel resolution
                           - Additional decoder-specific parameters

        Returns:
            The decoded result from the selected decoder. The exact format depends on
            the decoder implementation but typically includes point cloud data.
        
        Raises:
            Exception: If decoding fails due to invalid data or metadata.
        
        Example:
            >>> metadata = {
            ...     'origin': [0.0, 0.0, 0.0],
            ...     'resolution': 0.1
            ... }
            >>> result = decoder.decode(compressed_data, metadata)
        """
        return self.decoder.decode(compressed_data, metadata)

    def get_decoder_name(self):
        """
        Get the name of the currently selected decoder.

        Returns:
            str: Name of the decoder (e.g., "LibVoxelDecoder" or "NativeDecoder").
        
        Example:
            >>> decoder = UnifiedLidarDecoder("native")
            >>> print(decoder.get_decoder_name())
            'NativeDecoder'
        """
        return self.decoder_name