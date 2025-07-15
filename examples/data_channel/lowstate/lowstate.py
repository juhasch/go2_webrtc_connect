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
import signal
import logging
from tabulate import tabulate
from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import RTC_TOPIC

# Suppress verbose logging from WebRTC components
logging.getLogger('root').setLevel(logging.CRITICAL)
logging.getLogger('aioice.ice').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)


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
        timestamp = data.get('stamp', None)
        
        print(f"📊 COMPREHENSIVE ROBOT LOW STATE DATA")
        
        # Handle different timestamp formats
        if timestamp is not None:
            if isinstance(timestamp, (int, float)):
                # Convert Unix timestamp to readable format
                import datetime
                try:
                    dt = datetime.datetime.fromtimestamp(timestamp)
                    print(f"Timestamp: {dt.strftime('%H:%M:%S.%f')[:-3]}")
                except (ValueError, OSError):
                    # If timestamp is not a valid Unix timestamp, show raw value
                    print(f"Timestamp: {timestamp}")
            else:
                print(f"Timestamp: {timestamp}")
        else:
            # Check for other possible timestamp fields
            time_fields = ['time', 'timestamp', 'frame_time', 'system_time']
            found_time = False
            for field in time_fields:
                if field in data and data[field] is not None:
                    print(f"Timestamp: {data[field]} ({field})")
                    found_time = True
                    break
            
            if not found_time:
                # Don't show timestamp line if none available
                pass
                
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
        
        # ==================== IMU STATE DATA ====================
        imu_state = data.get('imu_state', {})
        if imu_state:
            print(f"\n🧭 IMU STATE DATA:")
            print("-" * 40)
            
            # Roll, Pitch, Yaw from IMU state - only show degrees
            rpy_state = imu_state.get('rpy', None)
            if rpy_state:
                print(f"   Roll/Pitch/Yaw:    [{rpy_state[0]*57.2958:.3f}, {rpy_state[1]*57.2958:.3f}, {rpy_state[2]*57.2958:.3f}] deg")
            
            # Show any other IMU state fields
            other_imu_fields = []
            known_imu_fields = {'rpy'}  # Only process rpy, show others as additional
            
            for key, value in imu_state.items():
                if key not in known_imu_fields:
                    other_imu_fields.append((key, value))
            
            if other_imu_fields:
                print(f"   Other IMU state:")
                for key, value in other_imu_fields:
                    if isinstance(value, (int, float)):
                        print(f"     {key}: {value}")
                    elif isinstance(value, (list, tuple)) and len(value) <= 5:
                        print(f"     {key}: {value}")
        
        # ==================== MOTOR STATES ====================
        motor_state = data.get('motor_state', [])
        if motor_state and len(motor_state) > 0:
            # Filter out non-existent motors (Go2 has 12 motors, filter out obvious zeros)
            real_motors = []
            
            # Motor names for Go2 (12 motors total)
            motor_names = [
                "FR_hip", "FR_thigh", "FR_calf",     # Front Right leg
                "FL_hip", "FL_thigh", "FL_calf",     # Front Left leg  
                "RR_hip", "RR_thigh", "RR_calf",     # Rear Right leg
                "RL_hip", "RL_thigh", "RL_calf"      # Rear Left leg
            ]
            
            # Only include motors that are real (first 12 motors or motors with non-zero data)
            for i, motor in enumerate(motor_state):
                # Include if within expected range OR has meaningful data
                if i < len(motor_names):
                    real_motors.append((i, motor))
                else:
                    # For motors beyond the expected count, only include if they have non-zero data
                    position = motor.get('q', 0)
                    velocity = motor.get('dq', 0)
                    torque = motor.get('tau_est', 0)
                    temperature = motor.get('temperature', 0)
                    
                    # Include if any parameter suggests this is a real motor
                    if abs(position) > 0.001 or abs(velocity) > 0.001 or abs(torque) > 0.001 or temperature > 5:
                        real_motors.append((i, motor))
            
            if real_motors:
                print(f"\n⚙️  MOTOR STATES ({len(real_motors)} motors):")
                print("-" * 60)
                
                # Prepare data for tabulate
                table_data = []
                for i, motor in real_motors:
                    motor_name = motor_names[i] if i < len(motor_names) else f"Motor{i}"
                    position = motor.get('q', 0)
                    velocity = motor.get('dq', 0)
                    torque = motor.get('tau_est', 0)
                    temperature = motor.get('temperature', None)
                    
                    temp_str = f"{temperature:.1f}" if temperature is not None else "N/A"
                    
                    table_data.append([
                        motor_name,
                        f"{position:.4f}",
                        f"{velocity:.4f}",
                        f"{torque:.4f}",
                        temp_str
                    ])
                
                # Display table using tabulate
                headers = ["Motor", "Pos(rad)", "Vel(r/s)", "Torque(Nm)", "Temp(°C)"]
                print(tabulate(table_data, headers=headers, tablefmt="simple", stralign="left"))
                
                # Show any motor errors
                for i, motor in real_motors:
                    error = motor.get('error', 0)
                    if error != 0:
                        motor_name = motor_names[i] if i < len(motor_names) else f"Motor{i}"
                        print(f"      ⚠️  {motor_name} ERROR: {error}")
        
        # ==================== FOOT FORCE SENSORS ====================
        foot_force = data.get('foot_force', None)
        if foot_force:
            print(f"\n🦶 FOOT FORCE SENSORS:")
            print("-" * 40)
            
            foot_names = ["Front Right", "Front Left", "Rear Right", "Rear Left"]
            force_data = []
            
            for i, force in enumerate(foot_force):
                foot_name = foot_names[i] if i < len(foot_names) else f"Foot {i}"
                contact = "✅ Contact" if force > 10 else "❌ No contact"  # Threshold for contact detection
                force_data.append([foot_name, f"{force:.2f}", contact])
            
            headers = ["Foot", "Force(N)", "Status"]
            print(tabulate(force_data, headers=headers, tablefmt="simple", stralign="left"))
        
        # ==================== FOOT CONTACT ====================
        foot_contact = data.get('foot_contact', None)
        if foot_contact:
            print(f"\n👟 FOOT CONTACT STATUS:")
            print("-" * 40)
            
            foot_names = ["FR", "FL", "RR", "RL"]  # Front Right, Front Left, Rear Right, Rear Left
            contact_data = []
            
            for i, contact in enumerate(foot_contact):
                status_icon = "🟢" if contact else "🔴"
                status_text = "In Contact" if contact else "No Contact"
                foot_name = foot_names[i] if i < len(foot_names) else f"F{i}"
                contact_data.append([foot_name, status_icon, status_text])
            
            headers = ["Foot", "Icon", "Status"]
            print(tabulate(contact_data, headers=headers, tablefmt="simple", stralign="left"))
        
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
        
        # ==================== BMS (BATTERY MANAGEMENT SYSTEM) ====================
        bms_state = data.get('bms_state', None)
        if bms_state:
            print(f"\n🔋 BATTERY MANAGEMENT SYSTEM:")
            print("-" * 40)
            
            # BMS Status and General Info
            bms_status = bms_state.get('bms_status', None)
            if bms_status is not None:
                status_text = "🟢 Normal" if bms_status == 0 else f"⚠️  Status: {bms_status}"
                print(f"   BMS Status:      {status_text}")
            
            # Pack voltage and current
            pack_voltage = bms_state.get('pack_voltage', None)
            pack_current = bms_state.get('pack_current', None)
            if pack_voltage is not None:
                print(f"   Pack Voltage:    {pack_voltage:.3f} V")
            if pack_current is not None:
                print(f"   Pack Current:    {pack_current:.3f} A")
            
            # State of Charge (SOC)
            soc = bms_state.get('soc', None)
            if soc is not None:
                print(f"   State of Charge: {soc:.1f} %")
            
            # Remaining capacity
            remaining_capacity = bms_state.get('remaining_capacity', None)
            if remaining_capacity is not None:
                print(f"   Remaining Cap:   {remaining_capacity:.2f} Ah")
            
            # Cell voltages
            cell_voltages = bms_state.get('cell_voltage', None)
            if cell_voltages and len(cell_voltages) > 0:
                print(f"   Cell Voltages:   {len(cell_voltages)} cells")
                # Show min/max/avg for summary
                min_v = min(cell_voltages)
                max_v = max(cell_voltages)
                avg_v = sum(cell_voltages) / len(cell_voltages)
                print(f"     Min/Avg/Max:   {min_v:.3f} / {avg_v:.3f} / {max_v:.3f} V")
                
                # Show individual cells if reasonable number (e.g., <= 16)
                if len(cell_voltages) <= 16:
                    for i, voltage in enumerate(cell_voltages):
                        if i % 4 == 0:  # New line every 4 cells
                            print(f"     Cells {i:2d}-{min(i+3, len(cell_voltages)-1):2d}: ", end="")
                        print(f"{voltage:.3f}V ", end="")
                        if (i + 1) % 4 == 0 or i == len(cell_voltages) - 1:
                            print()  # New line
            
            # Cell temperatures
            cell_temps = bms_state.get('cell_temperature', None)
            if cell_temps and len(cell_temps) > 0:
                print(f"   Cell Temps:      {len(cell_temps)} sensors")
                min_t = min(cell_temps)
                max_t = max(cell_temps)
                avg_t = sum(cell_temps) / len(cell_temps)
                print(f"     Min/Avg/Max:   {min_t:.1f} / {avg_t:.1f} / {max_t:.1f} °C")
            
            # Cycle count
            cycle_count = bms_state.get('cycle_count', None)
            if cycle_count is not None:
                print(f"   Cycle Count:     {cycle_count}")
            
            # BMS temperatures
            bms_temp = bms_state.get('bms_temperature', None)
            if bms_temp is not None:
                print(f"   BMS Temperature: {bms_temp:.1f} °C")
            
            # Error flags
            error_flags = bms_state.get('error_flags', None)
            if error_flags is not None and error_flags != 0:
                print(f"   ⚠️  Error Flags:  {error_flags:04X}")
            
            # Show any other BMS fields
            other_bms_fields = []
            known_bms_fields = {
                'bms_status', 'pack_voltage', 'pack_current', 'soc', 'remaining_capacity',
                'cell_voltage', 'cell_temperature', 'cycle_count', 'bms_temperature', 'error_flags'
            }
            
            for key, value in bms_state.items():
                if key not in known_bms_fields:
                    other_bms_fields.append((key, value))
            
            if other_bms_fields:
                print(f"   Other BMS data:")
                for key, value in other_bms_fields:
                    if isinstance(value, (int, float)):
                        print(f"     {key}: {value}")
                    elif isinstance(value, (list, tuple)) and len(value) <= 5:
                        print(f"     {key}: {value}")
        
        # ==================== ADDITIONAL SENSOR DATA ====================
        # Check for any additional fields that might be present
        additional_fields = []
        known_fields = {
            'stamp', 'imu', 'imu_state', 'motor_state', 'foot_force', 'foot_contact', 
            'battery_state', 'position', 'velocity', 'temperature', 
            'error_state', 'errors', 'mode', 'gait_type', 'body_height', 'bms_state'
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
    print("📡 Starting low state monitoring...")
    
    # Get access to the underlying connection for data subscription
    conn = robot.conn
    
    # Define callback function to handle lowstate data when received
    def lowstate_callback(message):
        current_message = message['data']
        display_data(current_message)
    
    # Subscribe to the low state data
    conn.datachannel.pub_sub.subscribe(RTC_TOPIC['LOW_STATE'], lowstate_callback)
    print("✅ Monitoring low state data (Ctrl+C to stop)")
    print("=" * 80)
    
    # Simple monitoring loop - cancellation handled at signal level
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print(f"\n🛑 Monitoring stopped")
        raise  # Re-raise to propagate cancellation to context manager


if __name__ == "__main__":
    """
    Main entry point with improved graceful shutdown handling
    """
    print("Go2 Robot Low State Monitoring")
    print("Press Ctrl+C to stop")
    print("=" * 30)
    
    async def main():
        """Main async function with improved shutdown handling"""
        async with Go2RobotHelper(enable_state_monitoring=False) as robot:
            await lowstate_monitoring_demo(robot)
    
    async def run_with_signal_handling():
        """Run main with proper signal handling for immediate shutdown"""
        # Create the main task
        main_task = asyncio.create_task(main())
        
        # Set up signal handler for graceful shutdown
        def signal_handler():
            print("\n✅ Stopped by user")
            main_task.cancel()
        
        # Register signal handlers for SIGINT (Ctrl+C)
        if hasattr(signal, 'SIGINT'):
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGINT, signal_handler)
        
        try:
            await main_task
        except asyncio.CancelledError:
            # Task was cancelled by signal handler - this is expected
            pass
        except KeyboardInterrupt:
            # Fallback in case signal handling doesn't work on this platform
            print("\n✅ Stopped by user")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Run with signal handling
    try:
        asyncio.run(run_with_signal_handling())
    except KeyboardInterrupt:
        # Fallback in case signal handling doesn't work on this platform
        print("\n✅ Stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        print("Done.")

