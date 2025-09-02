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
2) Start the server:
   - python apps/webxr/server.py --method sta  # or --method ap/remote and pass credentials
3) Open the headset browser to: http://YOUR_PC_IP:8080
4) Enter VR and enjoy. Use left stick for x/y and right stick X for yaw. Trigger to press virtual buttons.

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

Privacy & cost note: audio is streamed to OpenAI when voice is on. Keep it optional and switch it off when not needed.
