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
let lidarGroup = null;      // container for LiDAR transform (rotation/pos)
let lidarCubes = null;      // InstancedMesh for cube rendering
let lidarCubeSize = 0.03;
let _cubeDummy = null;      // reused Object3D for per-instance transforms

let videoEl = null;
let videoMesh = null;
let videoTexture = null;
let previewEl = null;
let videoHUDMesh = null;    // camera-attached video plane for VR
// In-VR debug HUD (canvas texture)
let debugCanvas = null;
let debugCtx = null;
let debugTexture = null;
let debugHUDMesh = null;
let hudGroup = null;        // follows XR camera each frame (in scene)
const _tmpPos = new THREE.Vector3();
const _tmpQuat = new THREE.Quaternion();
const _tmpDir = new THREE.Vector3();
function getActiveCamera() {
  try { if (renderer && renderer.xr && renderer.xr.isPresenting) return renderer.xr.getCamera(); } catch {}
  return camera;
}
// VR debug visuals
let vrDebugEnabled = false;
let hudMesh = null;        // camera-attached HUD plane
let fixedDebugMesh = null; // world-fixed debug plane
let moveArrow = null;      // shows x/y move vector
let yawArrow = null;       // shows yaw magnitude/direction

let actions = [];
let actionButtons = [];
let panelGroup = null;      // VR control panel group (child of hudGroup)
let panelBackground = null; // background plane for control panel
const raycaster = new THREE.Raycaster();
const tempMatrix = new THREE.Matrix4();

// Movement throttle
let lastMoveSent = 0;
const moveIntervalMs = 80; // ~12.5 Hz to reduce spam
const deadzone = 0.05;

// Joystick button state (for logging/demo)
let lastButtonsSentAt = 0;
let lastButtonsState = { left: [], right: [] };

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
  leftButtons: [],
  rightButtons: [],
  move: { x: 0, y: 0, yaw: 0 },
  pcRotate: false,
};

function initDebug() {
  debugEl = document.getElementById('debug');
  updateDebug();
}

function updateDebug() {
  const lines = [];
  lines.push(`DC control: ${debugState.controlDC} | DC lidar: ${debugState.lidarDC}`);
  lines.push(`Video: ${debugState.video} ${debugState.videoDims}`);
  lines.push(`LiDAR points: ${debugState.lidarPoints}`);
  const la = dbgFmtAxes(debugState.leftAxes);
  const ra = dbgFmtAxes(debugState.rightAxes);
  lines.push(`Left axes:  ${la}`);
  lines.push(`Right axes: ${ra}`);
  const lb = dbgFmtButtons(debugState.leftButtons);
  const rb = dbgFmtButtons(debugState.rightButtons);
  lines.push(`Left buttons:  ${lb}`);
  lines.push(`Right buttons: ${rb}`);
  const m = debugState.move;
  lines.push(`Move (x,y,yaw): ${m.x.toFixed(3)}, ${m.y.toFixed(3)}, ${m.yaw.toFixed(3)}`);
  lines.push(`VR Debug: ${debugState.vrdbg ? 'ON' : 'off'}`);
  lines.push(`PC Rotate: ${debugState.pcRotate ? 'ON' : 'off'} (toggle: B)`);
  if (debugEl) debugEl.textContent = lines.join('\n');

  // Mirror into VR HUD canvas
  if (debugCtx && debugTexture && debugCanvas) {
    const W = debugCanvas.width, H = debugCanvas.height;
    debugCtx.clearRect(0, 0, W, H);
    debugCtx.fillStyle = 'rgba(0,0,0,0.25)';
    debugCtx.fillRect(0, 0, W, H);
    debugCtx.fillStyle = '#00ff00';
    debugCtx.font = '22px monospace';
    debugCtx.textBaseline = 'top';
    const lh = 24;
    for (let i = 0; i < lines.length; i++) {
      debugCtx.fillText(lines[i], 10, 8 + i * lh);
    }
    debugTexture.needsUpdate = true;
  }
}

function dbgFmtAxes(a) {
  if (!a || a.length === 0) return '[]';
  return '[' + a.map(v => (Math.abs(v) < 0.001 ? ' 0.000' : (v>0?'+':'') + v.toFixed(3))).join(', ') + ']';
}

function dbgFmtButtons(arr) {
  try {
    if (!Array.isArray(arr) || arr.length === 0) return '[]';
    const pressed = [];
    const touched = [];
    const values = [];
    arr.forEach((b, i) => {
      if (!b) return;
      if (b.pressed) pressed.push(i);
      if (b.touched) touched.push(i);
      if (b.value && Math.abs(b.value) > 0.01) values.push(`${i}:${Number(b.value).toFixed(2)}`);
    });
    return `P=[${pressed.join(',')}] T=[${touched.join(',')}] V=[${values.join(',')}]`;
  } catch { return '[]'; }
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

  // Show/hide video HUD when entering/leaving XR
  try {
    renderer.xr.addEventListener('sessionstart', () => {
      if (videoMesh) videoMesh.visible = true; // keep world screen as fallback in VR
      if (videoTexture) ensureVideoHUD();
      if (videoHUDMesh) videoHUDMesh.visible = (debugState.video === 'playing');
      ensureHudGroup();
      ensureDebugHUD();
      if (hudGroup) hudGroup.visible = true;
      if (debugHUDMesh) debugHUDMesh.visible = true;
    });
    renderer.xr.addEventListener('sessionend', () => {
      if (videoMesh) videoMesh.visible = true;
      if (videoHUDMesh) videoHUDMesh.visible = false;
      if (debugHUDMesh) debugHUDMesh.visible = false;
      if (hudGroup) hudGroup.visible = true; // keep visible in non-VR
    });
  } catch {}

  // Basic lighting
  const light = new THREE.HemisphereLight(0xffffff, 0x222233, 1.0);
  scene.add(light);

  // Floor grid for reference
  const grid = new THREE.GridHelper(20, 20, 0x444444, 0x222222);
  grid.position.y = -1;
  scene.add(grid);

  // Video screen placeholder (updated when stream arrives)
  const screenGeom = new THREE.PlaneGeometry(3.2, 1.8);
  const screenMat = new THREE.MeshBasicMaterial({ color: 0x111111, side: THREE.DoubleSide, transparent: true, opacity: 0.6 });
  videoMesh = new THREE.Mesh(screenGeom, screenMat);
  videoMesh.position.set(0, 1.2, -2.2);
  videoMesh.renderOrder = 1;
  videoMesh.material.depthWrite = false;
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
  window.addEventListener('keydown', onKeyDown);

  renderer.setAnimationLoop(onXRFrame);

  // Wire voice assistant button
  const voiceBtn = document.getElementById('voiceBtn');
  if (voiceBtn) voiceBtn.addEventListener('click', toggleVoiceAssistant);

  initDebug();
  previewEl = document.getElementById('preview');
  const debugBtn = document.getElementById('debugBtn');
  if (debugBtn) debugBtn.addEventListener('click', toggleVRDebug);
  // Prepare VR debug HUD once
  ensureDebugHUD();
  // Prepare control panel and lay out default actions
  ensureHudGroup();
  ensureControlPanelGroup();
  if (actions && actions.length) layoutActionButtons();
}

// Keyboard controls
let pcRotateMode = false;
let pcYaw = 0;    // radians
let pcPitch = 0;  // radians
const PC_PITCH_MIN = -1.3, PC_PITCH_MAX = 1.3;
const PC_ROT_SPEED = 2.2; // rad/sec per full deflection
let RIGHT_B_INDEX = 5; // default button for rotate toggle; override via ?rb=idx
let _prevRightB = false;
let RIGHT_PANEL_INDEX = 4; // default button index for panel toggle; override via ?rp=idx
let _prevRightPanel = false;

function onKeyDown(e) {
  const k = (e.key || '').toLowerCase();
  if (k === 'b') {
    pcRotateMode = !pcRotateMode;
    debugState.pcRotate = pcRotateMode;
    updateDebug();
  }
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

function ensureVideoHUD() {
  if (!videoTexture) return null;
  ensureHudGroup();
  if (!videoHUDMesh) {
    // Dedicated HUD material bound to the live VideoTexture
    const mat = new THREE.MeshBasicMaterial({ map: videoTexture, side: THREE.DoubleSide, color: 0xffffff });
    mat.depthWrite = false;
    mat.depthTest = false;
    const geo = new THREE.PlaneGeometry(1.6, 0.9);
    videoHUDMesh = new THREE.Mesh(geo, mat);
    videoHUDMesh.name = 'videoHUD';
    videoHUDMesh.renderOrder = 9999;
  }
  if (videoHUDMesh.parent !== hudGroup) {
    try { if (videoHUDMesh.parent) videoHUDMesh.parent.remove(videoHUDMesh); } catch {}
    hudGroup.add(videoHUDMesh);
    videoHUDMesh.position.set(0, 0.12, 0);
    videoHUDMesh.rotation.set(0, 0, 0);
    videoHUDMesh.visible = true;
  }
  return videoHUDMesh;
}

function ensureDebugHUD() {
  if (!debugCanvas) {
    debugCanvas = document.createElement('canvas');
    debugCanvas.width = 1024; // crisp text
    debugCanvas.height = 512;
    debugCtx = debugCanvas.getContext('2d');
    debugTexture = new THREE.CanvasTexture(debugCanvas);
  }
  if (!debugHUDMesh) {
    const mat = new THREE.MeshBasicMaterial({ map: debugTexture, transparent: true, color: 0xffffff });
    mat.depthWrite = false;
    mat.depthTest = false;
    const geo = new THREE.PlaneGeometry(1.2, 0.6);
    debugHUDMesh = new THREE.Mesh(geo, mat);
    debugHUDMesh.name = 'debugHUD';
    debugHUDMesh.renderOrder = 9999;
  }
  ensureHudGroup();
  if (debugHUDMesh.parent !== hudGroup) {
    try { if (debugHUDMesh.parent) debugHUDMesh.parent.remove(debugHUDMesh); } catch {}
    hudGroup.add(debugHUDMesh);
    debugHUDMesh.position.set(0.0, -0.25, 0);
    debugHUDMesh.rotation.set(0, 0, 0);
    debugHUDMesh.visible = true;
  }
  // Initial draw
  updateDebug();
  return debugHUDMesh;
}

function ensureHudGroup() {
  const cam = getActiveCamera();
  if (!hudGroup) {
    hudGroup = new THREE.Group();
    hudGroup.name = 'hudGroup';
    hudGroup.renderOrder = 9999;
    scene.add(hudGroup);
  }
  // Copy XR camera pose each frame in onXRFrame; here just ensure exists
  return hudGroup;
}

function toggleVRDebug() {
  vrDebugEnabled = !vrDebugEnabled;
  debugState.vrdbg = vrDebugEnabled;
  try { const btn = document.getElementById('debugBtn'); if (btn) btn.textContent = vrDebugEnabled ? 'VR Debug ON' : 'VR Debug'; } catch {}
  if (vrDebugEnabled) {
    // HUD plane attached to camera
    // Repurpose: when VR Debug ON, ensure in-headset debug HUD visible
    ensureDebugHUD();
    if (debugHUDMesh) debugHUDMesh.visible = true;
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
    // Joystick debug arrows attached to camera
    if (!moveArrow) {
      moveArrow = new THREE.ArrowHelper(new THREE.Vector3(0,0,-1), new THREE.Vector3(0, -0.1, -1.0), 0.01, 0x00ff66, 0.18, 0.09);
      moveArrow.name = 'vrdbg_move';
    }
    if (moveArrow.parent !== camera) camera.add(moveArrow);
    if (!yawArrow) {
      yawArrow = new THREE.ArrowHelper(new THREE.Vector3(1,0,0), new THREE.Vector3(0, -0.4, -1.0), 0.01, 0xff5500, 0.18, 0.09);
      yawArrow.name = 'vrdbg_yaw';
    }
    if (yawArrow.parent !== camera) camera.add(yawArrow);
  } else {
    try { if (hudMesh && hudMesh.parent) hudMesh.parent.remove(hudMesh); } catch {}
    try { if (fixedDebugMesh && fixedDebugMesh.parent) fixedDebugMesh.parent.remove(fixedDebugMesh); } catch {}
    fixedDebugMesh = null;
    try { if (debugHUDMesh) debugHUDMesh.visible = false; } catch {}
    try {
      if (lidarPoints && lidarPoints.material) {
        lidarPoints.material.size = 0.02;
        lidarPoints.material.needsUpdate = true;
      }
    } catch {}
    try { if (moveArrow && moveArrow.parent) moveArrow.parent.remove(moveArrow); } catch {}
    try { if (yawArrow && yawArrow.parent) yawArrow.parent.remove(yawArrow); } catch {}
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
  ensureControlPanelGroup();
  // Remove previous buttons
  for (const m of actionButtons) { try { panelGroup.remove(m); } catch {} }
  actionButtons = [];
  // Remove and recreate background
  try { if (panelBackground) panelGroup.remove(panelBackground); } catch {}
  panelBackground = null;

  const cols = 4;
  const btnW = 0.5, btnH = 0.18;
  const spacingX = 0.56;
  const spacingY = 0.22;
  const startX = -((cols - 1) * spacingX) / 2;
  let row = 0, col = 0;
  for (const a of actions) {
    const b = createTextButton(a, btnW, btnH);
    b.position.set(startX + col * spacingX, 0.1 + (-row) * spacingY, 0);
    panelGroup.add(b);
    actionButtons.push(b);
    col += 1;
    if (col >= cols) { col = 0; row += 1; }
  }
  // Obstacle toggle button at bottom
  const ob = createTextButton('Obstacle ON/OFF', btnW, btnH);
  ob.position.set(0, 0.1 + (-row) * spacingY, 0);
  ob.userData.toggleObstacle = true;
  panelGroup.add(ob);
  actionButtons.push(ob);

  // Background plane sized to content
  const rows = row + (col > 0 ? 1 : 0) + 1; // include toggle row
  const bgW = cols * spacingX + 0.35;
  const bgH = rows * spacingY + 0.32;
  const bgGeo = new THREE.PlaneGeometry(bgW, bgH);
  const bgMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.25, depthWrite: false, depthTest: false, side: THREE.DoubleSide });
  panelBackground = new THREE.Mesh(bgGeo, bgMat);
  panelBackground.position.set(0, (0.1 - (rows - 1) * spacingY) / 2, -0.001);
  panelBackground.renderOrder = 9998;
  panelGroup.add(panelBackground);
}

function ensureControlPanelGroup() {
  ensureHudGroup();
  if (!panelGroup) {
    panelGroup = new THREE.Group();
    panelGroup.name = 'controlPanel';
    panelGroup.renderOrder = 9999;
    hudGroup.add(panelGroup);
    panelGroup.position.set(0, -0.02, 0);
    panelGroup.scale.set(0.7, 0.7, 1.0); // shrink panel to fit FOV
    panelGroup.visible = false; // hidden by default
  }
  return panelGroup;
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
    // highlight the triggered action more visibly
    try {
      const original = target.material.color.clone();
      target.material.color = new THREE.Color(0xffaa00);
      target.scale.set(1.05 * target.scale.x, 1.05 * target.scale.y, 1.0);
      setTimeout(() => {
        target.material.color = original;
        target.scale.set(1.0, 1.0, 1.0);
      }, 450);
    } catch {}
  }
}

function getGamepadForHand(hand) {
  try {
    const s = renderer?.xr?.getSession?.();
    if (!s || !s.inputSources) return null;
    for (const src of s.inputSources) {
      if (src && src.handedness === hand && src.gamepad) return src.gamepad;
    }
  } catch {}
  return null;
}

function getHandAxes(hand, fallbackController) {
  try {
    const gp = getGamepadForHand(hand) || (fallbackController?.inputSource?.gamepad || null);
    if (!gp || !gp.axes) return [];
    const axes = Array.from(gp.axes);
    if (hand === 'left') debugState.leftAxes = axes;
    if (hand === 'right') debugState.rightAxes = axes;
    return axes;
  } catch { return []; }
}

function getStickXYForRotation(hand, fallbackController) {
  const a = getHandAxes(hand, fallbackController);
  // Prefer [2,3] if available (often right stick in XR), else [0,1]
  let ax = 0, ay = 0;
  if (a.length >= 4) { ax = Number(a[2] || 0); ay = Number(a[3] || 0); }
  else { ax = Number(a[0] || 0); ay = Number(a[1] || 0); }
  return { x: dz(ax), y: dz(ay) };
}

function isRightButtonPressed(idx) {
  try {
    const gp = getGamepadForHand('right') || (rightController?.inputSource?.gamepad || null);
    if (!gp || !gp.buttons || idx < 0 || idx >= gp.buttons.length) return false;
    const b = gp.buttons[idx];
    return !!(b && (b.pressed || (b.value && b.value > 0.5)));
  } catch { return false; }
}

function sendMoveIfNeeded() {
  if (!controlChannel || controlChannel.readyState !== 'open') return;
  if (pcRotateMode) return; // don't move robot while rotating point cloud
  const now = performance.now();
  if (now - lastMoveSent < moveIntervalMs) return;

  // left stick → x/y; right stick X/2 → yaw
  const la = getHandAxes('left', leftController);
  const ra = getHandAxes('right', rightController);
  // Extract best XY from each hand
  const pickXY = (axes) => {
    const a0 = Number(axes[0] || 0), a1 = Number(axes[1] || 0);
    const a2 = Number(axes[2] || 0), a3 = Number(axes[3] || 0);
    const m01 = Math.abs(a0) + Math.abs(a1);
    const m23 = Math.abs(a2) + Math.abs(a3);
    return (m23 > m01 + 0.02) ? { x: a2, y: a3, src: '23' } : { x: a0, y: a1, src: '01' };
  };
  const lxy = pickXY(la);
  const rxy = pickXY(ra);
  const lm = Math.abs(lxy.x) + Math.abs(lxy.y);
  const rm = Math.abs(rxy.x) + Math.abs(rxy.y);
  const useRightForXY = rm > lm + 0.02;
  const xy = useRightForXY ? rxy : lxy;
  let x = dz(-xy.y); // forward when pushing up
  let y = dz(xy.x);
  debugState.xyFrom = useRightForXY ? 'right' : 'left';
  // Yaw: prefer right stick axis[2] if available, else right[0], else fallback to left
  const yawFromAxes = (axes) => dz(typeof axes[2] === 'number' && Math.abs(axes[2]) > 0.01 ? Number(axes[2]) : Number(axes[0] || 0));
  let yaw = dz(0);
  let yawFrom = 'right';
  const ry = yawFromAxes(ra);
  if (Math.abs(ry) > 0.01) { yaw = ry; yawFrom = 'right'; }
  else { yaw = yawFromAxes(la); yawFrom = 'left'; }
  debugState.yawFrom = yawFrom;

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

function readButtonsForHand(hand, fallbackController) {
  try {
    const gp = getGamepadForHand(hand) || (fallbackController?.inputSource?.gamepad || null);
    if (!gp || !gp.buttons) return [];
    return gp.buttons.map(b => ({ pressed: !!b.pressed, touched: !!b.touched, value: Number(b.value || 0) }));
  } catch { return []; }
}

function sendButtonsIfNeeded() {
  if (!controlChannel || controlChannel.readyState !== 'open') return;
  const now = performance.now();
  if (now - lastButtonsSentAt < 150) return; // ~6-7 Hz
  const lb = readButtonsForHand('left', leftController);
  const rb = readButtonsForHand('right', rightController);
  debugState.leftButtons = lb;
  debugState.rightButtons = rb;
  const changed = JSON.stringify(lb) !== JSON.stringify(lastButtonsState.left) || JSON.stringify(rb) !== JSON.stringify(lastButtonsState.right);
  if (changed) {
    try {
      controlChannel.send(JSON.stringify({ type: 'joy_buttons', left: lb, right: rb }));
    } catch {}
    lastButtonsState = { left: lb, right: rb };
    lastButtonsSentAt = now;
    updateDebug();
  }
}

function ensureLidarScene() {
  if (!lidarGroup) {
    lidarGroup = new THREE.Group();
    lidarGroup.position.set(0, 0, -2.0);
    scene.add(lidarGroup);
  }
  // Initialize points geometry lazily only if we need it; cubes will be default
  if (!lidarPoints) {
    lidarGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(3); // will grow dynamically
    lidarGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const colors = new Float32Array(3);
    lidarGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const material = new THREE.PointsMaterial({ size: 0.03, sizeAttenuation: true, vertexColors: true });
    lidarPoints = new THREE.Points(lidarGeometry, material);
    lidarPoints.renderOrder = 2;
    lidarPoints.visible = false; // default hidden when using cubes
    lidarGroup.add(lidarPoints);
  }
}

function updateLidarPoints(buffer) {
  ensureLidarScene();
  const arr = new Float32Array(buffer);
  const count = Math.floor(arr.length / 3);
  if (count <= 0) return;
  if (!lidarGeometry) return;
  const oldAttr = lidarGeometry.getAttribute('position');
  if (!oldAttr || oldAttr.array.length < arr.length) {
    lidarGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(arr.length), 3));
    lidarGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  } else {
    const oldColor = lidarGeometry.getAttribute('color');
    if (!oldColor || oldColor.array.length < count * 3) {
      lidarGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    }
  }
  // Center and scale to fit ~1.5m box for visibility
  let sx = 0, sy = 0, sz = 0;
  for (let i = 0; i < count; i++) {
    sx += arr[3*i + 0];
    sy += arr[3*i + 1];
    sz += arr[3*i + 2];
  }
  const mx = sx / Math.max(1, count);
  const my = sy / Math.max(1, count);
  const mz = sz / Math.max(1, count);
  let maxAbs = 1e-6;
  const dst = lidarGeometry.getAttribute('position').array;
  for (let i = 0; i < count; i++) {
    const x = arr[3*i + 0] - mx;
    const y = arr[3*i + 1] - my;
    const z = arr[3*i + 2] - mz;
    const ax = Math.abs(x), ay = Math.abs(y), az = Math.abs(z);
    if (ax > maxAbs) maxAbs = ax;
    if (ay > maxAbs) maxAbs = ay;
    if (az > maxAbs) maxAbs = az;
    dst[3*i + 0] = x;
    dst[3*i + 1] = y;
    dst[3*i + 2] = z;
  }
  // Scale so the largest axis fits ~1.5 meters
  const scale = 1.5 / maxAbs;
  if (scale > 0 && scale !== 1) {
    for (let i = 0; i < count*3; i++) dst[i] *= scale;
  }
  // Compute per-vertex colors based on height (z), rainbow HSV hue from blue->red
  const colorAttr = lidarGeometry.getAttribute('color');
  const cArr = colorAttr.array;
  let zMin = Infinity, zMax = -Infinity;
  for (let i = 0; i < count; i++) {
    const z = dst[3*i + 2];
    if (z < zMin) zMin = z;
    if (z > zMax) zMax = z;
  }
  const denom = (zMax - zMin) > 1e-6 ? (zMax - zMin) : 1e-6;
  for (let i = 0; i < count; i++) {
    const z = dst[3*i + 2];
    const norm = (z - zMin) / denom; // 0..1
    const hue = (2.0 / 3.0) * (1.0 - norm); // 2/3..0 blue->red
    const hh = hue * 6.0;
    const c = 1.0;
    const x = c * (1.0 - Math.abs((hh % 2.0) - 1.0));
    const sext = Math.floor(hh) % 6;
    let r = 0, g = 0, b = 0;
    if (sext === 0) { r = c; g = x; b = 0; }
    else if (sext === 1) { r = x; g = c; b = 0; }
    else if (sext === 2) { r = 0; g = c; b = x; }
    else if (sext === 3) { r = 0; g = x; b = c; }
    else if (sext === 4) { r = x; g = 0; b = c; }
    else /* 5 */ { r = c; g = 0; b = x; }
    cArr[3*i + 0] = r;
    cArr[3*i + 1] = g;
    cArr[3*i + 2] = b;
  }
  const attr = lidarGeometry.getAttribute('position');
  attr.needsUpdate = true;
  colorAttr.needsUpdate = true;
  lidarGeometry.setDrawRange(0, count);
  lidarGeometry.computeBoundingSphere();

  // --- Render as cubes using InstancedMesh ---
  if (!_cubeDummy) _cubeDummy = new THREE.Object3D();
  const needCreate = !lidarCubes || (lidarCubes.userData.capacity || 0) < count;
  if (needCreate) {
    try { if (lidarCubes && lidarCubes.parent) lidarCubes.parent.remove(lidarCubes); } catch {}
    const cap = count;
    const boxGeo = new THREE.BoxGeometry(lidarCubeSize, lidarCubeSize, lidarCubeSize);
    const boxMat = new THREE.MeshBasicMaterial({ vertexColors: true });
    boxMat.depthTest = true;
    boxMat.depthWrite = true;
    lidarCubes = new THREE.InstancedMesh(boxGeo, boxMat, cap);
    lidarCubes.userData.capacity = cap;
    lidarCubes.count = count;
    lidarCubes.renderOrder = 3;
    lidarGroup.add(lidarCubes);
    // Hide points since we're using cubes
    if (lidarPoints) lidarPoints.visible = false;
  } else {
    lidarCubes.count = count;
  }
  // Ensure instanceColor attribute exists and sized
  if (!lidarCubes.instanceColor || (lidarCubes.instanceColor.count || 0) < count) {
    try {
      lidarCubes.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(count * 3), 3);
    } catch {}
  }
  const icArr = lidarCubes.instanceColor ? lidarCubes.instanceColor.array : null;
  for (let i = 0; i < count; i++) {
    const px = dst[3*i + 0];
    const py = dst[3*i + 1];
    const pz = dst[3*i + 2];
    _cubeDummy.position.set(px, py, pz);
    _cubeDummy.rotation.set(0, 0, 0);
    _cubeDummy.updateMatrix();
    lidarCubes.setMatrixAt(i, _cubeDummy.matrix);
    if (icArr) {
      icArr[3*i + 0] = cArr[3*i + 0] || 1;
      icArr[3*i + 1] = cArr[3*i + 1] || 1;
      icArr[3*i + 2] = cArr[3*i + 2] || 1;
    }
  }
  lidarCubes.instanceMatrix.needsUpdate = true;
  if (lidarCubes.instanceColor) lidarCubes.instanceColor.needsUpdate = true;
}

let _lastXRTime = 0;
function onXRFrame(time) {
  const t = typeof time === 'number' ? time : performance.now();
  const dt = Math.max(0, Math.min(0.05, (t - (_lastXRTime || t)) / 1000));
  _lastXRTime = t;

  if (pcRotateMode && lidarGroup) {
    // Use right stick to rotate point cloud (yaw/pitch)
    const rs = getStickXYForRotation('right', rightController);
    pcYaw += rs.x * PC_ROT_SPEED * dt;
    pcPitch += -rs.y * PC_ROT_SPEED * dt;
    if (pcPitch < PC_PITCH_MIN) pcPitch = PC_PITCH_MIN;
    if (pcPitch > PC_PITCH_MAX) pcPitch = PC_PITCH_MAX;
    lidarGroup.rotation.set(pcPitch, pcYaw, 0);
  } else {
    sendMoveIfNeeded();
  }

  // Toggle rotate mode on B button (rising edge)
  const rbPressed = isRightButtonPressed(RIGHT_B_INDEX);
  if (rbPressed && !_prevRightB) {
    pcRotateMode = !pcRotateMode;
    debugState.pcRotate = pcRotateMode;
    updateDebug();
  }
  _prevRightB = rbPressed;

  // Toggle control panel on A button (right controller) rising edge
  const rpPressed = isRightButtonPressed(RIGHT_PANEL_INDEX);
  if (rpPressed && !_prevRightPanel) {
    try { ensureControlPanelGroup(); panelGroup.visible = !panelGroup.visible; } catch {}
  }
  _prevRightPanel = rpPressed;

  sendButtonsIfNeeded();
  if (videoTexture) videoTexture.needsUpdate = true;
  // Keep HUD group aligned with active XR camera
  try {
    if (renderer?.xr?.isPresenting) {
      const cam = getActiveCamera();
      ensureHudGroup();
      // Position hudGroup slightly in front of camera
      cam.getWorldPosition(_tmpPos);
      cam.getWorldQuaternion(_tmpQuat);
      _tmpDir.set(0, 0, -1).applyQuaternion(_tmpQuat);
      hudGroup.position.copy(_tmpPos).addScaledVector(_tmpDir, 1.0);
      hudGroup.quaternion.copy(_tmpQuat);
      // Auto-toggle video HUD visibility based on playback
      try {
        const playing = !!(videoEl && !videoEl.paused && !videoEl.ended && videoEl.readyState >= 2);
        if (videoHUDMesh) videoHUDMesh.visible = playing;
      } catch {}
    }
  } catch {}
  // Update joystick debug arrows when VR Debug is ON
  if (vrDebugEnabled) {
    const m = debugState.move || { x: 0, y: 0, yaw: 0 };
    if (moveArrow) {
      const v = new THREE.Vector3(m.y, 0, -m.x);
      const len = Math.min(0.8, Math.sqrt(m.x * m.x + m.y * m.y) * 0.8);
      if (len > 0.01) {
        moveArrow.setDirection(v.normalize());
        moveArrow.setLength(len, 0.18, 0.09);
        moveArrow.visible = true;
      } else {
        moveArrow.visible = false;
      }
    }
    if (yawArrow) {
      const len = Math.min(0.6, Math.abs(m.yaw) * 0.6);
      if (len > 0.01) {
        const sign = m.yaw >= 0 ? 1 : -1;
        yawArrow.setDirection(new THREE.Vector3(sign, 0, 0));
        yawArrow.setLength(len, 0.18, 0.09);
        yawArrow.visible = true;
      } else {
        yawArrow.visible = false;
      }
    }
  }
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
        // Prefer server-provided list, else use fallback below
        actions = (msg.actions && msg.actions.length) ? msg.actions : actions;
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
      videoEl.addEventListener('playing', () => {
        debugState.video = 'playing';
        updateDebug();
        try { if (videoHUDMesh) videoHUDMesh.visible = true; } catch {}
      });
      videoEl.addEventListener('loadedmetadata', () => { debugState.videoDims = `${videoEl.videoWidth}x${videoEl.videoHeight}`; updateDebug(); });
    }
    // Use the preview <video> as the playback source to ensure frames are flowing
    if (previewEl && !previewEl.srcObject) previewEl.srcObject = ev.streams[0];
    if (previewEl && previewEl.srcObject) {
      videoEl = previewEl;
    } else {
      videoEl.srcObject = ev.streams[0];
    }
    // Create texture and assign to screen
    videoTexture = new THREE.VideoTexture(videoEl);
    try {
      if (THREE && THREE.NoColorSpace) {
        // three r160+ renamed color spaces; allow default
      } else if (THREE && THREE.SRGBColorSpace) {
        videoTexture.colorSpace = THREE.SRGBColorSpace;
      }
    } catch {}
    videoTexture.minFilter = THREE.LinearFilter;
    videoTexture.magFilter = THREE.LinearFilter;
    // Map video onto existing world screen material
    try {
      videoMesh.material.map = videoTexture;
      videoMesh.material.transparent = false;
      videoMesh.material.opacity = 1.0;
      videoMesh.material.needsUpdate = true;
      // Keep normal depth for proper scene blending
      videoMesh.renderOrder = 1;
    } catch {}
    // Bind texture to HUD in XR if active
    try {
      if (renderer?.xr?.isPresenting) {
        const hud = ensureVideoHUD();
        if (hud) {
          try {
            hud.material.map = videoTexture;
            hud.material.depthWrite = false;
            hud.material.depthTest = false;
            hud.renderOrder = 10000;
            hud.material.needsUpdate = true;
          } catch {}
          hud.visible = (debugState.video === 'playing');
        }
        ensureHudGroup();
      }
    } catch {}
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
  // Fallback actions if server list hasn't arrived yet
  if (!actions || actions.length === 0) {
    actions = [
      'BackFlip','Content','Dance1','Dance2','FrontFlip','FrontJump','FrontPounce','Handstand',
      'Heart','Hello','LeftFlip','RecoveryStand','RiseSit','Scrape','Sit','StandDown','StandUp','Stretch'
    ];
    layoutActionButtons();
  }
  try {
    const params = new URLSearchParams(window.location.search);
    const rb = parseInt(params.get('rb') || '', 10);
    if (!Number.isNaN(rb) && rb >= 0) RIGHT_B_INDEX = rb;
    const rp = parseInt(params.get('rp') || '', 10);
    if (!Number.isNaN(rp) && rp >= 0) RIGHT_PANEL_INDEX = rp;
  } catch {}
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
