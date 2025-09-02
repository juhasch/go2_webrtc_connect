#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import os
import time
import ssl
from typing import Any, Dict, List, Optional

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRelay
from aiohttp import web, ClientSession

from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import WebRTCConnectionMethod
from go2_webrtc_driver.cli_go2action import SUPPORTED_ACTIONS


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webxr")


class RobotVRServer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.robot: Optional[Go2RobotHelper] = None
        self.robot_video_track: Optional[MediaStreamTrack] = None
        self.video_relay: Optional[MediaRelay] = None

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

        # Robot state cache (for assistant context)
        self.latest_state: Dict[str, Any] | None = None

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
        conn.datachannel.set_decoder(decoder_type="native")
        conn.datachannel.pub_sub.publish_without_callback("rt/utlidar/switch", "on")

        def lidar_subscriber(message: Dict[str, Any]):
            # Offload to event loop task (non-blocking)
            asyncio.create_task(self._handle_lidar_msg(message))

        conn.datachannel.pub_sub.subscribe(
            "rt/utlidar/voxel_map_compressed",
            lidar_subscriber,
        )

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
        finally:
            self.robot = None
            self.robot_video_track = None
            self.video_relay = None

    async def _handle_lidar_msg(self, message: Dict[str, Any]) -> None:
        now = time.time()
        if now - self.last_lidar_sent_ts < self.lidar_min_interval_s:
            return

        try:
            data = message.get("data", {}).get("data", {})
            # Unified decoder returns either list under "points" (native) or flat list under "positions" (libvoxel)
            points = data.get("points")
            if callable(points):
                points = points()
            if points is None:
                pos = data.get("positions", [])
                points = [pos[i : i + 3] for i in range(0, len(pos), 3)]

            # Downsample if needed
            if len(points) > self.lidar_max_points:
                step = max(1, len(points) // self.lidar_max_points)
                points = points[::step]

            # Pack as Float32Array binary
            import array

            flat: List[float] = []
            for p in points:
                # Safety: ensure 3 floats
                if isinstance(p, (list, tuple)) and len(p) >= 3:
                    flat.extend([float(p[0]), float(p[1]), float(p[2])])

            buf = array.array("f", flat).tobytes()

            # Broadcast on lidar channels
            for ch in list(self.lidar_channels):
                if ch.readyState == "open":
                    try:
                        ch.send(buf)
                    except Exception:
                        pass

            self.last_lidar_sent_ts = now
        except Exception as e:
            logger.debug(f"LiDAR processing error: {e}")

    # ---------------- Web (browser) side -----------------
    async def index(self, request: web.Request) -> web.Response:
        return web.FileResponse(path=os.path.join(os.path.dirname(__file__), "static", "index.html"))

    async def offer(self, request: web.Request) -> web.Response:
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection()
        self.pcs.append(pc)
        logger.info("Created PC %s", id(pc))

        # Create data channels from server-side
        control_dc = pc.createDataChannel("control")
        lidar_dc = pc.createDataChannel("lidar")

        self._setup_control_channel(control_dc)
        self._setup_lidar_channel(lidar_dc)

        # Add relayed robot video track if available
        if self.robot_video_track is not None and self.video_relay is not None:
            pc.addTrack(self.video_relay.subscribe(self.robot_video_track))
            setattr(pc, "_has_robot_video", True)

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
                asyncio.create_task(self._handle_move(x, y, yaw))
            elif t == "action":
                # {type: "action", name: "StandUp"}
                name = data.get("name")
                if isinstance(name, str):
                    asyncio.create_task(self._handle_action(name))
            elif t == "toggle_obstacle":
                asyncio.create_task(self._handle_toggle_obstacle())

    def _setup_lidar_channel(self, dc) -> None:
        self.lidar_channels.append(dc)

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
                # sport_move expects z=yaw
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
