#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import os
import time
import ssl
from typing import Any, Dict, List, Optional
import numpy as np
import contextlib


from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import RTC_TOPIC, MCF_CMD, SPORT_CMD, DATA_CHANNEL_TYPE
from go2_webrtc_driver.constants import WebRTCConnectionMethod
from go2_webrtc_driver.cli_go2action import SUPPORTED_ACTIONS

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRelay, MediaPlayer
from aiohttp import web, ClientSession


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webxr")


class RobotVRServer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.robot: Optional[Go2RobotHelper] = None
        self.robot_video_track: Optional[MediaStreamTrack] = None
        self.video_relay: Optional[MediaRelay] = None
        self._video_player: Optional[MediaPlayer] = None

        # Web clients state
        self.pcs: List[RTCPeerConnection] = []
        self.control_channels: List[Any] = []  # aiortc RTCDataChannel
        self.lidar_channels: List[Any] = []

        # LiDAR throttling
        self.last_lidar_sent_ts: float = 0.0
        self.lidar_min_interval_s: float = 0.05  # 20 Hz cap to clients
        self.lidar_max_points: int = 8000        # downsample cap

        # Movement throttling
        self.last_move_ts: float = 0.0
        self.move_interval_s: float = 0.05  # 20 Hz
        self.obstacle_enabled: bool = False
        self.fast_move: bool = os.getenv("WEBXR_FAST_MOVE", "1") != "0"
        # LiDAR RX logging state
        self._lidar_rx_count: int = 0
        self._lidar_last_log_ts: float = 0.0
        # LiDAR replay
        self._lidar_replay_task: Optional[asyncio.Task] = None

        # Robot state cache (for assistant context)
        self.latest_state: Dict[str, Any] | None = None

        # Joystick logging state
        self._move_rx_count: int = 0
        self._move_last_log_ts: float = 0.0

    # ---------------- Robot side -----------------
    async def start_robot(self) -> None:
        method_map = {
            "ap": WebRTCConnectionMethod.LocalAP,
            "sta": WebRTCConnectionMethod.LocalSTA,
            "remote": WebRTCConnectionMethod.Remote,
        }
        connection_method = method_map.get(self.args.method, WebRTCConnectionMethod.LocalSTA)

        if self.args.no_robot:
            logger.warning("Starting WebXR server without robot connection (--no-robot)")
            # If replay is requested, set up simulated sources
            await self._maybe_start_replay_sources()
            return

        self.robot = Go2RobotHelper(
            connection_method=connection_method,
            serial_number=self.args.serial,
            ip=self.args.ip,
            username=self.args.username,
            password=self.args.password,
            enable_state_monitoring=False,
            detailed_state_display=False,
            logging_level=logging.ERROR,
        )
        try:
            # Allow slower robots: override with env GO2_DCH_TIMEOUT_S, default 10s
            await self.robot.__aenter__()
        except SystemExit:
            logger.error("Robot connection failed (data channel not ready). Serving UI without robot. "
                         "Check ROBOT_IP and network, and try GO2_DCH_TIMEOUT_S=15")
            self.robot = None
            return

        # Prepare programmatic control (same semantics as gamepad controller)
        await self.robot.prepare_programmatic_control()

        # Enable video and capture the track via callback
        conn = self.robot.conn
        assert conn is not None
        conn.video.switchVideoChannel(True)

        async def on_video(track: MediaStreamTrack):
            # First frame arrives via track.recv() inside webrtc_driver;
            # here we just store the track and set up a relay
            logger.info("Robot video track available")
            self.robot_video_track = track
            if self.video_relay is None:
                self.video_relay = MediaRelay()
            # Add to existing PCs dynamically
            for pc in list(self.pcs):
                try:
                    pc.addTrack(self.video_relay.subscribe(self.robot_video_track))
                    setattr(pc, "_has_robot_video", True)
                except Exception:
                    pass

        conn.video.add_track_callback(on_video)

        # LiDAR: request stream and subscribe
        await conn.datachannel.disableTrafficSaving(True)
        decoder_type = os.getenv("GO2_LIDAR_DECODER", "libvoxel")
        try:
            conn.datachannel.set_decoder(decoder_type=decoder_type)
            logger.info("LiDAR decoder set to %s", decoder_type)
        except Exception:
            logger.warning("Failed to set decoder %s, falling back to native", decoder_type)
            conn.datachannel.set_decoder(decoder_type="native")
        conn.datachannel.pub_sub.publish_without_callback("rt/utlidar/switch", "on")
        logger.info("LiDAR switch:on published; subscribing to voxel topics")

        def lidar_subscriber(message: Dict[str, Any]):
            # Offload to event loop task (non-blocking)
            try:
                now = time.time()
                sz = 0
                d = message.get('data', {}).get('data')
                if isinstance(d, dict):
                    if 'points' in d:
                        pts = d['points']
                        try:
                            sz = len(pts() if callable(pts) else pts)
                        except Exception:
                            sz = 0
                    elif 'positions' in d and hasattr(d['positions'], '__len__'):
                        sz = len(d['positions']) // 3
                self._lidar_rx_count += 1
                # Log first few and then rate every ~2s
                if self._lidar_rx_count <= 5 or (now - self._lidar_last_log_ts) >= 2.0:
                    logger.info("LiDAR RX: frame #%d, est_points=%d", self._lidar_rx_count, sz)
                    self._lidar_last_log_ts = now
            except Exception:
                logger.info("LiDAR RX: error parsing message")
            asyncio.create_task(self._handle_lidar_msg(message))

        conn.datachannel.pub_sub.subscribe("rt/utlidar/voxel_map_compressed", lidar_subscriber)
        # Fallback subscribe to non-compressed topic as well
        try:
            conn.datachannel.pub_sub.subscribe("rt/utlidar/voxel_map", lidar_subscriber)
        except Exception:
            pass

        # Subscribe to state for lightweight status answers
        try:
            from go2_webrtc_driver.constants import RTC_TOPIC

            def state_cb(message: Dict[str, Any]) -> None:
                try:
                    self.latest_state = message.get("data")
                except Exception:
                    pass

            conn.datachannel.pub_sub.subscribe(RTC_TOPIC['LF_SPORT_MOD_STATE'], state_cb)
        except Exception:
            logger.debug("State subscription not available")

    async def stop_robot(self) -> None:
        try:
            if self.robot:
                await self.robot.__aexit__(None, None, None)
            # Stop replay sources
            try:
                if self._lidar_replay_task:
                    self._lidar_replay_task.cancel()
                    with contextlib.suppress(Exception):
                        await self._lidar_replay_task
            except Exception:
                pass
            try:
                if self._video_player:
                    with contextlib.suppress(Exception):
                        await self._video_player.stop()
            except Exception:
                pass
        finally:
            self.robot = None
            self.robot_video_track = None
            self.video_relay = None
            self._video_player = None
            self._lidar_replay_task = None

    async def _handle_lidar_msg(self, message: Dict[str, Any]) -> None:
        now = time.time()
        if now - self.last_lidar_sent_ts < self.lidar_min_interval_s:
            return

        try:
            data = message.get("data", {}).get("data", {})
            src = ""
            np_points: Optional[np.ndarray] = None
            if "points" in data:
                pts = data["points"]
                if callable(pts):
                    pts = pts()
                # pts is likely a list-of-triplets or ndarray
                arr = np.asarray(pts)
                # Normalize to (N,3)
                if arr.ndim == 1:
                    n = (arr.size // 3) * 3
                    arr = arr[:n].reshape(-1, 3)
                elif arr.ndim >= 2 and arr.shape[1] >= 3:
                    arr = arr[:, :3]
                else:
                    arr = arr.reshape(-1, 3)
                np_points = arr.astype(np.float32, copy=False)
                src = "points"
            elif "positions" in data:
                pos = data.get("positions", [])
                arr = np.asarray(pos, dtype=np.float32)
                n = (arr.size // 3) * 3
                arr = arr[:n].reshape(-1, 3)
                np_points = arr
                src = "positions"
            else:
                np_points = None
                src = "unknown"

            # Downsample
            buf = b""
            out_pts = 0
            if np_points is not None and np_points.size:
                npts = np_points.shape[0]
                step = 1
                if npts > self.lidar_max_points:
                    step = max(1, npts // self.lidar_max_points)
                    np_points = np_points[::step]
                    npts = np_points.shape[0]
                # Flatten to bytes
                buf = np_points.astype(np.float32, copy=False).ravel().tobytes()
                out_pts = npts
            else:
                # No usable points decoded
                buf = b""
                out_pts = 0

            # Broadcast on lidar channels
            sent_count = 0
            for ch in list(self.lidar_channels):
                if ch.readyState == "open":
                    try:
                        ch.send(buf)
                        sent_count += 1
                    except Exception:
                        pass

            self.last_lidar_sent_ts = now
            if sent_count:
                logger.info("LiDAR TX: %d points to %d clients, %d bytes (src=%s)", out_pts, sent_count, len(buf), src)
            else:
                logger.info("LiDAR TX: no open clients; dropping frame (%d points, src=%s)", out_pts, src)
        except Exception as e:
            logger.debug(f"LiDAR processing error: {e}")

    # ---------------- Replay sources (no-robot) -----------------
    async def _maybe_start_replay_sources(self) -> None:
        # Video replay via FFmpeg player if provided
        if getattr(self.args, "replay_video", None):
            try:
                opts = {"-re": "1"}
                if getattr(self.args, "replay_loop", False):
                    # Loop indefinitely (-1)
                    opts["-stream_loop"] = "-1"
                self._video_player = MediaPlayer(self.args.replay_video, options=opts)
                if self._video_player.video:
                    self.robot_video_track = self._video_player.video
                    if self.video_relay is None:
                        self.video_relay = MediaRelay()
                    # Attach to any existing PCs
                    for pc in list(self.pcs):
                        try:
                            pc.addTrack(self.video_relay.subscribe(self.robot_video_track))
                            setattr(pc, "_has_robot_video", True)
                        except Exception:
                            pass
                    logger.info("Replay video source attached: %s", self.args.replay_video)
            except Exception as e:
                logger.error("Failed to start replay video '%s': %s", self.args.replay_video, e)

        # LiDAR replay from .lidarlog
        if getattr(self.args, "replay_lidar", None):
            try:
                self._lidar_replay_task = asyncio.create_task(self._run_lidar_replay(
                    self.args.replay_lidar,
                    speed=float(getattr(self.args, "replay_speed", 1.0) or 1.0),
                    loop=bool(getattr(self.args, "replay_loop", False)),
                ))
                logger.info("LiDAR replay started: %s", self.args.replay_lidar)
            except Exception as e:
                logger.error("Failed to start LiDAR replay '%s': %s", self.args.replay_lidar, e)

    async def _run_lidar_replay(self, path: str, speed: float = 1.0, loop: bool = False) -> None:
        import struct
        MAGIC = b"LIDARLOGv1\n"
        HEADER_FMT = "<IQ"  # uint32 n_points, uint64 ts_us
        HEADER_SZ = struct.calcsize(HEADER_FMT)

        async def _broadcast(buf: bytes) -> None:
            sent = 0
            for ch in list(self.lidar_channels):
                if getattr(ch, "readyState", None) == "open":
                    try:
                        ch.send(buf)
                        sent += 1
                    except Exception:
                        pass
            if sent:
                logger.info("LiDAR TX(replay): %d bytes to %d clients", len(buf), sent)

        while True:
            try:
                with open(path, "rb") as f:
                    hdr = f.read(len(MAGIC))
                    if hdr != MAGIC:
                        logger.error("Invalid lidar log (magic mismatch): %s", path)
                        return
                    prev_ts: Optional[int] = None
                    while True:
                        h = f.read(HEADER_SZ)
                        if not h or len(h) < HEADER_SZ:
                            break
                        npts, ts_us = struct.unpack(HEADER_FMT, h)
                        num_floats = npts * 3
                        payload_bytes = num_floats * 4
                        buf = f.read(payload_bytes)
                        if not buf or len(buf) < payload_bytes:
                            break
                        # pacing
                        if prev_ts is not None and speed > 0:
                            dt = max(0.0, (ts_us - prev_ts) / 1_000_000.0)
                            if dt > 0:
                                await asyncio.sleep(dt / max(1e-6, speed))
                        prev_ts = ts_us
                        await _broadcast(buf)
                if not loop:
                    return
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error("LiDAR replay error: %s", e)
                await asyncio.sleep(1.0)

    # ---------------- Web (browser) side -----------------
    async def index(self, request: web.Request) -> web.Response:
        return web.FileResponse(path=os.path.join(os.path.dirname(__file__), "static", "index.html"))

    async def offer(self, request: web.Request) -> web.Response:
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection()
        self.pcs.append(pc)
        logger.info("Created PC %s", id(pc))

        @pc.on("datachannel")
        def on_datachannel(channel) -> None:
            try:
                label = getattr(channel, 'label', '')
            except Exception:
                label = ''
            logger.info("peer %s datachannel '%s'", id(pc), label)
            if label == 'control':
                self._setup_control_channel(channel)
            elif label == 'lidar':
                self._setup_lidar_channel(channel)

        # Add relayed robot video track if available
        if self.robot_video_track is not None and self.video_relay is not None:
            pc.addTrack(self.video_relay.subscribe(self.robot_video_track))
            setattr(pc, "_has_robot_video", True)
            logger.info("attached robot video to peer %s", id(pc))

        @pc.on("iceconnectionstatechange")
        async def on_ice_state_change() -> None:
            if pc.iceConnectionState in ("failed", "closed", "disconnected"):
                await self._cleanup_pc(pc)

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.json_response(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        )

    async def _cleanup_pc(self, pc: RTCPeerConnection) -> None:
        if pc in self.pcs:
            self.pcs.remove(pc)
        try:
            await pc.close()
        except Exception:
            pass

    async def realtime_session(self, request: web.Request) -> web.Response:
        """Issue an ephemeral Realtime session token for the browser."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return web.json_response({"enabled": False, "error": "OPENAI_API_KEY not set"}, status=400)
        model = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")
        body = {
            "model": model,
            # Optional defaults suitable for browser
            "voice": "verse",
            # Low-latency TTS; server may choose output format; default OK
        }
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    "https://api.openai.com/v1/realtime/sessions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                ) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        return web.json_response({"enabled": False, "error": data}, status=resp.status)
        except Exception as e:
            return web.json_response({"enabled": False, "error": str(e)}, status=500)

        # Return only what the browser needs
        client_secret = (data.get("client_secret") or {}).get("value")
        return web.json_response({
            "enabled": True,
            "model": model,
            "ephemeral_key": client_secret,
        })

    async def state_endpoint(self, request: web.Request) -> web.Response:
        return web.json_response(self.latest_state or {})

    def _setup_control_channel(self, dc) -> None:
        self.control_channels.append(dc)

        def send_actions_list() -> None:
            try:
                payload = {
                    "type": "actions",
                    "actions": sorted(SUPPORTED_ACTIONS),
                }
                dc.send(json.dumps(payload))
            except Exception:
                pass

        @dc.on("open")
        def on_open() -> None:
            logger.info("control channel open")
            send_actions_list()
            # Send a ping to mark connectivity
            try:
                dc.send(json.dumps({"type": "ping", "ts": time.time()}))
            except Exception:
                pass

        @dc.on("close")
        def on_close() -> None:
            logger.info("control channel close")
            if dc in self.control_channels:
                self.control_channels.remove(dc)

        @dc.on("message")
        def on_message(message: Any) -> None:
            try:
                if isinstance(message, (bytes, bytearray)):
                    return
                data = json.loads(message)
            except Exception:
                return

            t = data.get("type")
            if t == "move":
                # {type: "move", x: float, y: float, yaw: float}
                x = float(data.get("x", 0.0))
                y = float(data.get("y", 0.0))
                yaw = float(data.get("yaw", 0.0))
                try:
                    now_ts = time.time()
                    self._move_rx_count += 1
                    if self._move_rx_count <= 5 or (now_ts - self._move_last_log_ts) >= 0.5:
                        logger.info("Joystick move: x=%.3f y=%.3f yaw=%.3f", x, y, yaw)
                        self._move_last_log_ts = now_ts
                except Exception:
                    pass
                asyncio.create_task(self._handle_move(x, y, yaw))
                # Debug ACK
                try:
                    dc.send(json.dumps({"type": "ack_move", "x": x, "y": y, "yaw": yaw, "ts": time.time()}))
                except Exception:
                    pass
            elif t == "action":
                # {type: "action", name: "StandUp"}
                name = data.get("name")
                if isinstance(name, str):
                    logger.info(f"recv action: {name}")
                    asyncio.create_task(self._handle_action(name))
                    try:
                        dc.send(json.dumps({"type": "ack_action", "name": name, "ts": time.time()}))
                    except Exception:
                        pass
            elif t == "toggle_obstacle":
                logger.info("recv toggle_obstacle")
                asyncio.create_task(self._handle_toggle_obstacle())
            elif t == "joy_buttons":
                # {type: 'joy_buttons', left: [...], right: [...]}
                try:
                    ls = data.get("left")
                    rs = data.get("right")
                    # Summarize pressed buttons for concise logging
                    def pressed_idx(arr: Any) -> List[int]:
                        out: List[int] = []
                        if isinstance(arr, list):
                            for i, b in enumerate(arr):
                                try:
                                    if (isinstance(b, dict) and bool(b.get("pressed"))) or (hasattr(b, "get") and bool(b.get("pressed"))):
                                        out.append(i)
                                except Exception:
                                    pass
                        return out
                    lpi = pressed_idx(ls)
                    rpi = pressed_idx(rs)
                    logger.info("Joystick buttons: left pressed=%s right pressed=%s", lpi, rpi)
                except Exception:
                    pass

    def _setup_lidar_channel(self, dc) -> None:
        self.lidar_channels.append(dc)

        @dc.on("open")
        def on_open() -> None:
            logger.info("lidar channel open (%d clients)", len(self.lidar_channels))

        @dc.on("close")
        def on_close() -> None:
            logger.info("lidar channel close")
            if dc in self.lidar_channels:
                self.lidar_channels.remove(dc)

    # ---------------- Handlers for control -----------------
    async def _handle_move(self, x: float, y: float, yaw: float) -> None:
        now = time.time()
        if now - self.last_move_ts < self.move_interval_s:
            return
        self.last_move_ts = now

        if not self.robot:
            return

        # Choose obstacle-aware or sport move based on flag
        try:
            if self.obstacle_enabled:
                await self.robot.avoid_move(x, y, yaw, 0)
            else:
                if self.fast_move and getattr(self.robot, 'conn', None):
                    # Low-noise publish (avoids print spam from execute_command)
                    try:
                        req_id = int(asyncio.get_event_loop().time() * 1000) % 2147483648
                        api_id = MCF_CMD.get("Move") or SPORT_CMD["Move"]
                        payload = {
                            "header": {"identity": {"id": req_id, "api_id": api_id}},
                            "parameter": json.dumps({"x": x, "y": y, "z": yaw}),
                        }
                        self.robot.conn.datachannel.pub_sub.publish_without_callback(  # type: ignore
                            RTC_TOPIC["SPORT_MOD"], payload, DATA_CHANNEL_TYPE["REQUEST"]
                        )
                    except Exception:
                        await self.robot.sport_move(x, y, yaw)
                else:
                    await self.robot.sport_move(x, y, yaw)
        except Exception as e:
            logger.debug(f"move failed: {e}")

    async def _handle_action(self, name: str) -> None:
        if not self.robot:
            return
        canonical = {a.lower(): a for a in SUPPORTED_ACTIONS}.get(name.lower())
        if not canonical:
            return
        try:
            await self.robot.execute_command(canonical, wait_time=1.0)
        except Exception as e:
            logger.debug(f"action {name} failed: {e}")

    async def _handle_toggle_obstacle(self) -> None:
        if not self.robot:
            return
        try:
            enable = not self.obstacle_enabled
            ok = await self.robot.obstacle_detection("enable" if enable else "disable")
            if ok:
                self.obstacle_enabled = enable
                await self.robot.set_obstacle_remote_commands(enable)
        except Exception as e:
            logger.debug(f"toggle obstacle failed: {e}")


async def create_app(args: argparse.Namespace) -> web.Application:
    server = RobotVRServer(args)
    app = web.Application()

    # Static files
    static_path = os.path.join(os.path.dirname(__file__), "static")
    app.router.add_get("/", server.index)
    app.router.add_static("/static/", static_path, show_index=False)

    # WebRTC signaling
    app.router.add_post("/offer", server.offer)

    # Startup/shutdown robot connection
    async def on_startup(app: web.Application) -> None:
        await server.start_robot()

    async def on_cleanup(app: web.Application) -> None:
        # Cleanup all PCs
        for pc in list(server.pcs):
            try:
                await pc.close()
            except Exception:
                pass
        server.pcs.clear()
        await server.stop_robot()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    # Optional realtime + state endpoints
    app.router.add_get("/realtime-session", server.realtime_session)
    app.router.add_get("/state", server.state_endpoint)
    return app


def parse_args() -> argparse.Namespace:
    home = os.path.expanduser("~")
    default_cert = os.path.join(home, ".local", "server", "fullchain.pem")
    default_key = os.path.join(home, ".local", "server", "privkey.pem")
    p = argparse.ArgumentParser(description="WebXR server for Go2 VR control/streaming")
    p.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    p.add_argument("--port", type=int, default=8080, help="Port; if TLS is enabled, this is HTTPS port")
    p.add_argument("--certfile", type=str, default=default_cert, help="Path to TLS certificate (PEM). Defaults to ~/.local/server/fullchain.pem if present")
    p.add_argument("--keyfile", type=str, default=default_key, help="Path to TLS private key (PEM). Defaults to ~/.local/server/privkey.pem if present")
    p.add_argument("--redirect-http", type=int, default=None, help="Optional HTTP port to run 301 redirect → HTTPS")
    p.add_argument("--method", choices=["ap", "sta", "remote"], default="sta")
    p.add_argument("--serial", default=os.getenv("GO2_SN"))
    p.add_argument("--ip", default=os.getenv("ROBOT_IP"))
    p.add_argument("--username", default=os.getenv("UNITREE_USER"))
    p.add_argument("--password", default=os.getenv("UNITREE_PASS"))
    p.add_argument("--no-robot", action="store_true", help="Run server without connecting to robot (UI/dev mode)")
    # Replay options (for --no-robot)
    p.add_argument("--replay-lidar", type=str, default=None, help="Path to LiDAR .lidarlog file for replay")
    p.add_argument("--replay-video", type=str, default=None, help="Path to video file for replay (mp4/mkv)")
    p.add_argument("--replay-loop", action="store_true", help="Loop replayed content")
    p.add_argument("--replay-speed", type=float, default=1.0, help="Speed multiplier for LiDAR replay (e.g., 0.5, 1.0, 2.0)")
    return p.parse_args()


async def _run_servers(args: argparse.Namespace) -> None:
    app = await create_app(args)

    # Prepare main HTTPS/HTTP site
    ssl_ctx = None
    certfile = os.path.expanduser(args.certfile) if args.certfile else None
    keyfile = os.path.expanduser(args.keyfile) if args.keyfile else None
    if certfile and keyfile and os.path.exists(certfile) and os.path.exists(keyfile):
        try:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.load_cert_chain(certfile, keyfile)
            logging.info("TLS enabled on port %s using %s", args.port, certfile)
        except Exception as e:
            logging.error("Failed to load TLS cert/key (%s, %s): %s", certfile, keyfile, e)
            ssl_ctx = None
    if ssl_ctx is None:
        logging.warning(
            "TLS not enabled. Pico 4 WebXR typically requires HTTPS. "
            "Place certificates at ~/.local/server/fullchain.pem and ~/.local/server/privkey.pem or pass --certfile/--keyfile."
        )

    runner = web.AppRunner(app)
    await runner.setup()
    main_site = web.TCPSite(runner, host=args.host, port=args.port, ssl_context=ssl_ctx)
    await main_site.start()

    # Optional redirect HTTP → HTTPS
    if args.redirect_http:
        async def redir(request: web.Request) -> web.Response:
            # Build https URL using same host but HTTPS port
            host = request.host
            # Strip incoming port and replace with HTTPS port
            if ':' in host:
                host = host.split(':')[0]
            target_host = host if args.port == 443 else f"{host}:{args.port}"
            url = f"https://{target_host}{request.rel_url}"
            raise web.HTTPMovedPermanently(location=url)

        redirect_app = web.Application()
        redirect_app.router.add_route('*', '/{tail:.*}', redir)
        redir_runner = web.AppRunner(redirect_app)
        await redir_runner.setup()
        redir_site = web.TCPSite(redir_runner, host=args.host, port=args.redirect_http)
        await redir_site.start()
        logging.info("HTTP redirect enabled on port %s → https://<host>:%s", args.redirect_http, args.port)

    # Keep running
    await asyncio.Event().wait()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(_run_servers(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
