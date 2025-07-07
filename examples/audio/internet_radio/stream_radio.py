import logging
import asyncio
import sys
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from aiortc.contrib.media import MediaPlayer


# Enable logging for debugging
logging.basicConfig(level=logging.FATAL)

async def cleanup_tasks():
    """Cancel and wait for all pending tasks to complete"""
    try:
        # Get all pending tasks
        tasks = [task for task in asyncio.all_tasks() if not task.done()]
        
        if tasks:
            logging.debug(f"Waiting for {len(tasks)} pending tasks to complete...")
            
            # Wait a moment for tasks to complete naturally
            await asyncio.sleep(0.1)
            
            # Check again for remaining tasks
            remaining_tasks = [task for task in asyncio.all_tasks() if not task.done()]
            
            if remaining_tasks:
                # Cancel any remaining tasks
                for task in remaining_tasks:
                    if not task.done():
                        task.cancel()
                
                # Wait for cancelled tasks to finish
                await asyncio.gather(*remaining_tasks, return_exceptions=True)
                
    except Exception as e:
        logging.debug(f"Error during task cleanup: {e}")

async def main():
    conn = None
    player = None
    
    try:
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        
        await conn.connect()

        stream_url = "https://streams.fluxfm.de/live/aac-64/audio/" #Radio ultra

        logging.info(f"Playing internet radio: {stream_url}")
        player = MediaPlayer(stream_url)  # Use MediaPlayer with the URL
        audio_track = player.audio  # Get the audio track from the player
        conn.pc.addTrack(audio_track)  # Add the audio track to the WebRTC connection

        await asyncio.sleep(3600)  # Keep the program running to handle events

    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Cleaning up...")
    except ValueError as e:
        logging.error(e)
    finally:
        # Cleanup resources
        if player:
            try:
                # Close the media player if it has a close method
                if hasattr(player, 'close'):
                    await player.close()
                elif hasattr(player, '_container') and hasattr(player._container, 'close'):
                    player._container.close()
            except Exception as e:
                logging.debug(f"Error closing player: {e}")
        
        if conn:
            try:
                await conn.disconnect()
                # Give a moment for cleanup to complete
                await asyncio.sleep(0.2)
            except Exception as e:
                logging.debug(f"Error disconnecting: {e}")
        
        # Clean up any remaining tasks
        await cleanup_tasks()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This should not be reached due to handling in main(), but kept as safety net
        pass
    print("Program exited successfully")