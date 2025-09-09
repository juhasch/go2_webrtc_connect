
"""
Record LiDAR and Video streams from the Unitree Go2 via WebRTC.

Outputs:
- Video: MP4 files using OpenCV VideoWriter (H.264 codec)
- LiDAR: binary .lidarlog with frames as: magic, (uint32 npts, uint64 ts_us), float32 xyz... per frame

Usage examples:
  python apps/webxr/record_lidar_video.py --video-out out.mp4 --lidar-out out.lidarlog
  python apps/webxr/record_lidar_video.py --method sta --decoder libvoxel \
         --video-out ~/captures/go2_cam.mp4 --lidar-out ~/captures/go2.lidarlog

The .lidarlog can be replayed by the WebXR server using:
  python apps/webxr/server.py --no-robot --replay-video out.mp4 --replay-lidar out.lidarlog --replay-loop
"""

import argparse
import asyncio
import logging
import os
import signal
import struct
import time
from typing import Optional, Any, Dict

from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

import numpy as np



MAGIC = b"LIDARLOGv1\n"
HEADER_FMT = "<IQ"  # uint32 n_points, uint64 ts_us
HEADER_SZ = struct.calcsize(HEADER_FMT)


class LidarBinaryWriter:
    def __init__(self, path: str) -> None:
        self.path = os.path.expanduser(path)
        self._f = open(self.path, "wb")
        self._f.write(MAGIC)
        self._frames = 0

    def write_frame(self, points: np.ndarray, ts_us: int) -> None:
        if points is None or points.size == 0:
            npts = 0
            header = struct.pack(HEADER_FMT, npts, int(ts_us))
            self._f.write(header)
            return
        pts = np.asarray(points, dtype=np.float32)
        if pts.ndim == 1:
            n = (pts.size // 3) * 3
            pts = pts[:n].reshape(-1, 3)
        elif pts.ndim >= 2 and pts.shape[1] >= 3:
            pts = pts[:, :3]
        else:
            pts = pts.reshape(-1, 3)
        npts = int(pts.shape[0])
        header = struct.pack(HEADER_FMT, npts, int(ts_us))
        self._f.write(header)
        if npts:
            self._f.write(pts.astype(np.float32, copy=False).ravel().tobytes())
        self._frames += 1

    def close(self) -> None:
        try:
            self._f.close()
        finally:
            pass


class Recorder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.conn: Optional[Go2WebRTCConnection] = None
        self.video_writer = None
        self.lidar_writer: Optional[LidarBinaryWriter] = None
        self._stop = asyncio.Event()
        self._video_started = False
        self._lidar_frames = 0
        self._video_frames = 0
        self._video_path = None
        self._start_time = time.time()

    async def start(self) -> None:
        method_map = {
            "ap": WebRTCConnectionMethod.LocalAP,
            "sta": WebRTCConnectionMethod.LocalSTA,
            "remote": WebRTCConnectionMethod.Remote,
        }
        connection_method = method_map.get(self.args.method, WebRTCConnectionMethod.LocalSTA)

        self.conn = Go2WebRTCConnection(
            connection_method,
            ip=self.args.ip,
        )
        await self.conn.connect()

        # Video
        if self.args.video_out:
            video_path = os.path.expanduser(self.args.video_out)
            self._video_path = video_path
            
            import cv2
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = None
            
            async def recv_camera_stream(track):
                if self._video_started:
                    return
                try:
                    self._video_started = True
                    frame_count = 0
                    while not self._stop.is_set():
                        try:
                            frame = await track.recv()
                            frame_count += 1
                            
                            # Convert frame to OpenCV format
                            img = frame.to_ndarray(format="bgr24")
                            
                            # Initialize video writer on first frame
                            if self.video_writer is None:
                                height, width = img.shape[:2]
                                self.video_writer = cv2.VideoWriter(video_path, fourcc, 30.0, (width, height))
                            
                            # Write frame to video file
                            self.video_writer.write(img)
                            
                            # Log progress every 30 frames
                            if frame_count % 30 == 0:
                                elapsed = time.time() - self._start_time
                                fps = frame_count / elapsed if elapsed > 0 else 0
                                logging.info("Video: %d frames (%.1f fps)", frame_count, fps)
                                
                        except asyncio.CancelledError:
                            break
                        except Exception as e:
                            logging.error("Video error: %s", e)
                            break
                            
                except Exception as e:
                    logging.error("Video recording failed: %s", e)

            self.conn.video.switchVideoChannel(True)
            self.conn.video.add_track_callback(recv_camera_stream)

        # LiDAR
        if self.args.lidar_out:
            lidar_path = os.path.expanduser(self.args.lidar_out)
            self.lidar_writer = LidarBinaryWriter(lidar_path)
            await self.conn.datachannel.disableTrafficSaving(True)
            try:
                self.conn.datachannel.set_decoder(decoder_type=self.args.decoder)
            except Exception:
                self.conn.datachannel.set_decoder(decoder_type="native")
            
            self.conn.datachannel.pub_sub.publish_without_callback("rt/utlidar/switch", "on")

            def lidar_cb(message: Dict[str, Any]) -> None:
                try:
                    data = message.get("data", {}).get("data", {})
                    ts_us = int(message.get("data", {}).get("timestamp_us") or time.time() * 1e6)
                    pts_arr: Optional[np.ndarray] = None
                    if "points" in data:
                        pts = data["points"]
                        if callable(pts):
                            pts = pts()
                        pts_arr = np.asarray(pts, dtype=np.float32)
                    elif "positions" in data:
                        pos = data.get("positions", [])
                        pos = np.asarray(pos, dtype=np.float32)
                        n = (pos.size // 3) * 3
                        pts_arr = pos[:n].reshape(-1, 3)
                    if self.lidar_writer is not None and pts_arr is not None:
                        self.lidar_writer.write_frame(pts_arr, ts_us)
                        self._lidar_frames += 1
                        if self._lidar_frames % 50 == 0:
                            elapsed = time.time() - self._start_time
                            rate = self._lidar_frames / elapsed if elapsed > 0 else 0
                            logging.info("LiDAR: %d frames (%.1f fps)", self._lidar_frames, rate)
                except Exception:
                    pass

            self.conn.datachannel.pub_sub.subscribe("rt/utlidar/voxel_map_compressed", lidar_cb)
            try:
                self.conn.datachannel.pub_sub.subscribe("rt/utlidar/voxel_map", lidar_cb)
            except Exception:
                pass

        # Optional max-seconds timer
        if self.args.max_seconds and self.args.max_seconds > 0:
            async def _timer():
                await asyncio.sleep(self.args.max_seconds)
                self._stop.set()
            asyncio.create_task(_timer())

        # Handle SIGINT/SIGTERM
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:
                pass

        # Check if we're actually recording anything
        if not self.args.video_out and not self.args.lidar_out:
            logging.warning("No output files specified! Use --video-out and/or --lidar-out")
            logging.info("Connected but not recording. Press Ctrl+C to stop.")
        else:
            logging.info("Recording started! Press Ctrl+C to stop.")
        
        await self._stop.wait()

    async def stop(self) -> None:
        if self.video_writer:
            try:
                self.video_writer.release()
            except Exception:
                pass
            self.video_writer = None

        if self.lidar_writer:
            try:
                self.lidar_writer.close()
            except Exception:
                pass
            self.lidar_writer = None

        if self.conn:
            try:
                await self.conn.disconnect()
            except Exception:
                pass
            self.conn = None

        elapsed = time.time() - self._start_time
        logging.info("Recording completed in %.1f seconds", elapsed)
        if self._video_frames > 0 or self._lidar_frames > 0:
            logging.info("Final counts - Video: %d frames, LiDAR: %d frames", self._video_frames, self._lidar_frames)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Record Go2 LiDAR and Video via WebRTC",
        epilog="Examples:\n"
               "  %(prog)s --video-out test.mp4 --lidar-out test.lidarlog\n"
               "  %(prog)s --method sta --video-out ~/captures/go2.mkv\n"
               "  %(prog)s --lidar-out data.lidarlog --max-seconds 30",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--method", choices=["ap", "sta", "remote"], default="sta")
    p.add_argument("--ip", type=str, default=os.getenv("ROBOT_IP"), help="Robot IP for STA/AP mode (env ROBOT_IP as default)")
    p.add_argument("--decoder", choices=["libvoxel", "native"], default="native")
    p.add_argument("--video-out", type=str, default=None, help="Output video file (e.g., out.mp4)")
    p.add_argument("--lidar-out", type=str, default=None, help="Output LiDAR .lidarlog file")
    p.add_argument("--max-seconds", type=int, default=0, help="Stop after N seconds (0 = infinite)")
    p.add_argument("--quiet", action="store_true", help="Reduce log verbosity")
    return p.parse_args()


async def amain(args: argparse.Namespace) -> None:
    if args.quiet:
        logging.basicConfig(level=logging.WARNING)
    else:
        logging.basicConfig(level=logging.INFO)
    rec = Recorder(args)
    try:
        await rec.start()
    finally:
        await rec.stop()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


