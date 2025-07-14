"""
Go2 Robot Comprehensive Low State Monitoring - Updated with Go2RobotHelper
========================================================================

This example demonstrates comprehensive monitoring of the robot's low-level state data
using the simplified Go2RobotHelper interface.

RESTORED: Full comprehensive data display including all motors, sensors, and system state.
Previously simplified version showed only basic IMU, battery, and 4 motors - now displays:

✅ Complete IMU data (quaternion, RPY, gyroscope, accelerometer, temperature)
✅ All 12 motor states with detailed information (position, velocity, torque, temperature, current, errors)  
✅ Foot force sensors and contact detection
✅ Comprehensive battery information (voltage, current, temperature, capacity, percentage, health)
✅ Robot position, velocity, and motion data
✅ System temperatures and error states
✅ Robot mode, gait type, and body height information
✅ Automatic detection and display of additional sensor data

The helper automatically handles:
- Connection management and cleanup
- Exception handling and recovery  
- Proper resource management

This example demonstrates:
- Subscribing to low-level state data
- Real-time monitoring of ALL robot sensors and systems
- Comprehensive data processing and display
- Error detection and reporting

Usage:
    python lowstate.py
"""

import asyncio
from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import RTC_TOPIC


def display_data(data):
    """
    Process and display comprehensive low state data from the robot
    
    This function handles the incoming low-level state messages
    and displays all available information about the robot's sensors,
    motors, and system state.
    """
    try:
        # Clear screen for clean display
        import sys
        sys.stdout.write("\033[H\033[J")
        
        # Extract key information from low state data
        timestamp = data.get('stamp', 'N/A')
        
        print(f"📊 COMPREHENSIVE ROBOT LOW STATE DATA")
        print(f"Timestamp: {timestamp}")
        print("=" * 80)
        
        # ==================== IMU DATA ====================
        imu = data.get('imu', {})
        if imu:
            print(f"\n🧭 IMU SENSOR DATA:")
            print("-" * 40)
            
            # Quaternion orientation
            quaternion = imu.get('quaternion', [0, 0, 0, 1])
            print(f"   Quaternion (XYZW): [{quaternion[0]:.6f}, {quaternion[1]:.6f}, {quaternion[2]:.6f}, {quaternion[3]:.6f}]")
            
            # Roll, Pitch, Yaw (if available)
            rpy = imu.get('rpy', None)
            if rpy:
                print(f"   Roll/Pitch/Yaw:    [{rpy[0]:.6f}, {rpy[1]:.6f}, {rpy[2]:.6f}] rad")
                print(f"   Roll/Pitch/Yaw:    [{rpy[0]*57.2958:.3f}, {rpy[1]*57.2958:.3f}, {rpy[2]*57.2958:.3f}] deg")
            
            # Angular velocity (gyroscope)
            gyroscope = imu.get('gyroscope', [0, 0, 0])
            print(f"   Gyroscope (XYZ):   [{gyroscope[0]:.6f}, {gyroscope[1]:.6f}, {gyroscope[2]:.6f}] rad/s")
            
            # Linear acceleration
            accelerometer = imu.get('accelerometer', [0, 0, 0])
            print(f"   Accelerometer:     [{accelerometer[0]:.6f}, {accelerometer[1]:.6f}, {accelerometer[2]:.6f}] m/s²")
            
            # Additional IMU fields
            temperature = imu.get('temperature', None)
            if temperature is not None:
                print(f"   IMU Temperature:   {temperature:.2f}°C")
        
        # ==================== MOTOR STATES ====================
        motor_state = data.get('motor_state', [])
        if motor_state and len(motor_state) > 0:
            print(f"\n⚙️  MOTOR STATES ({len(motor_state)} motors):")
            print("-" * 80)
            
            # Motor names for Go2 (12 motors total)
            motor_names = [
                "FR_hip", "FR_thigh", "FR_calf",     # Front Right leg
                "FL_hip", "FL_thigh", "FL_calf",     # Front Left leg  
                "RR_hip", "RR_thigh", "RR_calf",     # Rear Right leg
                "RL_hip", "RL_thigh", "RL_calf"      # Rear Left leg
            ]
            
            # Display header
            print(f"   {'Motor':<12} {'Mode':<6} {'Pos(rad)':<10} {'Vel(r/s)':<10} {'Torque(Nm)':<12} {'Temp(°C)':<8} {'Current(A)':<10}")
            print("   " + "-" * 75)
            
            # Display all motors
            for i, motor in enumerate(motor_state):
                motor_name = motor_names[i] if i < len(motor_names) else f"Motor{i}"
                mode = motor.get('mode', 'N/A')
                position = motor.get('q', 0)
                velocity = motor.get('dq', 0)
                torque = motor.get('tau_est', 0)
                temperature = motor.get('temperature', None)
                current = motor.get('current', None)
                
                temp_str = f"{temperature:.1f}" if temperature is not None else "N/A"
                current_str = f"{current:.3f}" if current is not None else "N/A"
                
                print(f"   {motor_name:<12} {mode:<6} {position:<10.4f} {velocity:<10.4f} {torque:<12.4f} {temp_str:<8} {current_str:<10}")
                
                # Show any error states
                error = motor.get('error', 0)
                if error != 0:
                    print(f"      ⚠️  ERROR: {error}")
        
        # ==================== FOOT FORCE SENSORS ====================
        foot_force = data.get('foot_force', None)
        if foot_force:
            print(f"\n🦶 FOOT FORCE SENSORS:")
            print("-" * 40)
            foot_names = ["Front Right", "Front Left", "Rear Right", "Rear Left"]
            for i, force in enumerate(foot_force):
                foot_name = foot_names[i] if i < len(foot_names) else f"Foot {i}"
                contact = "✅ Contact" if force > 10 else "❌ No contact"  # Threshold for contact detection
                print(f"   {foot_name:<12}: {force:>8.2f} N  {contact}")
        
        # ==================== FOOT CONTACT ====================
        foot_contact = data.get('foot_contact', None)
        if foot_contact:
            print(f"\n👟 FOOT CONTACT STATUS:")
            print("-" * 40)
            foot_names = ["FR", "FL", "RR", "RL"]  # Front Right, Front Left, Rear Right, Rear Left
            contact_status = []
            for i, contact in enumerate(foot_contact):
                status = "🟢" if contact else "🔴"
                foot_name = foot_names[i] if i < len(foot_names) else f"F{i}"
                contact_status.append(f"{foot_name}:{status}")
                print(f"   {foot_names[i] if i < len(foot_names) else f'Foot {i}'}: {'In Contact' if contact else 'No Contact'}")
            
        # ==================== BATTERY INFORMATION ====================
        battery_state = data.get('battery_state', {})
        if battery_state:
            print(f"\n🔋 BATTERY SYSTEM:")
            print("-" * 40)
            
            voltage = battery_state.get('voltage', 0)
            current = battery_state.get('current', 0)
            temperature = battery_state.get('temperature', None)
            capacity = battery_state.get('capacity', None)
            percentage = battery_state.get('percentage', None)
            
            print(f"   Voltage:     {voltage:.3f} V")
            print(f"   Current:     {current:.3f} A")
            if temperature is not None:
                print(f"   Temperature: {temperature:.2f} °C")
            if capacity is not None:
                print(f"   Capacity:    {capacity:.2f} Ah")
            if percentage is not None:
                print(f"   Charge:      {percentage:.1f} %")
                
            # Battery health indicator
            if voltage > 0:
                if voltage > 25.0:
                    health = "🟢 Good"
                elif voltage > 23.0:
                    health = "🟡 Low"
                else:
                    health = "🔴 Critical"
                print(f"   Status:      {health}")
        
        # ==================== POSITION & VELOCITY ====================
        position = data.get('position', None)
        velocity = data.get('velocity', None)
        
        if position or velocity:
            print(f"\n📍 ROBOT POSE & MOTION:")
            print("-" * 40)
            
            if position:
                print(f"   Position (XYZ): [{position[0]:.6f}, {position[1]:.6f}, {position[2]:.6f}] m")
            
            if velocity:
                print(f"   Velocity (XYZ): [{velocity[0]:.6f}, {velocity[1]:.6f}, {velocity[2]:.6f}] m/s")
        
        # ==================== SYSTEM TEMPERATURES ====================
        temperature_data = data.get('temperature', None)
        if temperature_data:
            print(f"\n🌡️  SYSTEM TEMPERATURES:")
            print("-" * 40)
            if isinstance(temperature_data, dict):
                for component, temp in temperature_data.items():
                    print(f"   {component.capitalize()}: {temp:.2f} °C")
            elif isinstance(temperature_data, (list, tuple)):
                temp_names = ["CPU", "GPU", "Board", "Ambient"]
                for i, temp in enumerate(temperature_data):
                    name = temp_names[i] if i < len(temp_names) else f"Sensor_{i}"
                    print(f"   {name}: {temp:.2f} °C")
        
        # ==================== ERROR STATES ====================
        error_state = data.get('error_state', None)
        errors = data.get('errors', None)
        
        if error_state or errors:
            print(f"\n⚠️  ERROR STATUS:")
            print("-" * 40)
            
            if error_state:
                if error_state == 0:
                    print("   ✅ No system errors")
                else:
                    print(f"   🚨 Error code: {error_state}")
            
            if errors and len(errors) > 0:
                for i, error in enumerate(errors):
                    print(f"   Error {i+1}: {error}")
        
        # ==================== MODE & GAIT INFORMATION ====================
        mode = data.get('mode', None)
        gait_type = data.get('gait_type', None)
        body_height = data.get('body_height', None)
        
        if mode or gait_type or body_height is not None:
            print(f"\n🤖 ROBOT STATE:")
            print("-" * 40)
            
            if mode is not None:
                print(f"   Mode:        {mode}")
            if gait_type is not None:
                print(f"   Gait Type:   {gait_type}")
            if body_height is not None:
                print(f"   Body Height: {body_height:.4f} m")
        
        # ==================== ADDITIONAL SENSOR DATA ====================
        # Check for any additional fields that might be present
        additional_fields = []
        known_fields = {
            'stamp', 'imu', 'motor_state', 'foot_force', 'foot_contact', 
            'battery_state', 'position', 'velocity', 'temperature', 
            'error_state', 'errors', 'mode', 'gait_type', 'body_height'
        }
        
        for key, value in data.items():
            if key not in known_fields:
                additional_fields.append((key, value))
        
        if additional_fields:
            print(f"\n🔍 ADDITIONAL DATA:")
            print("-" * 40)
            for key, value in additional_fields:
                if isinstance(value, (int, float)):
                    print(f"   {key}: {value}")
                elif isinstance(value, (list, tuple)) and len(value) <= 10:
                    print(f"   {key}: {value}")
                elif isinstance(value, dict) and len(value) <= 5:
                    print(f"   {key}: {value}")
                else:
                    print(f"   {key}: <complex data structure>")
        
        print("=" * 80)
        print(f"📊 Low state data update complete")
        
        # Flush output to ensure immediate display
        sys.stdout.flush()
        
    except Exception as e:
        print(f"❌ Error processing low state data: {e}")
        import traceback
        traceback.print_exc()


async def lowstate_monitoring_demo(robot: Go2RobotHelper):
    """
    Demonstrate low state monitoring using the robot helper
    
    This subscribes to the robot's low-level state data and displays
    real-time sensor information.
    """
    print("=== Go2 Robot Comprehensive Low State Monitoring ===")
    print("📡 Starting comprehensive low state data monitoring...")
    print("This will display detailed real-time sensor data from the robot")
    print("Press Ctrl+C to stop monitoring gracefully")
    
    # Get access to the underlying connection for data subscription
    conn = robot.conn
    
    print(f"\n📊 Setting up low state data subscription...")
    
    # Define callback function to handle lowstate data when received
    def lowstate_callback(message):
        current_message = message['data']
        display_data(current_message)
    
    # Subscribe to the low state data
    conn.datachannel.pub_sub.subscribe(RTC_TOPIC['LOW_STATE'], lowstate_callback)
    print("✅ Subscribed to comprehensive low state data stream")
    
    print(f"\n🔄 Monitoring comprehensive low state data...")
    print("Detailed sensor data will appear below as it's received from the robot")
    print("💡 Tip: Scroll up to see the data refresh in real-time")
    print("🛑 Press Ctrl+C anytime for graceful shutdown")
    print("\n" + "=" * 80)
    
    try:
        # Create a simple monitoring loop that can be cancelled cleanly
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        # This is expected when the program is interrupted
        print(f"\n🛑 Monitoring stopped gracefully")
        raise  # Re-raise to exit the context manager normally
    except Exception as e:
        print(f"\n❌ Error during monitoring: {e}")
        raise
    
    print(f"\n📊 Low state monitoring session completed")


if __name__ == "__main__":
    """
    Main entry point with improved graceful shutdown handling
    """
    print("Starting Go2 Robot Comprehensive Low State Monitoring...")
    print("This will display detailed real-time sensor data from all robot systems")
    print("Press Ctrl+C to stop the program gracefully at any time")
    print("=" * 70)
    
    def run_monitoring():
        """Run the monitoring with proper shutdown handling"""
        # Flag to track if we're shutting down gracefully
        shutdown_requested = False
        
        async def main():
            nonlocal shutdown_requested
            try:
                # Set flag to indicate this is normal operation
                async with Go2RobotHelper(enable_state_monitoring=False) as robot:
                    # Mark that we're running normally (not an emergency)
                    robot.is_graceful_shutdown = True
                    await lowstate_monitoring_demo(robot)
            except asyncio.CancelledError:
                # This happens when KeyboardInterrupt is converted to CancelledError
                shutdown_requested = True
                print("\n✅ Program stopped gracefully by user")
            except KeyboardInterrupt:
                # Direct KeyboardInterrupt (shouldn't happen in async context, but just in case)
                shutdown_requested = True
                print("\n✅ Program stopped gracefully by user")
        
        # Run with improved error handling
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n✅ Program stopped gracefully by user")
            shutdown_requested = True
        except Exception as e:
            if not shutdown_requested:
                print(f"❌ Fatal error: {e}")
        
        if shutdown_requested:
            print("📊 Low state monitoring session ended successfully")
        print("Goodbye! 👋")
    
    # Execute the monitoring
    run_monitoring()

