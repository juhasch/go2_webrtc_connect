"""
Point Cloud Accumulator Module

This module provides point cloud accumulation functionality inspired by ROS2 cloud accumulation nodes.
It includes time-based accumulation, voxel filtering, height filtering, and configurable parameters.

Author: @MrRobotoW at The RoboVerse Discord
"""

import numpy as np
import time
from collections import deque
from typing import List, Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class CloudData:
    """Container for point cloud data with timestamp."""
    
    def __init__(self, points: np.ndarray, timestamp: float):
        self.points = points
        self.timestamp = timestamp


class PointCloudAccumulator:
    """
    Accumulates point clouds over time with filtering and deduplication.
    
    Inspired by ROS2 cloud accumulation nodes, this class provides:
    - Time-based accumulation (configurable max age)
    - Count-based accumulation (configurable max clouds)
    - Height filtering (Z-axis range)
    - Voxel grid deduplication
    - Configurable publish rate
    """
    
    def __init__(self, 
                 max_clouds: int = 30,
                 max_age_seconds: float = 2.0,
                 voxel_size: float = 0.05,
                 min_height: float = 0.2,
                 max_height: float = 1.0,
                 publish_rate: float = 10.0,
                 enable_logging: bool = True,
                 disable_height_filter: bool = False):
        """
        Initialize the point cloud accumulator.
        
        Args:
            max_clouds: Maximum number of clouds to accumulate
            max_age_seconds: Maximum age of clouds in seconds
            voxel_size: Voxel grid size for deduplication (meters)
            min_height: Minimum Z height for filtering (meters)
            max_height: Maximum Z height for filtering (meters)
            publish_rate: Rate to publish accumulated clouds (Hz)
            enable_logging: Whether to enable debug logging
            disable_height_filter: Whether to disable height filtering
        """
        self.max_clouds = max_clouds
        self.max_age_seconds = max_age_seconds
        self.voxel_size = voxel_size
        self.min_height = min_height
        self.max_height = max_height
        self.publish_rate = publish_rate
        self.enable_logging = enable_logging
        self.disable_height_filter = disable_height_filter
        
        # Storage
        self.cloud_buffer = deque()
        self.last_publish_time = 0.0
        
        if self.enable_logging:
            height_info = f"height_range=[{min_height}, {max_height}]m" if not disable_height_filter else "height_filter=disabled"
            logger.info(f"PointCloudAccumulator initialized: max_clouds={max_clouds}, "
                       f"max_age={max_age_seconds}s, voxel_size={voxel_size}m, "
                       f"{height_info}, publish_rate={publish_rate}Hz")
    
    def height_filter(self, points: np.ndarray) -> np.ndarray:
        """
        Filter points by height (Z-axis).
        
        Args:
            points: Input point cloud (Nx3 array)
            
        Returns:
            Filtered point cloud
        """
        if points.size == 0 or self.disable_height_filter:
            return points
        
        # Filter by Z height
        mask = (points[:, 2] >= self.min_height) & (points[:, 2] <= self.max_height)
        filtered_points = points[mask]
        
        if self.enable_logging and len(points) != len(filtered_points):
            logger.debug(f"Height filtering: {len(points)} -> {len(filtered_points)} points")
        
        return filtered_points
    
    def voxel_filter(self, points: np.ndarray) -> np.ndarray:
        """
        Remove duplicate points using a simple voxel grid.
        
        Args:
            points: Input point cloud (Nx3 array)
            
        Returns:
            Deduplicated point cloud
        """
        if points.size == 0:
            return points
        
        # Create voxel grid hash
        voxel_coords = np.floor(points / self.voxel_size).astype(int)
        
        # Create unique voxel keys using bit shifting
        voxel_keys = (voxel_coords[:, 0].astype(np.int64) << 20) | \
                     (voxel_coords[:, 1].astype(np.int64) << 10) | \
                     voxel_coords[:, 2].astype(np.int64)
        
        # Find unique voxels and keep first point in each voxel
        _, unique_indices = np.unique(voxel_keys, return_index=True)
        filtered_points = points[unique_indices]
        
        if self.enable_logging and len(points) != len(filtered_points):
            logger.debug(f"Voxel filtering: {len(points)} -> {len(filtered_points)} points")
        
        return filtered_points
    
    def remove_old_clouds(self) -> None:
        """Remove clouds that are too old or exceed the maximum count."""
        current_time = time.time()
        
        # Remove by age
        removed_by_age = 0
        while self.cloud_buffer and (current_time - self.cloud_buffer[0].timestamp) > self.max_age_seconds:
            self.cloud_buffer.popleft()
            removed_by_age += 1
        
        # Remove by count
        removed_by_count = 0
        while len(self.cloud_buffer) > self.max_clouds:
            self.cloud_buffer.popleft()
            removed_by_count += 1
        
        if self.enable_logging and (removed_by_age > 0 or removed_by_count > 0):
            logger.debug(f"Removed clouds: {removed_by_age} by age, {removed_by_count} by count. "
                        f"Buffer size: {len(self.cloud_buffer)}")
    
    def add_cloud(self, points: np.ndarray, timestamp: Optional[float] = None) -> None:
        """
        Add a point cloud to the accumulation buffer.
        
        Args:
            points: Point cloud to add (Nx3 array)
            timestamp: Timestamp for the cloud (uses current time if None)
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Apply height filtering first
        filtered_points = self.height_filter(points)
        
        if filtered_points.size == 0:
            if self.enable_logging:
                logger.debug("Skipping cloud: no points after height filtering")
            return
        
        # Add to accumulation buffer
        cloud_data = CloudData(filtered_points, timestamp)
        self.cloud_buffer.append(cloud_data)
        
        # Remove old clouds
        self.remove_old_clouds()
        
        if self.enable_logging:
            logger.debug(f"Added cloud: {len(filtered_points)} points, buffer size: {len(self.cloud_buffer)}")
    
    def should_publish(self) -> bool:
        """
        Check if accumulated cloud should be published based on rate.
        
        Returns:
            True if should publish, False otherwise
        """
        current_time = time.time()
        return current_time - self.last_publish_time >= (1.0 / self.publish_rate)
    
    def get_accumulated_cloud(self) -> Optional[np.ndarray]:
        """
        Get the accumulated point cloud with all filtering applied.
        
        Returns:
            Accumulated and filtered point cloud, or None if no clouds available
        """
        if not self.cloud_buffer:
            return None
        
        # Remove old clouds first
        self.remove_old_clouds()
        
        if not self.cloud_buffer:
            return None
        
        # Combine all points from accumulated clouds
        all_points = []
        for cloud_data in self.cloud_buffer:
            all_points.append(cloud_data.points)
        
        if not all_points:
            return None
        
        # Concatenate all points
        accumulated_points = np.vstack(all_points)
        
        # Apply voxel filtering to remove duplicates
        filtered_points = self.voxel_filter(accumulated_points)
        
        if filtered_points.size == 0:
            return None
        
        # Apply height filtering (redundant but safe)
        filtered_points = self.height_filter(filtered_points)
        
        if self.enable_logging:
            total_source_points = sum(len(cloud.points) for cloud in self.cloud_buffer)
            logger.debug(f"Accumulated cloud: {len(filtered_points)} points from "
                        f"{len(self.cloud_buffer)} clouds ({total_source_points} total source points)")
        
        return filtered_points
    
    def publish_accumulated_cloud(self, callback: Optional[callable] = None) -> bool:
        """
        Publish accumulated cloud if rate allows.
        
        Args:
            callback: Optional callback function to call with the accumulated cloud
            
        Returns:
            True if published, False otherwise
        """
        if not self.should_publish():
            return False
        
        accumulated_cloud = self.get_accumulated_cloud()
        if accumulated_cloud is None:
            return False
        
        # Update publish time
        self.last_publish_time = time.time()
        
        # Call callback if provided
        if callback:
            callback(accumulated_cloud)
        
        if self.enable_logging:
            logger.info(f"Published accumulated cloud: {len(accumulated_cloud)} points "
                       f"from {len(self.cloud_buffer)} source clouds")
        
        return True
    
    def get_buffer_info(self) -> Dict[str, Any]:
        """
        Get information about the current buffer state.
        
        Returns:
            Dictionary with buffer information
        """
        current_time = time.time()
        return {
            'buffer_size': len(self.cloud_buffer),
            'max_clouds': self.max_clouds,
            'max_age_seconds': self.max_age_seconds,
            'oldest_cloud_age': current_time - self.cloud_buffer[0].timestamp if self.cloud_buffer else 0,
            'total_points': sum(len(cloud.points) for cloud in self.cloud_buffer),
            'last_publish_age': current_time - self.last_publish_time
        }
    
    def reset(self) -> None:
        """Reset the accumulator (clear buffer and reset timing)."""
        self.cloud_buffer.clear()
        self.last_publish_time = 0.0
        if self.enable_logging:
            logger.info("PointCloudAccumulator reset")


def create_accumulator_from_args(args) -> Optional[PointCloudAccumulator]:
    """
    Create a PointCloudAccumulator from command line arguments.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        PointCloudAccumulator instance if accumulation is enabled, None otherwise
    """
    if not hasattr(args, 'accumulation') or not args.accumulation:
        return None
    
    # Extract parameters from args
    max_clouds = getattr(args, 'max_clouds', 30)
    max_age = getattr(args, 'max_age', 2.0)
    voxel_size = getattr(args, 'voxel_size', 0.05)
    min_height = getattr(args, 'min_height', 0.2)
    max_height = getattr(args, 'max_height', 1.0)
    publish_rate = getattr(args, 'publish_rate', 10.0)
    disable_height_filter = getattr(args, 'no_height_filter', False)
    
    return PointCloudAccumulator(
        max_clouds=max_clouds,
        max_age_seconds=max_age,
        voxel_size=voxel_size,
        min_height=min_height,
        max_height=max_height,
        publish_rate=publish_rate,
        disable_height_filter=disable_height_filter
    )


def add_accumulation_args(parser):
    """
    Add accumulation-related command line arguments to an ArgumentParser.
    
    Args:
        parser: ArgumentParser instance to add arguments to
    """
    parser.add_argument('--accumulation', action="store_true", 
                       help='Enable point cloud accumulation')
    parser.add_argument('--max-clouds', type=int, default=30, 
                       help='Maximum number of clouds to accumulate')
    parser.add_argument('--max-age', type=float, default=2.0, 
                       help='Maximum age of clouds in seconds')
    parser.add_argument('--voxel-size', type=float, default=0.05, 
                       help='Voxel grid size for deduplication')
    parser.add_argument('--min-height', type=float, default=0.2, 
                       help='Minimum Z height for filtering')
    parser.add_argument('--max-height', type=float, default=1.0, 
                       help='Maximum Z height for filtering')
    parser.add_argument('--publish-rate', type=float, default=10.0, 
                       help='Rate to publish accumulated clouds (Hz)')
    parser.add_argument('--no-height-filter', action="store_true",
                       help='Disable height filtering in accumulation mode')


def process_points_with_accumulation(points: np.ndarray, 
                                   message_data: dict,
                                   accumulator: Optional[PointCloudAccumulator],
                                   single_frame_callback: callable,
                                   accumulated_callback: callable,
                                   csv_writer=None,
                                   csv_file=None) -> None:
    """
    Process Lidar points with optional accumulation.
    
    Args:
        points: Input point cloud
        message_data: Message metadata
        accumulator: PointCloudAccumulator instance (None for single frame processing)
        single_frame_callback: Callback for single frame processing
        accumulated_callback: Callback for accumulated cloud processing
        csv_writer: Optional CSV writer for data logging
        csv_file: Optional CSV file for flushing
    """
    if accumulator is None:
        # Original processing without accumulation
        single_frame_callback(points, message_data, csv_writer, csv_file)
        return
    
    # Apply height filtering first
    filtered_points = accumulator.height_filter(points)
    
    if filtered_points.size == 0:
        return
    
    # Add to accumulation buffer
    accumulator.add_cloud(filtered_points)
    
    # Check if we should publish accumulated cloud
    if accumulator.publish_accumulated_cloud(accumulated_callback):
        # Save to CSV if requested
        if csv_writer:
            accumulated_cloud = accumulator.get_accumulated_cloud()
            if accumulated_cloud is not None:
                csv_writer.writerow([
                    message_data.get("stamp", ""),
                    message_data.get("frame_id", ""),
                    message_data.get("resolution", ""),
                    message_data.get("src_size", ""),
                    message_data.get("origin", ""),
                    message_data.get("width", ""),
                    len(accumulated_cloud),
                    accumulated_cloud.tolist()
                ])
                if csv_file:
                    csv_file.flush()
    
    # Save individual frame to CSV if requested
    if csv_writer:
        csv_writer.writerow([
            message_data.get("stamp", ""),
            message_data.get("frame_id", ""),
            message_data.get("resolution", ""),
            message_data.get("src_size", ""),
            message_data.get("origin", ""),
            message_data.get("width", ""),
            len(filtered_points),
            filtered_points.tolist()
        ])
        if csv_file:
            csv_file.flush() 