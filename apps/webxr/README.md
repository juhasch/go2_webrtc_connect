WebXR VR Control & Streaming for Go2
====================================

This app serves a WebXR experience for the Pico 4 (or any WebXR-capable headset) to:
- Stream the robot’s camera to the headset (WebRTC video → Three.js texture).
- Stream LiDAR as a live point cloud (WebRTC data channel → Three.js Points).
- Control the robot with both VR controllers (left/right joysticks → Move).
- Trigger actions via virtual buttons using the controller trigger.

How it works
------------
- Python server (aiohttp + aiortc) connects to the Go2 via go2_webrtc_driver.
- Video from the robot is relayed to the browser over a WebRTC PeerConnection.
- LiDAR frames are decoded on the Python side and pushed via a data channel.
- VR controller inputs are sent back to the server via the same data channel to move the robot.

Run
---
1) Ensure dependencies: `aiortc` and `aiohttp` are required in addition to project deps.
   - pip install aiortc aiohttp
2) HTTPS is required for WebXR on Pico. Generate a certificate (recommended: mkcert):
   - mkcert -install
   - mkcert 192.168.1.42   # use your PC’s LAN IP you’ll open on the Pico
   This generates files like `192.168.1.42.pem` and `192.168.1.42-key.pem`.
   Alternatively with OpenSSL (single-IP SAN):
   - openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
       -keyout key.pem -out cert.pem -subj "/CN=192.168.1.42" \
       -addext "subjectAltName = IP:192.168.1.42"
3) Default cert location: the server automatically tries `~/.local/server/fullchain.pem` and `~/.local/server/privkey.pem`. If present, HTTPS is enabled automatically.
   - To override, pass `--certfile` and `--keyfile`.
4) Start the server over HTTPS and (optionally) an HTTP→HTTPS redirect:
   - python apps/webxr/server.py --method sta --ip <GO2_IP> --host 0.0.0.0 --port 8443 --redirect-http 8080
5) Open the headset browser to: https://192.168.1.42:8443 (accept the cert if prompted)
6) Enter VR and enjoy. Use left stick for x/y and right stick X for yaw. Trigger to press virtual buttons.

Notes
-----
- Actions are sourced from the `go2action` CLI supported set.
- Movement uses the same semantics as `apps/gamepad/gamepad_controller.py`.
- LiDAR is downsampled for performance. Tweak in server.py if needed.

Optional: Voice Assistant (OpenAI Realtime)
-------------------------------------------
You can talk to the dog and ask it to do things. The browser connects directly to OpenAI Realtime via WebRTC using an ephemeral token issued by the server.

- Set `OPENAI_API_KEY` in your environment on the server machine.
- Optional: set `OPENAI_REALTIME_MODEL` (default: `gpt-4o-realtime-preview`).
- Start the server as usual and click “Start Voice” in the top overlay.
- Speak naturally. The assistant replies with TTS audio and, when relevant, appends a final JSON command line that the client forwards to the robot (move/action/status).

Tool-calling mode
-----------------
The assistant is configured with real tools that it can call via the Realtime API:
- `robot_action(action, wait_s?)`: Execute any action supported by `go2action`.
- `robot_move(x, y, yaw)`: Move the robot with velocity inputs.
- `get_status()`: Fetch the current cached robot status.

When a tool-call is emitted, the browser executes it locally (sending control to the Python server) and returns the tool output back to the assistant, which then continues the conversation.

Privacy & cost note: audio is streamed to OpenAI when voice is on. Keep it optional and switch it off when not needed.

Troubleshooting HTTPS
---------------------
- If the Pico browser blocks the page, ensure you’re using HTTPS and the cert matches the IP you visit.
- With mkcert, you may need to accept the self-signed cert once in the Pico browser.
- If you prefer a public CA, run behind a reverse proxy (Caddy/NGINX) with a real certificate and proxy to the Python server.
