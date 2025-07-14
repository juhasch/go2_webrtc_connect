#!/usr/bin/env python3
"""
Quick Heartbeat Test Utility

A simple script to verify heartbeat functionality with the Unitree Go2 robot.
Provides clear pass/fail results with minimal output.
"""

import asyncio
import logging
import sys
import time

from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

# Suppress most logging for clean output
logging.basicConfig(level=logging.WARNING)

async def quick_heartbeat_test(duration_seconds: int = 8, min_responses: int = 3):
    """
    Perform a quick heartbeat test.
    
    Args:
        duration_seconds: How long to test (default: 8 seconds)
        min_responses: Minimum responses needed to pass (default: 3)
    
    Returns:
        bool: True if test passes, False otherwise
    """
    conn = None
    try:
        print(f"🔗 Connecting to Go2...")
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        await conn.connect()
        
        print(f"💓 Testing heartbeat for {duration_seconds} seconds...")
        # Use the existing heartbeat instance from the data channel
        heartbeat = conn.datachannel.heartbeat
        heartbeat.start_heartbeat()
        
        start_time = time.time()
        last_count = 0
        
        # Test for specified duration
        while time.time() - start_time < duration_seconds:
            await asyncio.sleep(0.5)
            
            response_info = heartbeat.get_response_info()
            current_count = response_info['total_responses']
            
            # Show progress for new responses
            if current_count > last_count:
                print(f"   ✓ Response {current_count} received")
                last_count = current_count
        
        # Final results
        final_info = heartbeat.get_response_info()
        total_responses = final_info['total_responses']
        
        heartbeat.stop_heartbeat()
        await conn.disconnect()
        
        # Determine pass/fail
        passed = total_responses >= min_responses
        
        print(f"\n📊 Test Results:")
        print(f"   Responses received: {total_responses}")
        print(f"   Minimum required: {min_responses}")
        print(f"   Result: {'✅ PASS' if passed else '❌ FAIL'}")
        
        if not passed:
            print(f"\n💡 Troubleshooting tips:")
            print(f"   • Ensure Go2 is powered on and connected")
            print(f"   • Check network connectivity")
            print(f"   • Try running the advanced heartbeat monitor for more details")
        
        return passed
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        if conn:
            try:
                await conn.disconnect()
            except:
                pass
        return False

async def main():
    """Main entry point with command line argument support"""
    
    # Simple argument parsing
    duration = 8
    min_responses = 3
    
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print("Usage: python quick_heartbeat_test.py [duration_seconds] [min_responses]")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        try:
            min_responses = int(sys.argv[2])
        except ValueError:
            print("Usage: python quick_heartbeat_test.py [duration_seconds] [min_responses]")
            sys.exit(1)
    
    print("🤖 Go2 Quick Heartbeat Test")
    print("=" * 40)
    
    success = await quick_heartbeat_test(duration, min_responses)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1) 