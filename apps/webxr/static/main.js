// Basic Three.js + WebXR scene with WebRTC hookup

let scene, camera, renderer;
let leftController, rightController;
let controlChannel = null;
let lidarChannel = null;
let lidarPoints = null;
let lidarGeometry = null;
let pointerRight = null;

let videoEl = null;
let videoMesh = null;

let actions = [];
let actionButtons = [];
const raycaster = new THREE.Raycaster();
const tempMatrix = new THREE.Matrix4();

// Movement throttle
let lastMoveSent = 0;
const moveIntervalMs = 50; // 20 Hz
const deadzone = 0.08;

function dz(v) { return Math.abs(v) < deadzone ? 0 : v; }

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

  // Clamp small noise; optionally scale if desired
  if (Math.abs(x) + Math.abs(y) + Math.abs(yaw) < 0.001) {
    // Still send occasionally to keep motion updated
  }

  controlChannel.send(JSON.stringify({ type: 'move', x, y, yaw }));
  lastMoveSent = now;
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
  renderer.render(scene, camera);
}

// ---------------- WebRTC client ----------------
async function connectWebRTC() {
  const pc = new RTCPeerConnection({
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
  });

  pc.ontrack = (ev) => {
    if (!videoEl) {
      videoEl = document.createElement('video');
      videoEl.autoplay = true;
      videoEl.muted = true;
      videoEl.playsInline = true;
    }
    videoEl.srcObject = ev.streams[0];
    // Create texture and assign to screen
    const tex = new THREE.VideoTexture(videoEl);
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.format = THREE.RGBFormat;
    videoMesh.material.map = tex;
    videoMesh.material.needsUpdate = true;
  };

  pc.ondatachannel = (ev) => {
    const ch = ev.channel;
    if (ch.label === 'control') {
      controlChannel = ch;
      ch.onmessage = (mev) => {
        try {
          const msg = JSON.parse(mev.data);
          if (msg.type === 'actions') {
            actions = msg.actions || [];
            layoutActionButtons();
          }
        } catch (e) {}
      };
    } else if (ch.label === 'lidar') {
      lidarChannel = ch;
      ch.binaryType = 'arraybuffer';
      ch.onmessage = (mev) => {
        updateLidarPoints(mev.data);
      };
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

  // Configure session with instructions and format
  const actionList = actions && actions.length ? actions.join(', ') : 'StandUp, StandDown, Hello, Sit, RecoveryStand';
  const systemPrompt = `You are a helpful robotic dog assistant for a Unitree Go2 in VR.\n` +
    `Keep responses short (1-2 sentences).\n` +
    `If the user requests an action/movement, append on a final single line a JSON object: ` +
    `{"intent":"robot_action"|"robot_move"|"status", "action":"<one of: ${actionList}>"?, "move":{"x":number,"y":number,"yaw":number}?}. ` +
    `Only include that one JSON object on the last line after your normal response.`;

  sendOAI({ type: 'session.update', session: { instructions: systemPrompt } });
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
