"""
Go2 Robot Helper Module
======================

This module provides a high-level helper class and utilities to reduce boilerplate code
across Go2 robot examples. It abstracts common patterns like connection management,
mode switching, state monitoring, and emergency cleanup.

Key Features:
- Automatic connection management with context manager support
- Safe mode switching with firmware 1.1.7 compatibility
- Built-in state monitoring and display
- Emergency cleanup and safe robot positioning
- Simplified command execution with error handling
- Async context manager for proper resource cleanup

Example Usage:
    ```python
    from go2_webrtc_driver.robot_helper import Go2RobotHelper
    
    async def main():
        async with Go2RobotHelper() as robot:
            # Robot is now connected and ready
            await robot.ensure_mode("ai")
            await robot.execute_command("Hello")
            await robot.handstand_sequence()
    ```

Author: Go2 WebRTC Connect
Version: 1.0
"""

import asyncio
import logging
import json
import sys
from typing import Optional, Dict, Any, Callable, Union, List
from contextlib import asynccontextmanager
from enum import Enum

from .webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from .constants import RTC_TOPIC, SPORT_CMD


class RobotMode(Enum):
    """Robot motion modes"""
    NORMAL = "normal"
    AI = "ai"
    SPORT = "sport"


class StateMonitor:
    """Robot state monitoring and display helper"""
    
    def __init__(self, enable_detailed: bool = False):
        self.latest_state = None
        self.state_count = 0
        self.monitoring_enabled = False
        self.detailed_mode = enable_detailed
        self._callbacks: List[Callable] = []
        
    def enable_monitoring(self) -> None:
        """Enable state monitoring output"""
        self.monitoring_enabled = True
        
    def disable_monitoring(self) -> None:
        """Disable state monitoring output"""
        self.monitoring_enabled = False
        
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add custom callback for state updates"""
        self._callbacks.append(callback)
        
    def display_compact_state(self, message: Dict[str, Any]) -> None:
        """Display compact state information"""
        if not self.monitoring_enabled:
            return
            
        try:
            self.state_count += 1
            timestamp = message.get('stamp', 'N/A')
            mode = message.get('mode', 'N/A')
            progress = message.get('progress', 'N/A')
            gait_type = message.get('gait_type', 'N/A')
            body_height = message.get('body_height', 'N/A')
            
            imu_state = message.get('imu_state', {})
            rpy = imu_state.get('rpy', [0, 0, 0])
            
            print(f"\r🤖 State #{self.state_count}: Mode={mode}, Progress={progress}, "
                  f"Gait={gait_type}, Height={body_height:.3f}m, "
                  f"Roll={rpy[0]:.3f}, Pitch={rpy[1]:.3f}, Yaw={rpy[2]:.3f}", 
                  end='', flush=True)
            
            self.latest_state = message
            
            # Call custom callbacks
            for callback in self._callbacks:
                callback(message)
                
        except Exception as e:
            print(f"\nError displaying state: {e}")
    
    def display_detailed_state(self, message: Dict[str, Any]) -> None:
        """Display detailed state information"""
        try:
            print("\n" + "="*60)
            print("🤖 DETAILED ROBOT STATE")
            print("="*60)
            
            timestamp = message.get('stamp', 'N/A')
            mode = message.get('mode', 'N/A')
            progress = message.get('progress', 'N/A')
            gait_type = message.get('gait_type', 'N/A')
            body_height = message.get('body_height', 'N/A')
            position = message.get('position', 'N/A')
            velocity = message.get('velocity', 'N/A')
            
            print(f"Timestamp: {timestamp}")
            print(f"Mode: {mode}")
            print(f"Progress: {progress}")
            print(f"Gait Type: {gait_type}")
            print(f"Body Height: {body_height} m")
            print(f"Position: {position}")
            print(f"Velocity: {velocity}")
            
            imu_state = message.get('imu_state', {})
            if imu_state:
                rpy = imu_state.get('rpy', [0, 0, 0])
                quaternion = imu_state.get('quaternion', [0, 0, 0, 1])
                gyroscope = imu_state.get('gyroscope', [0, 0, 0])
                accelerometer = imu_state.get('accelerometer', [0, 0, 0])
                
                print(f"IMU - Roll: {rpy[0]:.3f}, Pitch: {rpy[1]:.3f}, Yaw: {rpy[2]:.3f}")
                print(f"IMU - Quaternion: {quaternion}")
                print(f"IMU - Gyroscope: {gyroscope}")
                print(f"IMU - Accelerometer: {accelerometer}")
            
            print("="*60)
            
        except Exception as e:
            print(f"\nError displaying detailed state: {e}")
    
    def get_state_callback(self) -> Callable:
        """Get callback function for state monitoring"""
        def sportmodestatus_callback(message):
            current_message = message['data']
            if self.detailed_mode:
                self.display_detailed_state(current_message)
            else:
                self.display_compact_state(current_message)
                
        return sportmodestatus_callback


class Go2RobotHelper:
    """
    High-level helper class for Go2 robot operations
    
    This class provides a simplified interface for common robot operations,
    handling connection management, mode switching, state monitoring, and
    emergency cleanup automatically.
    
    Example:
        ```python
        async with Go2RobotHelper() as robot:
            await robot.ensure_mode("ai")
            await robot.execute_command("Hello")
            await robot.handstand_sequence()
        ```
    """
    
    def __init__(self, 
                 connection_method: WebRTCConnectionMethod = WebRTCConnectionMethod.LocalSTA,
                 serial_number: Optional[str] = None,
                 ip: Optional[str] = None,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 enable_state_monitoring: bool = True,
                 detailed_state_display: bool = False,
                 logging_level: int = logging.WARNING):
        """
        Initialize robot helper
        
        Args:
            connection_method: WebRTC connection method
            serial_number: Robot serial number (for remote connections)
            ip: Robot IP address (for local connections)
            username: Username (for remote connections)
            password: Password (for remote connections)
            enable_state_monitoring: Enable automatic state monitoring
            detailed_state_display: Use detailed state display
            logging_level: Logging level
        """
        self.connection_method = connection_method
        self.serial_number = serial_number
        self.ip = ip
        self.username = username
        self.password = password
        
        self.conn: Optional[Go2WebRTCConnection] = None
        self.state_monitor = StateMonitor(detailed_state_display)
        self.enable_state_monitoring = enable_state_monitoring
        self.current_mode: Optional[str] = None
        self.is_connected = False
        self.is_graceful_shutdown = False  # Flag to track graceful vs emergency shutdown
        
        # Set up logging
        logging.basicConfig(level=logging_level)
        self.logger = logging.getLogger(__name__)
        
    async def __aenter__(self) -> 'Go2RobotHelper':
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with conditional emergency cleanup"""
        # Only perform emergency cleanup for actual errors, not for graceful shutdowns
        if exc_type is not None and not (exc_type is asyncio.CancelledError and self.is_graceful_shutdown):
            # There was an actual error (not a graceful cancellation)
            if exc_type is not KeyboardInterrupt and exc_type is not asyncio.CancelledError:
                await self.emergency_cleanup()
        
        # Always disconnect cleanly
        await self.disconnect()
        
    async def connect(self) -> None:
        """Connect to the robot"""
        print("🔌 Initializing robot connection...")
        
        self.conn = Go2WebRTCConnection(
            self.connection_method,
            serialNumber=self.serial_number,
            ip=self.ip,
            username=self.username,
            password=self.password
        )
        
        print("🔗 Connecting to robot...")
        await self.conn.connect()
        self.is_connected = True
        print("✅ Connected to robot successfully!")
        
        # Set up state monitoring
        if self.enable_state_monitoring:
            print("📊 Setting up state monitoring...")
            callback = self.state_monitor.get_state_callback()
            self.conn.datachannel.pub_sub.subscribe(RTC_TOPIC['LF_SPORT_MOD_STATE'], callback)
            self.state_monitor.enable_monitoring()
            print("✅ State monitoring enabled")
            
            # Get initial state
            await asyncio.sleep(2)
            
        # Get current mode
        await self.get_current_mode()
        
    async def disconnect(self) -> None:
        """Disconnect from the robot cleanly"""
        if self.conn and self.is_connected:
            try:
                # Disable state monitoring first
                self.state_monitor.disable_monitoring()
                
                # Give a moment for any pending operations to complete
                await asyncio.sleep(0.1)
                
                # Disconnect from WebRTC
                await self.conn.disconnect()
                
                if not self.is_graceful_shutdown:
                    print("✅ WebRTC connection closed successfully")
                    
            except Exception as e:
                if not self.is_graceful_shutdown:
                    self.logger.error(f"Error closing WebRTC connection: {e}")
            finally:
                self.is_connected = False
                
    async def get_current_mode(self) -> str:
        """Get current robot motion mode"""
        try:
            response = await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"], 
                {"api_id": 1001}
            )
            
            if response['data']['header']['status']['code'] == 0:
                data = json.loads(response['data']['data'])
                self.current_mode = data['name']
                print(f"📋 Current motion mode: {self.current_mode}")
                return self.current_mode
            else:
                print("⚠️  Warning: Could not determine current motion mode")
                self.current_mode = "unknown"
                return self.current_mode
                
        except Exception as e:
            self.logger.error(f"Error getting current mode: {e}")
            self.current_mode = "unknown"
            return self.current_mode
            
    async def ensure_mode(self, target_mode: Union[str, RobotMode], 
                         standdown_before_switch: bool = True) -> bool:
        """
        Ensure robot is in the specified mode
        
        Args:
            target_mode: Target mode ('normal', 'ai', 'sport' or RobotMode enum)
            standdown_before_switch: Whether to stand down before mode switching (required for firmware 1.1.7)
            
        Returns:
            bool: True if mode switch was successful
        """
        if isinstance(target_mode, RobotMode):
            target_mode = target_mode.value
            
        current_mode = await self.get_current_mode()
        
        if current_mode == target_mode:
            print(f"✅ Already in {target_mode} mode")
            return True
            
        print(f"🔄 Switching from {current_mode} to {target_mode} mode...")
        
        # StandDown before mode switch (required for firmware 1.1.7)
        if standdown_before_switch and current_mode != "normal":
            print("🔽 Making robot stand down (required for firmware 1.1.7)...")
            await self.execute_command("StandDown")
            await asyncio.sleep(3)
            
        # Switch mode
        try:
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"], 
                {
                    "api_id": 1002,
                    "parameter": {"name": target_mode}
                }
            )
            
            print(f"⏳ Waiting for mode switch to complete...")
            await asyncio.sleep(5)
            
            # Verify mode switch
            new_mode = await self.get_current_mode()
            if new_mode == target_mode:
                print(f"✅ Successfully switched to {target_mode} mode")
                return True
            else:
                print(f"❌ Mode switch failed. Current mode: {new_mode}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error switching mode: {e}")
            return False
            
    async def execute_command(self, command: str, 
                            parameter: Optional[Dict[str, Any]] = None,
                            wait_time: float = 2.0) -> Dict[str, Any]:
        """
        Execute a sport command
        
        Args:
            command: Command name (e.g., "Hello", "StandUp", "Sit")
            parameter: Optional command parameters
            wait_time: Time to wait after command execution
            
        Returns:
            Command response
        """
        if command not in SPORT_CMD:
            raise ValueError(f"Unknown command: {command}. Available commands: {list(SPORT_CMD.keys())}")
            
        print(f"🎯 Executing command: {command}")
        
        try:
            request_data = {"api_id": SPORT_CMD[command]}
            if parameter:
                request_data["parameter"] = parameter
                
            response = await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], 
                request_data
            )
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                
            print(f"✅ Command {command} executed successfully")
            return response
            
        except Exception as e:
            self.logger.error(f"Error executing command {command}: {e}")
            raise
            
    async def handstand_sequence(self, duration: float = 10.0) -> bool:
        """
        Perform a complete handstand sequence
        
        Args:
            duration: Duration to hold handstand in seconds
            
        Returns:
            bool: True if handstand was successful
        """
        print("🤸 Starting handstand sequence...")
        
        try:
            # Ensure AI mode
#            if not await self.ensure_mode("ai"):
#                print("❌ Failed to switch to AI mode")
#                return False
                
            # Stand up
            await self.execute_command("StandUp", wait_time=3)
            
            # Perform handstand
            print(f"🤸 Performing handstand for {duration} seconds...")
            await self.execute_command("StandOut", {"data": True}, wait_time=0)
            
            # Monitor handstand
            for i in range(int(duration)):
                print(f"🤸 Handstand progress: {i+1}/{int(duration)} seconds")
                await asyncio.sleep(1)
                
            # Turn off handstand
            print("🤸 Turning off handstand mode...")
            await self.execute_command("StandOut", {"data": False}, wait_time=3)
            
            # Return to standing
            await self.execute_command("StandUp", wait_time=3)
            
            print("✅ Handstand sequence completed successfully!")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during handstand sequence: {e}")
            print("❌ Handstand sequence failed")
            return False
            
    async def emergency_cleanup(self) -> None:
        """Emergency cleanup to return robot to safe position"""
        if not self.conn or not self.is_connected:
            return
            
        # Only show emergency messages for actual emergencies
        if not self.is_graceful_shutdown:
            print("🚨 Performing emergency cleanup...")
        
        try:
            # Try to turn off any active special modes
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], 
                {
                    "api_id": SPORT_CMD["StandOut"],
                    "parameter": {"data": False}
                }
            )
            await asyncio.sleep(1)
            
            # StandDown before mode switch (required for firmware 1.1.7)
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], 
                {"api_id": SPORT_CMD["StandDown"]}
            )
            await asyncio.sleep(2)
            
            # Switch to normal mode
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"], 
                {
                    "api_id": 1002,
                    "parameter": {"name": "normal"}
                }
            )
            await asyncio.sleep(2)
            
            # Stand up
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], 
                {"api_id": SPORT_CMD["StandUp"]}
            )
            await asyncio.sleep(2)
            
            if not self.is_graceful_shutdown:
                print("✅ Emergency cleanup completed")
            
        except Exception as e:
            if not self.is_graceful_shutdown:
                self.logger.error(f"Error during emergency cleanup: {e}")
                print("❌ Emergency cleanup failed")
            
    def get_state_monitor(self) -> StateMonitor:
        """Get the state monitor instance"""
        return self.state_monitor
        
    def add_state_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add custom state monitoring callback"""
        self.state_monitor.add_callback(callback)


# Convenience functions for common operations
async def simple_robot_connection(connection_method: WebRTCConnectionMethod = WebRTCConnectionMethod.LocalSTA):
    """
    Simple robot connection context manager
    
    Example:
        ```python
        async with simple_robot_connection() as robot:
            await robot.execute_command("Hello")
        ```
    """
    return Go2RobotHelper(connection_method)


def create_example_main(robot_operations: Callable):
    """
    Create a standardized main function for examples
    
    Args:
        robot_operations: Async function that takes a Go2RobotHelper instance
        
    Returns:
        Main function that handles all boilerplate
    """
    async def main():
        robot = None
        try:
            async with Go2RobotHelper() as robot:
                await robot_operations(robot)
        except KeyboardInterrupt:
            print("\n✅ Program interrupted by user")
            # Set flag for graceful shutdown if robot is available
            if robot:
                robot.is_graceful_shutdown = True
        except Exception as e:
            print(f"❌ An error occurred: {e}")
            logging.error(f"Error in robot operations: {e}")
            
    return main


# Example usage demonstration
if __name__ == "__main__":
    async def example_operations(robot: Go2RobotHelper):
        """Example robot operations"""
        await robot.ensure_mode("ai")
        await robot.execute_command("Hello")
        await robot.handstand_sequence(5.0)
        
    # Create standardized main function
    main = create_example_main(example_operations)
    
    # Run the example
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1) 