// Basic Three.js + WebXR scene with WebRTC hookup (ESM)
import * as THREE from 'https://unpkg.com/three@0.160.0/build/three.module.js';
import { VRButton } from 'https://unpkg.com/three@0.160.0/examples/jsm/webxr/VRButton.js';

let scene, camera, renderer;
let leftController, rightController;
let controlChannel = null;
let lidarChannel = null;
let lidarPoints = null;
let lidarGeometry = null;
let pointerRight = null;

let videoEl = null;
let videoMesh = null;
let videoTexture = null;
let previewEl = null;

let actions = [];
let actionButtons = [];
const raycaster = new THREE.Raycaster();
const tempMatrix = new THREE.Matrix4();

// Movement throttle
let lastMoveSent = 0;
const moveIntervalMs = 80; // ~12.5 Hz to reduce spam
const deadzone = 0.08;

function dz(v) { return Math.abs(v) < deadzone ? 0 : v; }

// Debug UI helpers
let debugEl = null;
const debugState = {
  controlDC: 'closed',
  lidarDC: 'closed',
  video: 'idle',
  videoDims: '',
  lidarPoints: 0,
  leftAxes: [],
  rightAxes: [],
  move: { x: 0, y: 0, yaw: 0 },
};

function initDebug() {
  debugEl = document.getElementById('debug');
  updateDebug();
}

function updateDebug() {
  if (!debugEl) return;
  const lines = [];
  lines.push(`DC control: ${debugState.controlDC} | DC lidar: ${debugState.lidarDC}`);
  lines.push(`Video: ${debugState.video} ${debugState.videoDims}`);
  lines.push(`LiDAR points: ${debugState.lidarPoints}`);
  const la = dbgFmtAxes(debugState.leftAxes);
  const ra = dbgFmtAxes(debugState.rightAxes);
  lines.push(`Left axes:  ${la}`);
  lines.push(`Right axes: ${ra}`);
  const m = debugState.move;
  lines.push(`Move (x,y,yaw): ${m.x.toFixed(3)}, ${m.y.toFixed(3)}, ${m.yaw.toFixed(3)}`);
  lines.push(`VR Debug: ${debugState.vrdbg ? 'ON' : 'off'}`);
  debugEl.textContent = lines.join('\n');
}

function dbgFmtAxes(a) {
  if (!a || a.length === 0) return '[]';
  return '[' + a.map(v => (Math.abs(v) < 0.001 ? ' 0.000' : (v>0?'+':'') + v.toFixed(3))).join(', ') + ']';
}

async function setupThree() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);

  camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.01, 200);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.xr.enabled = true;
  document.body.appendChild(renderer.domElement);

  document.body.appendChild(VRButton.createButton(renderer));

  // Basic lighting
  const light = new THREE.HemisphereLight(0xffffff, 0x222233, 1.0);
  scene.add(light);

  // Floor grid for reference
  const grid = new THREE.GridHelper(20, 20, 0x444444, 0x222222);
  grid.position.y = -1;
  scene.add(grid);

  // Video screen placeholder (updated when stream arrives)
  const screenGeom = new THREE.PlaneGeometry(3.2, 1.8);
  const screenMat = new THREE.MeshBasicMaterial({ color: 0x111111, side: THREE.DoubleSide });
  videoMesh = new THREE.Mesh(screenGeom, screenMat);
  videoMesh.position.set(0, 1.2, -2.2);
  scene.add(videoMesh);

  // Controllers
  leftController = renderer.xr.getController(0);
  rightController = renderer.xr.getController(1);
  scene.add(leftController);
  scene.add(rightController);

  // Pointer ray for right controller
  const lineGeom = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(0, 0, -1)
  ]);
  const line = new THREE.Line(lineGeom, new THREE.LineBasicMaterial({ color: 0x00ffff }));
  line.name = 'pointer';
  line.scale.z = 5;
  rightController.add(line);
  pointerRight = line;

  rightController.addEventListener('selectstart', onSelectStart);

  window.addEventListener('resize', onWindowResize);

  renderer.setAnimationLoop(onXRFrame);

  // Wire voice assistant button
  const voiceBtn = document.getElementById('voiceBtn');
  if (voiceBtn) voiceBtn.addEventListener('click', toggleVoiceAssistant);

  initDebug();
  previewEl = document.getElementById('preview');
  const debugBtn = document.getElementById('debugBtn');
  if (debugBtn) debugBtn.addEventListener('click', toggleVRDebug);
}

function ensureVideoMaterial() {
  if (!videoTexture && videoEl) {
    videoTexture = new THREE.VideoTexture(videoEl);
    videoTexture.minFilter = THREE.LinearFilter;
    videoTexture.magFilter = THREE.LinearFilter;
  }
  if (!videoTexture) {
    return new THREE.MeshBasicMaterial({ color: 0x3333aa, side: THREE.DoubleSide });
  }
  return new THREE.MeshBasicMaterial({ map: videoTexture, side: THREE.DoubleSide });
}

function toggleVRDebug() {
  vrDebugEnabled = !vrDebugEnabled;
  debugState.vrdbg = vrDebugEnabled;
  if (vrDebugEnabled) {
    // HUD plane attached to camera
    if (!hudMesh) {
      const mat = ensureVideoMaterial();
      const geo = new THREE.PlaneGeometry(1.6, 0.9);
      hudMesh = new THREE.Mesh(geo, mat);
      hudMesh.name = 'vrdebug_hud';
      hudMesh.renderOrder = 999;
    }
    if (hudMesh.parent !== camera) {
      camera.add(hudMesh);
      hudMesh.position.set(0, 0, -1.6);
    }
    // World-fixed debug plane
    if (!fixedDebugMesh) {
      const mat2 = ensureVideoMaterial();
      const geo2 = new THREE.PlaneGeometry(2.4, 1.35);
      fixedDebugMesh = new THREE.Mesh(geo2, mat2);
      fixedDebugMesh.name = 'vrdebug_fixed';
      fixedDebugMesh.position.set(0, 1.4, -3.0);
      scene.add(fixedDebugMesh);
    }
    // Make LiDAR more visible
    try {
      if (lidarPoints && lidarPoints.material) {
        lidarPoints.material.size = 0.05;
        lidarPoints.material.needsUpdate = true;
      }
    } catch {}
  } else {
    try { if (hudMesh && hudMesh.parent) hudMesh.parent.remove(hudMesh); } catch {}
    try { if (fixedDebugMesh && fixedDebugMesh.parent) fixedDebugMesh.parent.remove(fixedDebugMesh); } catch {}
    fixedDebugMesh = null;
    try {
      if (lidarPoints && lidarPoints.material) {
        lidarPoints.material.size = 0.02;
        lidarPoints.material.needsUpdate = true;
      }
    } catch {}
  }
  updateDebug();
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

// Create a textured button mesh from text
function createTextButton(text, width = 0.5, height = 0.18) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const W = 512, H = 128;
  canvas.width = W; canvas.height = H;
  ctx.fillStyle = '#222';
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#0ff';
  ctx.font = '48px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, W/2, H/2);
  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: false });
  const geo = new THREE.PlaneGeometry(width, height);
  const mesh = new THREE.Mesh(geo, mat);
  mesh.userData.label = text;
  return mesh;
}

function layoutActionButtons() {
  // Clear previous
  for (const m of actionButtons) scene.remove(m);
  actionButtons = [];

  const cols = 4;
  const spacingX = 0.6;
  const spacingY = 0.25;
  const startX = -((cols - 1) * spacingX) / 2;
  let row = 0, col = 0;
  for (const a of actions) {
    const b = createTextButton(a);
    b.position.set(startX + col * spacingX, 0.5 + (-row) * spacingY, -1.5);
    scene.add(b);
    actionButtons.push(b);
    col += 1;
    if (col >= cols) { col = 0; row += 1; }
  }

  // Obstacle toggle button
  const ob = createTextButton('Obstacle ON/OFF');
  ob.position.set(0, -0.5 + (-row) * spacingY, -1.5);
  ob.userData.toggleObstacle = true;
  scene.add(ob);
  actionButtons.push(ob);
}

function onSelectStart() {
  if (!rightController) return;
  if (!controlChannel || controlChannel.readyState !== 'open') return;

  tempMatrix.identity().extractRotation(rightController.matrixWorld);
  raycaster.ray.origin.setFromMatrixPosition(rightController.matrixWorld);
  raycaster.ray.direction.set(0, 0, -1).applyMatrix4(tempMatrix);

  const intersects = raycaster.intersectObjects(actionButtons, false);
  if (intersects.length > 0) {
    const target = intersects[0].object;
    if (target.userData.toggleObstacle) {
      controlChannel.send(JSON.stringify({ type: 'toggle_obstacle' }));
      // quick visual feedback
      target.material.color = new THREE.Color(0x00aa00);
      setTimeout(() => target.material.color = new THREE.Color(0xffffff), 300);
      return;
    }
    const label = target.userData.label;
    console.log('[UI] action click', label);
    controlChannel.send(JSON.stringify({ type: 'action', name: label }));
    target.material.color = new THREE.Color(0x00aa00);
    setTimeout(() => target.material.color = new THREE.Color(0xffffff), 300);
  }
}

function controllerStickXY(controller) {
  try {
    const src = controller?.inputSource;
    const gp = src?.gamepad;
    if (!gp) return { x: 0, y: 0 };
    // Prefer axes[0], axes[1] for xr-standard; fallback to [2], [3]
    let ax = 0, ay = 0;
    if (gp.axes && gp.axes.length >= 2) {
      ax = gp.axes[0] ?? 0; ay = gp.axes[1] ?? 0;
    }
    if ((Math.abs(ax) + Math.abs(ay)) < 0.01 && gp.axes && gp.axes.length >= 4) {
      ax = gp.axes[2] ?? 0; ay = gp.axes[3] ?? 0;
    }
    // Update debug: show all raw axes
    if (controller === leftController) {
      debugState.leftAxes = gp.axes ? Array.from(gp.axes) : [];
    } else if (controller === rightController) {
      debugState.rightAxes = gp.axes ? Array.from(gp.axes) : [];
    }
    return { x: ax, y: ay };
  } catch (e) {
    return { x: 0, y: 0 };
  }
}

function sendMoveIfNeeded() {
  if (!controlChannel || controlChannel.readyState !== 'open') return;
  const now = performance.now();
  if (now - lastMoveSent < moveIntervalMs) return;

  // left stick → x/y; right stick X → yaw
  const ls = controllerStickXY(leftController);
  const rs = controllerStickXY(rightController);
  let x = dz(-ls.y); // forward when pushing up
  let y = dz(ls.x);
  let yaw = dz(rs.x);

  // Only send if significant change or a periodic keepalive
  const prev = sendMoveIfNeeded._prev || { x: 0, y: 0, yaw: 0 };
  const eps = 0.02;
  const changed = (Math.abs(x - prev.x) > eps) || (Math.abs(y - prev.y) > eps) || (Math.abs(yaw - prev.yaw) > eps);
  const mag = Math.abs(x) + Math.abs(y) + Math.abs(yaw);

  // Keepalive (even if unchanged) every ~1.2s
  const keepalive = (!sendMoveIfNeeded._lastKA || (now - sendMoveIfNeeded._lastKA) > 1200);

  // If we just crossed near-zero, send a zero once
  const wasMoving = (Math.abs(prev.x) + Math.abs(prev.y) + Math.abs(prev.yaw)) > 1e-3;
  const nowStopped = mag < 1e-3 && wasMoving;

  if (changed || keepalive || nowStopped) {
    controlChannel.send(JSON.stringify({ type: 'move', x, y, yaw }));
    lastMoveSent = now;
    sendMoveIfNeeded._prev = { x, y, yaw };
    if (keepalive) sendMoveIfNeeded._lastKA = now;
    debugState.move = { x, y, yaw };
    updateDebug();
  }
}

function ensureLidarScene() {
  if (lidarPoints) return;
  lidarGeometry = new THREE.BufferGeometry();
  const positions = new Float32Array(3); // will grow dynamically
  lidarGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({ color: 0x44ffaa, size: 0.02, sizeAttenuation: true });
  lidarPoints = new THREE.Points(lidarGeometry, material);
  lidarPoints.position.set(0, 0, -2.5);
  scene.add(lidarPoints);
}

function updateLidarPoints(buffer) {
  ensureLidarScene();
  const arr = new Float32Array(buffer);
  const count = Math.floor(arr.length / 3);
  if (!lidarGeometry) return;
  const oldAttr = lidarGeometry.getAttribute('position');
  if (!oldAttr || oldAttr.array.length < arr.length) {
    lidarGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(arr.length), 3));
  }
  const attr = lidarGeometry.getAttribute('position');
  attr.array.set(arr);
  attr.needsUpdate = true;
  lidarGeometry.setDrawRange(0, count);
  lidarGeometry.computeBoundingSphere();
}

function onXRFrame() {
  sendMoveIfNeeded();
  if (videoTexture) videoTexture.needsUpdate = true;
  try {
    // Keep the screen in front of user; useful for debugging visibility
    const pos = new THREE.Vector3();
    camera.getWorldPosition(pos);
    const dir = new THREE.Vector3();
    camera.getWorldDirection(dir);
    const target = pos.clone().add(dir.multiplyScalar(2.2));
    if (videoMesh) {
      videoMesh.position.copy(target);
      videoMesh.lookAt(pos);
    }
  } catch (e) {}
  renderer.render(scene, camera);
}

// ---------------- WebRTC client ----------------
async function connectWebRTC() {
  const pc = new RTCPeerConnection({
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
  });

  // Ensure the offer contains a video m-line we can answer with a recv track
  try { pc.addTransceiver('video', { direction: 'recvonly' }); } catch {}

  // Create data channels from the offerer side (browser)
  const ctrl = pc.createDataChannel('control');
  controlChannel = ctrl;
  ctrl.onopen = () => { console.log('[DC] control open (offerer)'); debugState.controlDC = 'open'; updateDebug(); };
  ctrl.onmessage = (mev) => {
    try {
      const msg = JSON.parse(mev.data);
      if (msg.type === 'actions') {
        actions = msg.actions || [];
        layoutActionButtons();
        updateRealtimeTools();
      } else if (msg.type === 'ping') {
        // round-trip sanity
      } else if (msg.type === 'ack_move') {
        console.log('[ACK] move', msg);
      } else if (msg.type === 'ack_action') {
        console.log('[ACK] action', msg);
      }
    } catch (e) {}
  };
  ctrl.onclose = () => { console.log('[DC] control close'); debugState.controlDC = 'closed'; updateDebug(); };

  const lidar = pc.createDataChannel('lidar');
  lidarChannel = lidar;
  lidar.binaryType = 'arraybuffer';
  lidar.onopen = () => { console.log('[DC] lidar open (offerer)'); debugState.lidarDC = 'open'; updateDebug(); };
  lidar.onmessage = (mev) => {
    updateLidarPoints(mev.data);
    try { debugState.lidarPoints = Math.floor(new Float32Array(mev.data).length / 3); } catch {};
    try { console.log('[LiDAR] recv', mev.data.byteLength, 'bytes, points=', debugState.lidarPoints); } catch {}
    updateDebug();
  };
  lidar.onclose = () => { console.log('[DC] lidar close'); debugState.lidarDC = 'closed'; updateDebug(); };

  pc.ontrack = (ev) => {
    console.log('[RTC] ontrack kind=', ev.track?.kind, 'streams=', ev.streams?.length);
    debugState.video = 'receiving'; updateDebug();
    if (!videoEl) {
      videoEl = document.createElement('video');
      videoEl.autoplay = true;
      videoEl.muted = true;
      videoEl.playsInline = true;
      videoEl.addEventListener('playing', () => { debugState.video = 'playing'; updateDebug(); });
      videoEl.addEventListener('loadedmetadata', () => { debugState.videoDims = `${videoEl.videoWidth}x${videoEl.videoHeight}`; updateDebug(); });
    }
    videoEl.srcObject = ev.streams[0];
    if (previewEl && !previewEl.srcObject) previewEl.srcObject = ev.streams[0];
    // Create texture and assign to screen
    videoTexture = new THREE.VideoTexture(videoEl);
    videoTexture.minFilter = THREE.LinearFilter;
    videoTexture.magFilter = THREE.LinearFilter;
    // tex.format no longer needed
    videoMesh.material.map = videoTexture;
    videoMesh.material.needsUpdate = true;
  };

  // Keep a fallback in case the answerer also creates channels
  pc.ondatachannel = (ev) => {
    const ch = ev.channel;
    console.log('[DC] ondatachannel', ch.label);
    if (ch.label === 'control' && !controlChannel) {
      controlChannel = ch;
    } else if (ch.label === 'lidar' && !lidarChannel) {
      lidarChannel = ch;
    }
  };

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const resp = await fetch('/offer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type })
  });
  const answer = await resp.json();
  await pc.setRemoteDescription(answer);
}

(async function main() {
  await setupThree();
  await connectWebRTC();
})();

// ================= Optional Voice Assistant (OpenAI Realtime) =================
let voicePC = null;
let voiceDC = null; // oai-events
let micStream = null;
let asstBox = null;
let asstBuf = '';
const pendingToolCalls = new Map();

function ensureAsstBox() {
  if (!asstBox) {
    asstBox = document.getElementById('asst');
  }
  return asstBox;
}

async function toggleVoiceAssistant() {
  if (voicePC) {
    stopVoiceAssistant();
    return;
  }
  try {
    await startVoiceAssistant();
    const btn = document.getElementById('voiceBtn');
    if (btn) btn.textContent = 'Stop Voice';
  } catch (e) {
    console.error(e);
    alert('Voice assistant failed to start: ' + e);
  }
}

function stopVoiceAssistant() {
  if (voicePC) try { voicePC.close(); } catch {}
  voicePC = null;
  voiceDC = null;
  if (micStream) {
    for (const t of micStream.getTracks()) t.stop();
    micStream = null;
  }
  const btn = document.getElementById('voiceBtn');
  if (btn) btn.textContent = 'Start Voice';
}

async function startVoiceAssistant() {
  // Fetch ephemeral key
  const r = await fetch('/realtime-session');
  const js = await r.json();
  if (!js.enabled || !js.ephemeral_key) throw new Error('Server has no OPENAI_API_KEY configured');
  const model = js.model || 'gpt-4o-realtime-preview';
  const ephemeralKey = js.ephemeral_key;

  // Setup peerconnection to OpenAI
  voicePC = new RTCPeerConnection({ iceServers: [] });

  // Create events channel
  voiceDC = voicePC.createDataChannel('oai-events');
  voiceDC.onmessage = onOAIEvent;

  voicePC.ontrack = (ev) => {
    // Play assistant TTS audio response
    const audioEl = new Audio();
    audioEl.autoplay = true;
    audioEl.srcObject = ev.streams[0];
    audioEl.play().catch(()=>{});
  };

  // Mic
  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  for (const t of micStream.getAudioTracks()) {
    voicePC.addTrack(t, micStream);
  }
  // Ensure we can receive TTS audio back
  try { voicePC.addTransceiver('audio', { direction: 'recvonly' }); } catch {}

  const offer = await voicePC.createOffer();
  await voicePC.setLocalDescription(offer);

  const sdpResp = await fetch('https://api.openai.com/v1/realtime?model=' + encodeURIComponent(model), {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + ephemeralKey,
      'Content-Type': 'application/sdp',
      'Accept': 'application/sdp'
    },
    body: voicePC.localDescription.sdp
  });
  if (!sdpResp.ok) throw new Error('OpenAI Realtime refused SDP');
  const answerSdp = await sdpResp.text();
  await voicePC.setRemoteDescription({ type: 'answer', sdp: answerSdp });

  // Configure session with instructions and tools
  const systemPrompt = `You are a concise, friendly VR dog assistant for a Unitree Go2.\n` +
    `Use the provided tools when the user asks to move or perform actions, or asks for status. ` +
    `Keep spoken responses brief (1–2 sentences).`;
  sendOAI({ type: 'session.update', session: { instructions: systemPrompt } });
  updateRealtimeTools();
  // Greeting
  sendOAI({ type: 'response.create', response: { instructions: 'Say hello. Listen to the user and follow the instructions.' } });
}

function sendOAI(obj) {
  try { voiceDC && voiceDC.readyState === 'open' && voiceDC.send(JSON.stringify(obj)); } catch {}
}

function onOAIEvent(ev) {
  const el = ensureAsstBox();
  try {
    const data = ev.data;
    // Realtime emits JSON events; sometimes chunked. Try line-by-line.
    const lines = typeof data === 'string' ? data.split('\n') : [data];
    for (const line of lines) {
      if (!line) continue;
      let msg;
      try { msg = JSON.parse(line); } catch { continue; }
      const t = msg.type;
      if (t === 'response.output_text.delta' && msg.delta) {
        asstBuf += msg.delta;
        if (el) el.textContent = asstBuf;
      } else if (t && t.startsWith('response.output_tool_call')) {
        handleToolEvent(msg);
      } else if (t === 'response.completed') {
        // Parse trailing single-line JSON command
        const cmd = extractTrailingJSON(asstBuf);
        if (cmd) handleAssistantCommand(cmd);
        asstBuf = '';
      }
    }
  } catch (e) {
    console.warn('oai event parse failed', e);
  }
}

function updateRealtimeTools() {
  if (!voiceDC || voiceDC.readyState !== 'open') return;
  const actionEnum = (actions && actions.length) ? actions : undefined;
  const tools = [
    {
      type: 'function',
      name: 'robot_action',
      description: 'Execute a Unitree Go2 action (e.g., StandUp, Hello).',
      parameters: {
        type: 'object',
        properties: {
          action: actionEnum ? { type: 'string', enum: actionEnum } : { type: 'string' },
          wait_s: { type: 'number', description: 'Seconds to wait after command' }
        },
        required: ['action'],
        additionalProperties: false
      }
    },
    {
      type: 'function',
      name: 'robot_move',
      description: 'Move the robot with velocity commands.',
      parameters: {
        type: 'object',
        properties: {
          x: { type: 'number', description: 'Forward/back velocity (-1..1)' },
          y: { type: 'number', description: 'Strafe velocity (-1..1)' },
          yaw: { type: 'number', description: 'Yaw rate (-1..1)' }
        },
        required: ['x', 'y', 'yaw'],
        additionalProperties: false
      }
    },
    {
      type: 'function',
      name: 'get_status',
      description: 'Return current robot status summary.',
      parameters: { type: 'object', properties: {}, additionalProperties: false }
    }
  ];
  sendOAI({ type: 'session.update', session: { tools, tool_choice: 'auto' } });
}

function handleToolEvent(msg) {
  const id = msg.id || msg.tool_call_id || (msg?.item?.id);
  if (!id) return;
  let tc = pendingToolCalls.get(id);
  if (!tc) { tc = { name: '', args: '' }; pendingToolCalls.set(id, tc); }
  const d = msg.delta || {};
  if (d.name) tc.name = d.name; if (msg.name) tc.name = msg.name;
  if (d.arguments) tc.args += d.arguments; if (msg.arguments) tc.args = msg.arguments;
  if (msg.type && msg.type.endsWith('completed')) {
    finalizeToolCall(id, tc);
  }
}

async function finalizeToolCall(id, tc) {
  let args = {};
  try { if (tc.args) args = JSON.parse(tc.args); } catch {}
  let output = '';
  try {
    output = await executeTool(tc.name, args);
  } catch (e) {
    output = JSON.stringify({ ok: false, error: String(e) });
  }
  sendOAI({ type: 'tool.output', tool_call_id: id, output: typeof output === 'string' ? output : JSON.stringify(output) });
  sendOAI({ type: 'response.create' });
  pendingToolCalls.delete(id);
}

async function executeTool(name, args) {
  if (!name) return JSON.stringify({ ok: false, error: 'missing tool name' });
  if (name === 'robot_action') {
    const action = String(args?.action || '');
    if (controlChannel && controlChannel.readyState === 'open' && action) {
      controlChannel.send(JSON.stringify({ type: 'action', name: action }));
      return JSON.stringify({ ok: true, action });
    }
    return JSON.stringify({ ok: false, error: 'control channel not ready or empty action' });
  }
  if (name === 'robot_move') {
    const x = Number(args?.x) || 0, y = Number(args?.y) || 0, yaw = Number(args?.yaw) || 0;
    if (controlChannel && controlChannel.readyState === 'open') {
      controlChannel.send(JSON.stringify({ type: 'move', x, y, yaw }));
      return JSON.stringify({ ok: true, move: { x, y, yaw } });
    }
    return JSON.stringify({ ok: false, error: 'control channel not ready' });
  }
  if (name === 'get_status') {
    try {
      const s = await fetch('/state').then(r => r.json());
      const text = summarizeState(s);
      return JSON.stringify({ ok: true, text, state: s });
    } catch (e) {
      return JSON.stringify({ ok: false, error: String(e) });
    }
  }
  return JSON.stringify({ ok: false, error: 'unknown tool ' + name });
}

function extractTrailingJSON(text) {
  // Find last {...} block in the text
  const m = text.match(/\{[^]*\}$/); // greedy to last
  if (!m) return null;
  try { return JSON.parse(m[0]); } catch { return null; }
}

function handleAssistantCommand(cmd) {
  if (!controlChannel || controlChannel.readyState !== 'open') return;
  try {
    if (cmd.intent === 'robot_action' && typeof cmd.action === 'string') {
      controlChannel.send(JSON.stringify({ type: 'action', name: cmd.action }));
    } else if (cmd.intent === 'robot_move' && cmd.move) {
      const { x=0, y=0, yaw=0 } = cmd.move || {};
      controlChannel.send(JSON.stringify({ type: 'move', x: Number(x)||0, y: Number(y)||0, yaw: Number(yaw)||0 }));
    } else if (cmd.intent === 'status') {
      fetch('/state').then(r=>r.json()).then(state => {
        const summary = summarizeState(state);
        const el = ensureAsstBox();
        if (el) el.textContent = summary;
      }).catch(()=>{});
    }
  } catch {}
}

function summarizeState(s) {
  try {
    const mode = s?.mode ?? 'unknown';
    const gait = s?.gait_type ?? 'n/a';
    const bh = s?.body_height ?? 0;
    const rpy = s?.imu_state?.rpy ?? [0,0,0];
    return `Mode ${mode}, gait ${gait}, height ${bh.toFixed?bh.toFixed(2):bh}m, roll/pitch/yaw ${rpy.map(v=>Number(v).toFixed(2)).join('/')}`;
  } catch { return 'Status unavailable'; }
}
