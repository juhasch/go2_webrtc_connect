import logging
import asyncio
import os
import json
import signal
from go2_webrtc_driver.robot_helper import Go2RobotHelper
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
    logger.debug("Program interrupted by user. Cleaning up...")
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
        # Use high-level helper (minimal verbosity)
        async with Go2RobotHelper(enable_state_monitoring=False, logging_level=logging.ERROR) as robot:
            conn = robot.conn
            # Create audio hub instance
            audio_hub = WebRTCAudioHub(conn, logger)
            logger.debug("Audio hub initialized")

            # Define audio file to upload and play
            audio_file = "dog-barking.wav"
            audio_file_path = os.path.join(os.path.dirname(__file__), audio_file)
            logger.debug(f"Using audio file: {audio_file_path}")

            # Get the list of available audio files
            response = await audio_hub.get_audio_list()
            if response and isinstance(response, dict):
                data_str = response.get('data', {}).get('data', '{}')
                audio_list = json.loads(data_str).get('audio_list', [])

                # Extract filename without extension
                filename = os.path.splitext(audio_file)[0]

                # Check if file already exists by CUSTOM_NAME and store UUID
                existing_audio = next((audio for audio in audio_list if audio.get('CUSTOM_NAME') == filename), None)
                if existing_audio:
                    uuid = existing_audio.get('UNIQUE_ID')
                else:
                    uuid = None

                    # Upload the audio file
                    logger.debug("Starting audio file upload...")
                    await audio_hub.upload_audio_file(audio_file_path)
                    logger.debug("Audio file upload completed")

                    # Refresh and parse audio list after upload
                    response = await audio_hub.get_audio_list()
                    data_str = response.get('data', {}).get('data', '{}') if isinstance(response, dict) else '{}'
                    audio_list = json.loads(data_str).get('audio_list', [])
                    existing_audio = next((audio for audio in audio_list if audio.get('CUSTOM_NAME') == filename), None)
                    uuid = existing_audio.get('UNIQUE_ID') if existing_audio else None

            # Play the uploaded audio file using its filename as UUID
            if not uuid:
                logger.error("Audio file UUID not found after upload/list. Cannot start playback.")
                return
            print(f"Starting audio playback of file: {uuid}")
            await audio_hub.play_by_uuid(uuid)
            logger.debug("Audio playback completed")

            # Exit immediately after requesting playback
            print("Playback command sent. Exiting.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        logger.debug("Stopping audio and cleaning up...")
        
        # Clean up audio hub (connection handled by helper context)
        if audio_hub:
            try:
                audio_hub = None
            except Exception as e:
                logger.debug(f"Error cleaning up audio hub: {e}")
        
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
    
    logger.debug("Program exited successfully")
