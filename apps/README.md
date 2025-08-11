# Small Apps for the Go2

## gesture

Control the Go2 using simple hand gestures captured from your webcam. The app uses MediaPipe to track hands and translates motion into robot commands over WebRTC via `Go2RobotHelper`. It supports a simulation mode (no robot) and an option to require two-hand up/down to reduce false triggers.

- Supported motions → actions:
  - push hand forward → move back (robot away from you)
  - pull hand backward → move forward (robot toward you)
  - push hand down → StandDown
  - push hand up → StandUp
  - swipe left/right → side step left/right

Script: `apps/gesture/hand_gestures.py`

## gamepad

Drive the Go2 with a USB/Bluetooth gamepad. Joystick axes provide continuous motion (x: forward/back, y: sidestep, z: yaw). Buttons and the D‑pad trigger discrete actions. Behavior is configurable via `apps/gamepad/gamepad_mapping.yaml` and validated with the schema in `apps/gamepad/gamepad_config.py`. Includes an optional obstacle-avoidance toggle and a visualizer to discover your controller’s indices.

Script: `apps/gamepad_control.py`

When you don't know the papping, use `apps/gamepad/gamepad_visualizer.py` to visualize the gampedad control mapings.
