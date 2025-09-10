import asyncio
import logging
import wave
import numpy as np
import sys
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

logging.basicConfig(level=logging.FATAL)

# Audio configuration
samplerate = 48000
channels = 2
filename = "output.wav"
record_duration = 5
total_frames_to_record = record_duration * samplerate
frames_recorded = 0
done_writing_to_file = False
conn = None
connection_closed = False

wf = wave.open(filename, 'wb')
wf.setnchannels(channels)
wf.setsampwidth(2)
wf.setframerate(samplerate)

async def recv_audio_stream(frame):
    global frames_recorded, done_writing_to_file, conn, connection_closed

    if done_writing_to_file:
        return

    audio_data = np.frombuffer(frame.to_ndarray(), dtype=np.int16)
    wf.writeframes(audio_data.tobytes())
    frames_recorded += len(audio_data) // channels

    if frames_recorded >= total_frames_to_record:
        wf.close()
        print(f"Audio recording complete, saved to {filename}")
        done_writing_to_file = True
        connection_closed = True
        await conn.disconnect()

async def main():
    global conn, connection_closed
    try:
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        await conn.connect()
        conn.audio.switchAudioChannel(True)
        conn.audio.add_track_callback(recv_audio_stream)
        
        print(f"Starting audio recording for {record_duration} seconds...")

        await asyncio.sleep(record_duration + 1)

    except ValueError as e:
        logging.error(f"Error in WebRTC connection: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        if conn and not connection_closed:
            await conn.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        if not done_writing_to_file and 'wf' in globals():
            wf.close()
        sys.exit(0)
