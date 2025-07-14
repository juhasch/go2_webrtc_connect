import logging
import asyncio
import os 
import sys
import signal
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from aiortc.contrib.media import MediaPlayer


# Enable logging for debugging
logging.basicConfig(level=logging.FATAL)

# Global variables for cleanup
conn = None
player = None
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle SIGINT (Ctrl+C) gracefully"""
    print("\nProgram interrupted by user. Cleaning up...")
    shutdown_event.set()

async def cleanup_tasks():
    """Cancel and wait for all pending tasks to complete"""
    try:
        # Give more time for aiortc internal cleanup
        await asyncio.sleep(0.5)
        
        # Get current task to avoid canceling ourselves
        current_task = asyncio.current_task()
        
        # Get all pending tasks except current one
        tasks = [task for task in asyncio.all_tasks() 
                if not task.done() and task != current_task]
        
        if tasks:
            logging.debug(f"Waiting for {len(tasks)} pending tasks to complete...")
            
            # Wait a bit more for natural completion
            await asyncio.sleep(0.3)
            
            # Check again for remaining tasks
            remaining_tasks = [task for task in asyncio.all_tasks() 
                             if not task.done() and task != current_task]
            
            if remaining_tasks:
                # Cancel remaining tasks
                for task in remaining_tasks:
                    if not task.done():
                        task.cancel()
                
                # Wait for cancelled tasks, suppress expected errors
                try:
                    await asyncio.gather(*remaining_tasks, return_exceptions=True)
                except Exception:
                    # Suppress exceptions from cancelled tasks
                    pass
                
    except Exception as e:
        logging.debug(f"Error during task cleanup: {e}")

async def main():
    global conn, player
    
    # Install signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Choose a connection method (uncomment the correct one)
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        
        await conn.connect()

        mp3_path = os.path.join(os.path.dirname(__file__), "dora-doradura-mp3.mp3")
        
        logging.info(f"Playing MP3: {mp3_path}")
        player = MediaPlayer(mp3_path)  # Use MediaPlayer for MP3
        audio_track = player.audio  # Get the audio track from the player
        conn.pc.addTrack(audio_track)  # Add the audio track to the WebRTC connection

        # Wait for shutdown signal instead of fixed time
        await shutdown_event.wait()

    except ValueError as e:
        # Log any value errors that occur during the process.
        logging.error(f"An error occurred: {e}")
    finally:
        print("Stopping media and cleaning up...")
        
        # Stop media player first to stop audio streaming
        if player:
            try:
                # Close the media player if it has a close method
                if hasattr(player, 'close'):
                    await player.close()
                elif hasattr(player, '_container') and hasattr(player._container, 'close'):
                    player._container.close()
            except Exception as e:
                logging.debug(f"Error closing player: {e}")
        
        # Then disconnect WebRTC
        if conn:
            try:
                # Suppress aiortc connection errors during shutdown
                original_level = logging.getLogger('aiortc').level
                logging.getLogger('aiortc').setLevel(logging.CRITICAL)
                
                await conn.disconnect()
                
                # Restore original logging level
                logging.getLogger('aiortc').setLevel(original_level)
                
            except Exception as e:
                logging.debug(f"Error disconnecting: {e}")
        
        # Clean up any remaining tasks
        await cleanup_tasks()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This should not be reached due to signal handling, but kept as safety net
        pass
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    print("Program exited successfully")

