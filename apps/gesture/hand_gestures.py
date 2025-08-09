import argparse
import asyncio
import logging
import time
from collections import deque
from typing import List, Tuple

import cv2
import mediapipe as mp

from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import WebRTCConnectionMethod


class GestureType:
    PUSH_FORWARD = "push_forward"
    PULL_BACKWARD = "pull_backward"
    PUSH_DOWN = "push_down"
    PUSH_UP = "push_up"
    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"


class HandMotionDetector:
    """
    Single-hand motion detector using MediaPipe hand landmarks.
    """

    def __init__(self, history_size: int = 5):
        self.centroid_history = deque(maxlen=history_size)
        self.area_history = deque(maxlen=history_size)
        self.time_history = deque(maxlen=history_size)

    def update(self, landmarks, frame_width: int, frame_height: int):
        xs = [lm.x * frame_width for lm in landmarks]
        ys = [lm.y * frame_height for lm in landmarks]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        centroid_x = (min_x + max_x) / 2.0
        centroid_y = (min_y + max_y) / 2.0
        area = (max_x - min_x) * (max_y - min_y)

        self.centroid_history.append((centroid_x, centroid_y))
        self.area_history.append(area)
        self.time_history.append(time.time())

    def _derivatives(self) -> Tuple[float, float, float]:
        if len(self.time_history) < 2:
            return 0.0, 0.0, 0.0
        dt = self.time_history[-1] - self.time_history[0]
        if dt <= 1e-6:
            return 0.0, 0.0, 0.0
        (x0, y0) = self.centroid_history[0]
        (x1, y1) = self.centroid_history[-1]
        area0 = self.area_history[0]
        area1 = self.area_history[-1]
        vx = (x1 - x0) / dt
        vy = (y1 - y0) / dt
        va = (area1 - area0) / dt
        return vx, vy, va

    def detect(self) -> str | None:
        vx, vy, va = self._derivatives()

        # Thresholds depend on frame size; use relative magnitudes
        if abs(vx) > 400 and abs(vx) > abs(vy) * 1.4:
            return GestureType.SWIPE_RIGHT if vx > 0 else GestureType.SWIPE_LEFT

        if abs(vy) > 400 and abs(vy) > abs(vx) * 1.4:
            return GestureType.PUSH_DOWN if vy > 0 else GestureType.PUSH_UP

        if abs(va) > 300000:
            return GestureType.PULL_BACKWARD if va < 0 else GestureType.PUSH_FORWARD

        return None


class MultiHandMotionDetector:
    """
    Track up to two hands and detect two-hands up/down gestures.
    """

    def __init__(self, history_size: int = 5):
        # Two slots: left (slot 0) and right (slot 1) by image X position
        self.centroid_histories = [deque(maxlen=history_size), deque(maxlen=history_size)]
        self.time_histories = [deque(maxlen=history_size), deque(maxlen=history_size)]

    @staticmethod
    def _centroid_and_area(landmarks, frame_w: int, frame_h: int) -> Tuple[float, float, float]:
        xs = [lm.x * frame_w for lm in landmarks]
        ys = [lm.y * frame_h for lm in landmarks]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        area = (max_x - min_x) * (max_y - min_y)
        return cx, cy, area

    def update(self, hands_landmarks: List, frame_w: int, frame_h: int) -> None:
        # Compute centroids for all hands and sort by x to assign slots
        hands_with_centroids = []
        for lm in hands_landmarks:
            cx, cy, _ = self._centroid_and_area(lm.landmark, frame_w, frame_h)
            hands_with_centroids.append((cx, cy, lm))
        hands_with_centroids.sort(key=lambda t: t[0])  # left to right

        now = time.time()
        # Reset slots if not enough hands present
        for slot in range(2):
            # We do not clear histories every frame to keep continuity
            pass

        # Fill slots with up to 2 hands
        for slot, (_, cy, lm) in enumerate(hands_with_centroids[:2]):
            self.centroid_histories[slot].append(cy)
            self.time_histories[slot].append(now)

    def _vy(self, slot: int) -> float:
        th = self.time_histories[slot]
        ch = self.centroid_histories[slot]
        if len(th) < 2:
            return 0.0
        dt = th[-1] - th[0]
        if dt <= 1e-6:
            return 0.0
        return (ch[-1] - ch[0]) / dt

    def detect_two_hands_updown(self) -> str | None:
        # Need both slots to have history
        if any(len(self.time_histories[slot]) < 2 for slot in (0, 1)):
            return None
        vy0 = self._vy(0)
        vy1 = self._vy(1)
        vy_thresh = 400.0
        same_direction = (vy0 > 0 and vy1 > 0) or (vy0 < 0 and vy1 < 0)
        if not same_direction:
            return None
        if abs(vy0) > vy_thresh and abs(vy1) > vy_thresh:
            return GestureType.PUSH_DOWN if vy0 > 0 else GestureType.PUSH_UP
        return None


def simulate_gesture_action(gesture: str) -> str:
    """
    Return a concise simulation string describing the intended action.
    """
    if gesture == GestureType.PUSH_FORWARD:
        x, y, z, wait_time = -0.5, 0.0, 0.0, 1.2
        linear_mag = (x ** 2 + y ** 2) ** 0.5
        msg = (
            f"SIM Move | x={x:+.3f}, y={y:+.3f}, z={z:+.3f}, lin|={linear_mag:.3f}, "
            f"wait={wait_time:.2f}s"
        )
        print(msg)
        return msg
    if gesture == GestureType.PULL_BACKWARD:
        x, y, z, wait_time = 0.5, 0.0, 0.0, 1.2
        linear_mag = (x ** 2 + y ** 2) ** 0.5
        msg = (
            f"SIM Move | x={x:+.3f}, y={y:+.3f}, z={z:+.3f}, lin|={linear_mag:.3f}, "
            f"wait={wait_time:.2f}s"
        )
        print(msg)
        return msg
    if gesture == GestureType.PUSH_DOWN:
        msg = "SIM StandDown"
        print(msg)
        return msg
    if gesture == GestureType.PUSH_UP:
        msg = "SIM StandUp"
        print(msg)
        return msg
    if gesture == GestureType.SWIPE_LEFT:
        x, y, z, wait_time = 0.0, 0.3, 0.0, 1.0
        linear_mag = (x ** 2 + y ** 2) ** 0.5
        msg = (
            f"SIM Move | x={x:+.3f}, y={y:+.3f}, z={z:+.3f}, lin|={linear_mag:.3f}, "
            f"wait={wait_time:.2f}s"
        )
        print(msg)
        return msg
    if gesture == GestureType.SWIPE_RIGHT:
        x, y, z, wait_time = 0.0, -0.3, 0.0, 1.0
        linear_mag = (x ** 2 + y ** 2) ** 0.5
        msg = (
            f"SIM Move | x={x:+.3f}, y={y:+.3f}, z={z:+.3f}, lin|={linear_mag:.3f}, "
            f"wait={wait_time:.2f}s"
        )
        print(msg)
        return msg
    return ""


async def gesture_to_robot(robot: Go2RobotHelper, gesture: str) -> str:
    """
    Map detected gesture to robot command.

    Mapping based on apps/gesture/README.md:
    - push hand forward: move back (robot away from you)
    - push hand backward: move forward (robot towards you)
    - push hand down: dog lays down
    - push hand up: dog stands up
    - swipe hand left: side step left
    - swipe hand right: side step right
    """
    # Minimal prints to respect user's preference

    if gesture == GestureType.PUSH_FORWARD:
        await robot.execute_command("Move", {"x": -0.5, "y": 0, "z": 0}, wait_time=1.2)
        return "Move back (x=-0.5)"
    if gesture == GestureType.PULL_BACKWARD:
        await robot.execute_command("Move", {"x": 0.5, "y": 0, "z": 0}, wait_time=1.2)
        return "Move forward (x=+0.5)"
    if gesture == GestureType.PUSH_DOWN:
        await robot.execute_command("StandDown", wait_time=1.5)
        return "StandDown"
    if gesture == GestureType.PUSH_UP:
        await robot.execute_command("StandUp", wait_time=1.5)
        return "StandUp"
    if gesture == GestureType.SWIPE_LEFT:
        await robot.execute_command("Move", {"x": 0, "y": 0.3, "z": 0}, wait_time=1.0)
        return "Side step left (y=+0.3)"
    if gesture == GestureType.SWIPE_RIGHT:
        await robot.execute_command("Move", {"x": 0, "y": -0.3, "z": 0}, wait_time=1.0)
        return "Side step right (y=-0.3)"
    return ""


async def _ensure_programmatic_control(robot: Go2RobotHelper) -> None:
    """Disable modes that can block API-driven Move and set sane speed level."""
    # Best-effort: disable joystick control
    for payload in ({"data": False}, {"enable": False}):
        try:
            await robot.execute_command("SwitchJoystick", payload, wait_time=0.2)
            break
        except Exception:
            continue

    # Best-effort: disable free-walk/lead-follow modes
    for payload in ({"data": False}, {"enable": False}):
        try:
            await robot.execute_command("FreeWalk", payload, wait_time=0.2)
            break
        except Exception:
            continue

    # Best-effort: set speed level
    for payload in ({"level": 3}, {"data": 3}):
        try:
            await robot.execute_command("SpeedLevel", payload, wait_time=0.2)
            break
        except Exception:
            continue

    # Ensure motion is stopped before starting
    try:
        await robot.execute_command("StopMove", wait_time=0.2)
    except Exception:
        pass


async def _restore_defaults(robot: Go2RobotHelper) -> None:
    """Restore safe defaults so this app doesn't impact others."""
    # Stop any residual motion
    try:
        await robot.execute_command("StopMove", wait_time=0.2)
    except Exception:
        pass

    # Re-disable joystick and free-walk to leave robot in API-friendly state
    for payload in ({"data": False}, {"enable": False}):
        try:
            await robot.execute_command("SwitchJoystick", payload, wait_time=0.2)
            break
        except Exception:
            continue
    for payload in ({"data": False}, {"enable": False}):
        try:
            await robot.execute_command("FreeWalk", payload, wait_time=0.2)
            break
        except Exception:
            continue


async def run(simulation: bool = False, require_two_hands_updown: bool = True):
    # Reduce verbosity and disable state monitoring for minimal console noise
    logging.getLogger().setLevel(logging.ERROR)

    if not simulation:
        robot_ctx = Go2RobotHelper(
            connection_method=WebRTCConnectionMethod.LocalSTA,
            enable_state_monitoring=False,
            detailed_state_display=False,
            logging_level=logging.ERROR,
        )
    else:
        robot_ctx = None

    async def gesture_loop(robot: Go2RobotHelper | None):
        # Initialize MediaPipe Hands
        mp_hands = mp.solutions.hands
        mp_drawing = mp.solutions.drawing_utils
        hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.5,
        )

        single = HandMotionDetector(history_size=6)
        multi = MultiHandMotionDetector(history_size=6)
        last_trigger_time = 0.0
        trigger_cooldown_sec = 0.8

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Failed to open webcam.")
            return

        try:
            # Initialize posture only in real mode
            if robot is not None:
                await robot.ensure_mode("normal")
                await robot.execute_command("StandUp", wait_time=1.5)
                await _ensure_programmatic_control(robot)

            last_info = ""
            while True:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.01)
                    continue

                frame = cv2.flip(frame, 1)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Offload heavy MediaPipe processing to a worker thread to avoid
                # blocking the asyncio event loop (which drives WebRTC I/O)
                result = await asyncio.to_thread(hands.process, frame_rgb)

                frame_h, frame_w = frame.shape[:2]

                gesture = None
                if result.multi_hand_landmarks:
                    # Update multi-hand histories
                    multi.update(result.multi_hand_landmarks, frame_w, frame_h)

                    # Pick primary hand for single-hand detection: largest area
                    areas = []
                    for lm in result.multi_hand_landmarks:
                        xs = [p.x * frame_w for p in lm.landmark]
                        ys = [p.y * frame_h for p in lm.landmark]
                        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                        areas.append(area)
                    primary_idx = int(max(range(len(areas)), key=lambda i: areas[i]))
                    primary_lm = result.multi_hand_landmarks[primary_idx]
                    single.update(primary_lm.landmark, frame_w, frame_h)

                    # Two-hands up/down first if required
                    if require_two_hands_updown:
                        gesture = multi.detect_two_hands_updown()

                    # Otherwise rely on single-hand detector
                    if gesture is None:
                        g_single = single.detect()
                        # If two-hands required, suppress single-hand up/down
                        if require_two_hands_updown and g_single in (GestureType.PUSH_UP, GestureType.PUSH_DOWN):
                            pass
                        else:
                            gesture = g_single

                    # Draw landmarks
                    for lm in result.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS)

                now = time.time()
                if gesture and (now - last_trigger_time) > trigger_cooldown_sec:
                    last_trigger_time = now
                    if robot is None:
                        last_info = simulate_gesture_action(gesture)
                    else:
                        last_info = await gesture_to_robot(robot, gesture)
                    # Brief yield to keep UI responsive
                    await asyncio.sleep(0)

                cv2.putText(
                    frame,
                    ("SIM" if simulation else "LIVE") + (" | 2H up/down" if require_two_hands_updown else "" ) + " | q: quit",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                if last_info:
                    cv2.putText(
                        frame,
                        last_info,
                        (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2,
                        cv2.LINE_AA,
                    )
                cv2.imshow("Go2 Hand Gestures", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

                # Yield control to event loop
                await asyncio.sleep(0)

        finally:
            cap.release()
            cv2.destroyAllWindows()

        if robot is not None:
            # End with robot standing and restore defaults
            await _restore_defaults(robot)
            await robot.execute_command("StandUp", wait_time=1.5)

    if robot_ctx is None:
        await gesture_loop(None)
    else:
        async with robot_ctx as robot:
            await gesture_loop(robot)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Control Go2 with hand gestures")
    parser.add_argument("--sim", action="store_true", help="Run in simulation mode (no robot)")
    parser.add_argument("--single-hand-updown", action="store_true", help="Allow single-hand up/down (default requires two hands)")
    args = parser.parse_args()

    try:
        asyncio.run(run(simulation=args.sim, require_two_hands_updown=not args.single_hand_updown))
    except KeyboardInterrupt:
        pass