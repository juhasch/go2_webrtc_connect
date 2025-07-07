"""
Multicast Device Discovery for Unitree Go2 Robot
================================================

This module provides functionality to discover Unitree Go2 robots on the local network
using multicast UDP communication. It implements the device discovery protocol used by
the Unitree ecosystem to automatically find and connect to robots without requiring
manual IP configuration.

The discovery process uses UDP multicast to broadcast a query message and listens for
responses from Go2 robots on the network. This allows automatic IP address resolution
based on robot serial numbers.

Key Features:
- Automatic device discovery via multicast
- Serial number to IP address mapping
- Timeout-based discovery with configurable duration
- Robust error handling for network issues

Network Configuration:
- Multicast Group: 231.1.1.1
- Query Port: 10131 (outbound)
- Response Port: 10134 (inbound)

Usage:
    >>> from go2_webrtc_driver.multicast_scanner import discover_ip_sn
    >>> devices = discover_ip_sn(timeout=5)
    >>> print(f"Found {len(devices)} devices")
    >>> for serial, ip in devices.items():
    ...     print(f"Robot {serial} at {ip}")
"""

import socket
import struct
import json
import logging

# Network configuration constants
RECV_PORT = 10134         # Port where devices send multicast responses
MULTICAST_GROUP = '231.1.1.1'  # Multicast group IP address for device discovery
MULTICAST_PORT = 10131    # Port to send multicast query to devices
DISCOVERY_MESSAGE = {"name": "unitree_dapengche"}  # Standard discovery query message


def discover_ip_sn(timeout: int = 2) -> dict:
    """
    Discover Unitree Go2 robots on the local network using multicast UDP.
    
    This function broadcasts a multicast discovery message and listens for responses
    from Go2 robots. It returns a dictionary mapping robot serial numbers to their
    IP addresses.
    
    Args:
        timeout (int, optional): Discovery timeout in seconds. Defaults to 2.
                               Longer timeouts may find more devices but take more time.
    
    Returns:
        dict: A dictionary mapping serial numbers (str) to IP addresses (str).
              Returns empty dict if no devices are found or if errors occur.
    
    Raises:
        socket.error: If there are network connectivity issues
        json.JSONDecodeError: If received messages are malformed
        
    Example:
        >>> devices = discover_ip_sn(timeout=5)
        >>> print(f"Found {len(devices)} devices")
        >>> for serial, ip in devices.items():
        ...     print(f"Robot {serial} at {ip}")
        
        # Example output:
        # Found 2 devices
        # Robot B42D2000XXXXXXXX at 192.168.1.100
        # Robot B42D2000YYYYYYYY at 192.168.1.101
    
    Network Protocol:
        1. Send multicast query to 231.1.1.1:10131
        2. Listen for responses on port 10134
        3. Parse JSON responses containing 'sn' and 'ip' fields
        4. Continue until timeout is reached
    """
    print("Discovering devices on the network...")
    
    # Dictionary to store serial number to IP mapping
    serial_to_ip = {}
    
    # Create UDP socket for multicast communication
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    
    try:
        # Configure socket for address reuse (important for multicast)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind socket to receive responses on the designated port
        sock.bind(('', RECV_PORT))
        
        # Join the multicast group on all available interfaces
        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        # Send multicast discovery query
        query_message = json.dumps(DISCOVERY_MESSAGE)
        
        try:
            sock.sendto(query_message.encode('utf-8'), (MULTICAST_GROUP, MULTICAST_PORT))
            logging.debug(f"Multicast discovery query sent to {MULTICAST_GROUP}:{MULTICAST_PORT}")
        except Exception as e:
            logging.error(f"Error sending multicast query: {e}")
            return serial_to_ip
        
        # Set timeout for receiving responses
        sock.settimeout(timeout)
        
        # Listen for responses until timeout
        try:
            while True:
                # Receive response from device
                data, addr = sock.recvfrom(1024)
                
                try:
                    # Parse the JSON response
                    message = data.decode('utf-8')
                    message_dict = json.loads(message)
                    
                    # Extract device information
                    if "sn" in message_dict:
                        serial_number = message_dict["sn"]
                        # Use IP from message if available, otherwise use sender's IP
                        ip_address = message_dict.get("ip", addr[0])
                        
                        # Store the mapping
                        serial_to_ip[serial_number] = ip_address
                        
                        print(f"Discovered device: {serial_number} at {ip_address}")
                        logging.debug(f"Discovered device: {serial_number} at {ip_address}")
                    else:
                        logging.warning(f"Received message without 'sn' field from {addr[0]}")
                        
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON message from {addr[0]}: {e}")
                    continue
                except UnicodeDecodeError as e:
                    logging.error(f"Error decoding message from {addr[0]}: {e}")
                    continue
                    
        except socket.timeout:
            logging.debug(f"Discovery timeout reached after {timeout} seconds")
            
        except Exception as e:
            logging.error(f"Unexpected error during discovery: {e}")
            
    except Exception as e:
        logging.error(f"Error setting up multicast socket: {e}")
        
    finally:
        # Always close the socket to free resources
        sock.close()
    
    # Log discovery results
    if serial_to_ip:
        logging.debug(f"Discovery completed. Found {len(serial_to_ip)} device(s)")
    else:
        logging.warning("No devices discovered")
    
    return serial_to_ip


def main():
    """
    Command-line interface for device discovery.
    
    This function provides a simple CLI for testing the multicast discovery
    functionality when the module is run as a command-line tool.
    """
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.debug,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 50)
    print("Unitree Go2 Robot Discovery")
    print("=" * 50)
    
    # Perform discovery with extended timeout for comprehensive scanning
    serial_to_ip = discover_ip_sn(timeout=5)
    
    # Display results
    print(f"\nDiscovery Results:")
    print("-" * 30)
    
    if serial_to_ip:
        print(f"Found {len(serial_to_ip)} device(s):")
        for serial_number, ip_address in serial_to_ip.items():
            print(f"  • Serial Number: {serial_number}")
            print(f"    IP Address: {ip_address}")
            print()
    else:
        print("No devices found on the network.")
        print("\nTroubleshooting:")
        print("- Ensure the Go2 robot is powered on and connected to the network")
        print("- Check that your computer is on the same network as the robot")
        print("- Verify firewall settings allow multicast traffic")
        print("- Try increasing the timeout value for slow networks")


if __name__ == '__main__':
    main()
