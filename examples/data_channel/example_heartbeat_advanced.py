import asyncio
import logging
import sys
import time
from collections import deque
from typing import List, Dict

from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.msgs.heartbeat import WebRTCDataChannelHeartBeat

# Enable logging for debugging
logging.basicConfig(level=logging.INFO)

class HeartbeatMonitor:
    """Advanced heartbeat monitoring with statistics and health analysis"""
    
    def __init__(self, heartbeat_manager):
        self.heartbeat = heartbeat_manager
        self.response_times = deque(maxlen=50)  # Keep last 50 response times
        self.response_intervals = deque(maxlen=49)  # Intervals between responses
        self.start_time = time.time()
        self.last_check_time = self.start_time
        self.missed_responses = 0
        self.expected_responses = 0
        
    def update_statistics(self):
        """Update monitoring statistics"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Calculate expected responses (every 2 seconds)
        self.expected_responses = max(1, int(elapsed / 2))
        
        # Track response timing
        response_info = self.heartbeat.get_response_info()
        if response_info['last_response_time'] and response_info['last_response_time'] not in self.response_times:
            self.response_times.append(response_info['last_response_time'])
            
            # Calculate intervals between responses
            if len(self.response_times) >= 2:
                interval = self.response_times[-1] - self.response_times[-2]
                self.response_intervals.append(interval)
        
        # Calculate missed responses
        actual_responses = response_info['total_responses']
        self.missed_responses = max(0, self.expected_responses - actual_responses)
        
        return {
            'elapsed_time': elapsed,
            'expected_responses': self.expected_responses,
            'actual_responses': actual_responses,
            'missed_responses': self.missed_responses,
            'success_rate': (actual_responses / self.expected_responses * 100) if self.expected_responses > 0 else 0,
            'avg_interval': sum(self.response_intervals) / len(self.response_intervals) if self.response_intervals else 0,
            'connection_health': self._assess_connection_health(actual_responses, self.expected_responses)
        }
    
    def _assess_connection_health(self, actual: int, expected: int) -> str:
        """Assess connection health based on response statistics"""
        if expected == 0:
            return "INITIALIZING"
        
        success_rate = (actual / expected) * 100
        
        if success_rate >= 90:
            return "EXCELLENT"
        elif success_rate >= 75:
            return "GOOD"
        elif success_rate >= 50:
            return "FAIR"
        elif success_rate >= 25:
            return "POOR"
        else:
            return "CRITICAL"

async def main():
    conn = None
    try:
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)

        # Connect to the WebRTC service
        print("🔗 Connecting to WebRTC...")
        await conn.connect()
        print("✅ Connected to WebRTC successfully!")

        # Use the existing heartbeat instance from the data channel
        # (Don't create a new one - responses go to the original instance)
        heartbeat = conn.datachannel.heartbeat
        monitor = HeartbeatMonitor(heartbeat)

        # Start sending heartbeats
        print("💓 Starting heartbeat transmission...")
        heartbeat.start_heartbeat()

        print("\n🔍 Advanced Heartbeat Monitoring")
        print("=" * 60)
        print("Monitoring for 20 seconds with detailed diagnostics...")
        print("Expected heartbeat frequency: every 2 seconds")
        print("Checking every 1 second for real-time monitoring\n")

        # Monitor for 20 seconds with 1-second intervals for detailed tracking
        for i in range(20):
            await asyncio.sleep(1)
            
            # Check for new responses
            has_new_response = heartbeat.check_and_reset_new_response_flag()
            stats = monitor.update_statistics()
            
            # Real-time status display
            status_icon = "✓" if has_new_response else "⏳"
            health_icons = {
                "EXCELLENT": "🟢", "GOOD": "🟡", "FAIR": "🟠", 
                "POOR": "🔴", "CRITICAL": "💀", "INITIALIZING": "🔵"
            }
            
            print(f"[{stats['elapsed_time']:5.1f}s] {status_icon} "
                  f"Responses: {stats['actual_responses']:2d}/{stats['expected_responses']:2d} "
                  f"({stats['success_rate']:5.1f}%) "
                  f"{health_icons[stats['connection_health']]} {stats['connection_health']}")
            
            # Detailed info every 5 seconds
            if (i + 1) % 5 == 0:
                print(f"    📊 Missed: {stats['missed_responses']}, "
                      f"Avg interval: {stats['avg_interval']:.1f}s, "
                      f"Expected: 2.0s")
                
                # Warning if connection seems problematic
                if stats['connection_health'] in ['POOR', 'CRITICAL']:
                    print(f"    ⚠️  Connection health is {stats['connection_health']} - check network stability")

        # Final comprehensive analysis
        final_stats = monitor.update_statistics()
        print(f"\n📈 Final Analysis")
        print("=" * 60)
        print(f"🕐 Total monitoring time: {final_stats['elapsed_time']:.1f} seconds")
        print(f"📡 Expected responses: {final_stats['expected_responses']}")
        print(f"✅ Actual responses: {final_stats['actual_responses']}")
        print(f"❌ Missed responses: {final_stats['missed_responses']}")
        print(f"📊 Success rate: {final_stats['success_rate']:.1f}%")
        
        if monitor.response_intervals:
            print(f"⏱️  Average response interval: {final_stats['avg_interval']:.2f}s (expected: 2.00s)")
            print(f"⏱️  Min interval: {min(monitor.response_intervals):.2f}s")
            print(f"⏱️  Max interval: {max(monitor.response_intervals):.2f}s")
        
        print(f"🏥 Final connection health: {final_stats['connection_health']}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        if final_stats['success_rate'] >= 90:
            print("   ✅ Connection is stable and performing well")
        elif final_stats['success_rate'] >= 75:
            print("   🟡 Connection is mostly stable with occasional drops")
        else:
            print("   🔴 Connection instability detected - consider:")
            print("      • Checking network connectivity")
            print("      • Verifying robot is powered and accessible")
            print("      • Testing with different connection methods")

        # Stop heartbeats when done
        print(f"\n🛑 Stopping heartbeat transmission...")
        heartbeat.stop_heartbeat()
        print("✅ Heartbeat stopped successfully!")

    except KeyboardInterrupt:
        print("\n⏹️  Program interrupted by user")
    except ValueError as e:
        logging.error(f"❌ Configuration error: {e}")
    except Exception as e:
        logging.error(f"💥 Unexpected error: {e}")
    finally:
        # Ensure proper cleanup of the WebRTC connection
        if conn:
            try:
                await conn.disconnect()
                print("🔌 WebRTC connection closed successfully")
            except Exception as e:
                logging.error(f"❌ Error closing WebRTC connection: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass 