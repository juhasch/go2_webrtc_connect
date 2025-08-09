"""
Go2 Robot Helper Module
======================

This module provides a high-level helper class and utilities to reduce boilerplate code
across Go2 robot examples. It abstracts common patterns like connection management,
mode switching, state monitoring, and emergency cleanup.

Key Features:
- Automatic connection management with context manager support
- Built-in state monitoring and display
- Emergency cleanup and safe robot positioning
- Simplified command execution with error handling
- Async context manager for proper resource cleanup
- Obstacle detection control and status querying

Example Usage:
    ```python
    from go2_webrtc_driver.robot_helper import Go2RobotHelper
    
    async def main():
        async with Go2RobotHelper() as robot:
            # Robot is now connected and ready
            await robot.ensure_mode("ai")
            await robot.execute_command("Hello")
            await robot.handstand_sequence()
            
            # Control obstacle detection
            status = await robot.obstacle_detection("status")  # Check current status
            await robot.obstacle_detection("enable")          # Enable obstacle detection
            await robot.obstacle_detection("disable")         # Disable obstacle detection
    ```

Author: Go2 WebRTC Connect
Version: 1.0
"""

import asyncio
import logging
import json
import sys
from typing import Optional, Dict, Any, Callable, Union, List
# from contextlib import asynccontextmanager
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
        self._last_printed_rpy = None  # Store last printed RPY for noise reduction
        self._rpy_threshold = 0.01     # Minimum change to trigger print
        
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
        """Display compact state information (only on significant RPY change)"""
        if not self.monitoring_enabled:
            return
        try:
            self.state_count += 1
            # timestamp is available in message but not used for compact display
            mode = message.get('mode', 'N/A')
            progress = message.get('progress', 'N/A')
            gait_type = message.get('gait_type', 'N/A')
            body_height = message.get('body_height', 'N/A')
            imu_state = message.get('imu_state', {})
            rpy = imu_state.get('rpy', [0, 0, 0])
            # Only print if RPY changes significantly
            should_print = False
            if self._last_printed_rpy is None:
                should_print = True
            else:
                diffs = [abs(rpy[i] - self._last_printed_rpy[i]) for i in range(3)]
                if any(d > self._rpy_threshold for d in diffs):
                    should_print = True
            if should_print:
                print(f"🤖 State #{self.state_count}: Mode={mode}, Progress={progress}, "
                      f"Gait={gait_type}, Height={body_height:.3f}m, "
                      f"Roll={rpy[0]:.3f}, Pitch={rpy[1]:.3f}, Yaw={rpy[2]:.3f}")
                self._last_printed_rpy = list(rpy)
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
        self._movement_prepared: bool = False  # Prepare joystick/speed once before first Move
        
        # Set up logging
        logging.basicConfig(level=logging_level)
        self.logger = logging.getLogger(__name__)
        
    async def __aenter__(self) -> 'Go2RobotHelper':
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with conditional emergency cleanup"""
        # Only perform emergency cleanup for serious connection/communication errors
        # Don't trigger emergency cleanup for simple command validation errors
        should_emergency_cleanup = False
        
        if exc_type is not None:
            # Skip cleanup for user interruptions and graceful cancellations
            if exc_type in (KeyboardInterrupt, asyncio.CancelledError):
                if exc_type is asyncio.CancelledError and self.is_graceful_shutdown:
                    should_emergency_cleanup = False
                else:
                    should_emergency_cleanup = False  # Let user interruptions be graceful
            # Skip cleanup for simple command validation errors
            elif exc_type is ValueError and "Unknown command" in str(exc_val):
                should_emergency_cleanup = False
            # Only cleanup for serious connection/communication errors
            else:
                # Check if it's a serious error (connection issues, etc.)
                error_str = str(exc_val).lower() if exc_val else ""
                serious_errors = ["connection", "timeout", "webrtc", "network", "socket"]
                should_emergency_cleanup = any(err in error_str for err in serious_errors)
        
        if should_emergency_cleanup:
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
                    
        # Switch mode
        try:
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"], 
                {
                    "api_id": 1002,
                    "parameter": {"name": target_mode}
                }
            )
            
            print("⏳ Waiting for mode switch to complete...")
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

            # Debug output specifically for movement optimization
                
            response = await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], 
                request_data
            )
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                
            # For Move, surface concise response information to aid debugging
            if command == "Move":
                try:
                    status = response.get("data", {}).get("header", {}).get("status", {})
                    code = status.get("code")
                    msg = status.get("msg") or status.get("message")
                    if code not in (0, None):
                        print(f"⚠️ Move response code={code}, msg={msg}")
                except Exception:
                    pass

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

    async def obstacle_detection(self, action: str = "status") -> Union[bool, None]:
        """
        Control or query obstacle detection system
        
        Args:
            action: Action to perform - "status", "enable", "disable", "on", "off", "query"
                   - "status"/"query": Return current obstacle detection status
                   - "enable"/"on": Enable obstacle detection  
                   - "disable"/"off": Disable obstacle detection
                   
        Returns:
            bool: For status queries, True if enabled, False if disabled
                  For enable/disable commands, True if successful, False if failed
            None: If status query fails or times out
        """
        action = action.lower().strip()
        
        # Normalize action names
        if action in ["on", "enable"]:
            action = "enable"
        elif action in ["off", "disable"]:
            action = "disable"
        elif action in ["status", "query"]:
            action = "status"
        else:
            raise ValueError(f"Invalid action: {action}. Use 'status', 'enable'/'on', or 'disable'/'off'")
        
        if action == "status":
            return await self._get_obstacle_detection_status()
        elif action == "enable":
            return await self._set_obstacle_detection(True)
        elif action == "disable":
            return await self._set_obstacle_detection(False)
            
    async def _get_obstacle_detection_status(self) -> Union[bool, None]:
        """
        Query current obstacle detection status
        
        Returns:
            bool: True if enabled, False if disabled, None if query failed
        """
        print("📡 Checking obstacle detection status...")
        
        try:
            import json
            status_received = False
            current_status = None
            
            def multiplestate_callback(message):
                nonlocal status_received, current_status
                try:
                    # Parse the message data
                    data = json.loads(message['data']) if isinstance(message['data'], str) else message['data']
                    current_status = data.get('obstaclesAvoidSwitch', False)
                    status_received = True
                except Exception as e:
                    self.logger.error(f"Error parsing multiplestate data: {e}")
            
            # Subscribe to multiple state topic to get current status
            self.conn.datachannel.pub_sub.subscribe(RTC_TOPIC['MULTIPLE_STATE'], multiplestate_callback)
            
            # Wait for status data (timeout after 5 seconds)
            wait_time = 0
            while not status_received and wait_time < 5.0:
                await asyncio.sleep(0.1)
                wait_time += 0.1
                
            if status_received:
                status_text = "🟢 ENABLED" if current_status else "🔴 DISABLED"
                print(f"📊 Obstacle detection status: {status_text}")
                return current_status
            else:
                print("⏱️ Status query timeout - no multiplestate data received")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting obstacle detection status: {e}")
            print(f"❌ Failed to query obstacle detection status: {e}")
            return None
            
    async def _set_obstacle_detection(self, enable: bool) -> bool:
        """
        Enable or disable obstacle detection
        
        Args:
            enable: True to enable, False to disable
            
        Returns:
            bool: True if successful, False if failed
        """
        action_text = "Enabling" if enable else "Disabling"
        emoji = "🟢" if enable else "🔴"
        print(f"{emoji} {action_text} obstacle detection...")
        
        try:
            # Send enable/disable command
            api_id = 1001 if enable else 1002  # 1001 for enable, 1002 for disable
            response = await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC['OBSTACLES_AVOID'], 
                {
                    "api_id": api_id,
                    "parameter": {"enable": enable}
                }
            )
            
            # Check response
            if response and response.get('data', {}).get('header', {}).get('status', {}).get('code') == 0:
                success_text = "enabled" if enable else "disabled"
                print(f"✅ Obstacle detection {success_text} successfully")
                
                # Brief wait for the change to take effect
                await asyncio.sleep(1)
                return True
            else:
                failure_text = "enable" if enable else "disable"
                print(f"❌ Failed to {failure_text} obstacle detection")
                return False
                
        except Exception as e:
            failure_text = "enabling" if enable else "disabling"
            self.logger.error(f"Error {failure_text} obstacle detection: {e}")
            print(f"❌ Error {failure_text} obstacle detection: {e}")
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
        
        # Demonstrate obstacle detection control
        print("\n🛡️ Obstacle Detection Demo")
        status = await robot.obstacle_detection("status")
        print(f"Initial status: {'Enabled' if status else 'Disabled' if status is not None else 'Unknown'}")
        
        if status is not None:
            # Toggle obstacle detection
            await robot.obstacle_detection("disable")
            await robot.obstacle_detection("enable") 
        
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