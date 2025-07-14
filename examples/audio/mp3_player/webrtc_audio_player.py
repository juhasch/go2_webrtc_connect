import logging
import asyncio
import os
import json
import signal
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.webrtc_audiohub import WebRTCAudioHub

# Enable logging for debugging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Global variables for cleanup
conn = None
audio_hub = None
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle SIGINT (Ctrl+C) gracefully"""
    logger.info("Program interrupted by user. Cleaning up...")
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
            logger.debug(f"Waiting for {len(tasks)} pending tasks to complete...")
            
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
        logger.debug(f"Error during task cleanup: {e}")

async def main():
    global conn, audio_hub
    
    # Install signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Establish WebRTC connection
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        await conn.connect()
        logger.info("WebRTC connection established")

        # Create audio hub instance
        audio_hub = WebRTCAudioHub(conn, logger)
        logger.info("Audio hub initialized")

        # Define audio file to upload and play
        audio_file = "dog-barking.wav"
        audio_file_path = os.path.join(os.path.dirname(__file__), audio_file)
        logger.info(f"Using audio file: {audio_file_path}")

        # Get the list of available audio files
        response = await audio_hub.get_audio_list()
        if response and isinstance(response, dict):
            data_str = response.get('data', {}).get('data', '{}')
            audio_list = json.loads(data_str).get('audio_list', [])
            
            # Extract filename without extension
            filename = os.path.splitext(audio_file)[0]
            print(audio_list)
            # Check if file already exists by CUSTOM_NAME and store UUID
            existing_audio = next((audio for audio in audio_list if audio['CUSTOM_NAME'] == filename), None)
            if existing_audio:
                print(f"Audio file {filename} already exists, skipping upload")
                uuid = existing_audio['UNIQUE_ID']
            else:
                print(f"Audio file {filename} not found, proceeding with upload")
                uuid = None

                # Upload the audio file
                logger.info("Starting audio file upload...")
                await audio_hub.upload_audio_file(audio_file_path)
                logger.info("Audio file upload completed")
                response = await audio_hub.get_audio_list()
                existing_audio = next((audio for audio in audio_list if audio['CUSTOM_NAME'] == filename), None)
                uuid = existing_audio['UNIQUE_ID']

        # Play the uploaded audio file using its filename as UUID
        print(f"Starting audio playback of file: {uuid}")
        await audio_hub.play_by_uuid(uuid)
        logger.info("Audio playback completed")

        # Wait for shutdown signal instead of exiting immediately
        print("Audio playback finished. Press Ctrl+C to exit.")
        await shutdown_event.wait()

    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        logger.info("Stopping audio and cleaning up...")
        
        # Clean up audio hub first
        if audio_hub:
            try:
                # Stop any ongoing audio operations
                # Note: WebRTCAudioHub might need specific cleanup methods
                # For now, we'll just clear the reference
                audio_hub = None
            except Exception as e:
                logger.debug(f"Error cleaning up audio hub: {e}")
        
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
                logger.debug(f"Error disconnecting: {e}")
        
        # Clean up any remaining tasks
        await cleanup_tasks()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This should not be reached due to signal handling, but kept as safety net
        pass
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    
    logger.info("Program exited successfully")
