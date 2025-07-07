#!/usr/bin/env python3
"""
Debug script for WebRTC connection issues
"""
import asyncio
import logging
import sys
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def debug_connection():
    """Debug WebRTC connection with detailed logging"""
    try:
        print("=== WebRTC Connection Debug ===")
        
        # Choose connection method - adjust IP as needed
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        
        print(f"Connection method: {conn.connectionMethod}")
        print(f"Robot IP: {conn.ip}")
        
        # Connect with timeout handling
        print("\n1. Attempting WebRTC connection...")
        await conn.connect()
        
        print("2. Connection established! Checking data channel...")
        
        # Check data channel state
        if conn.datachannel:
            print(f"   Data channel exists: {conn.datachannel is not None}")
            print(f"   Data channel ready: {conn.datachannel.is_open()}")
            print(f"   Channel state: {conn.datachannel.channel.readyState}")
        
        print("3. Testing basic communication...")
        
        # Test a simple subscription
        def test_callback(message):
            print(f"   Received message: {message.get('type', 'unknown')}")
        
        conn.datachannel.pub_sub.subscribe("rt/lf/lowstate", test_callback)
        
        # Wait and monitor
        print("4. Monitoring for 10 seconds...")
        for i in range(10):
            await asyncio.sleep(1)
            if conn.datachannel.is_open():
                print(f"   [{i+1}/10] Data channel is open ✓")
            else:
                print(f"   [{i+1}/10] Data channel not ready ✗")
        
        print("5. Debug complete!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_connection()) 