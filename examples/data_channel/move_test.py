"""
Minimal Move Command Tester
===========================

Run basic Move commands without the gesture/video pipeline to verify movement.

Usage:
    python examples/data_channel/move_test.py                 # default sequence
    python examples/data_channel/move_test.py --x 0.5 --wait 2 # single move
    python examples/data_channel/move_test.py --ip 192.168.8.181 --sequence

Notes:
- Uses Go2RobotHelper with minimal verbosity.
- Ensures normal mode and stands up before moving.
- Prints concise debug info for Move commands.
- Now explicitly DISABLES joystick/free-walk and restores them on exit to avoid
  interfering with other scripts.
"""

import argparse
import asyncio
import logging

from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import WebRTCConnectionMethod


async def run_single_move(robot: Go2RobotHelper, x: float, y: float, z: float, wait: float) -> None:
    print(f"Sending Move: x={x:+.3f}, y={y:+.3f}, z={z:+.3f}, wait={wait:.2f}s")
    await robot.execute_command("Move", {"x": x, "y": y, "z": z}, wait_time=wait)


async def run_sequence(robot: Go2RobotHelper) -> None:
    print("Running default movement sequence: fwd, back, left, right")
    await robot.execute_command("Move", {"x": 0.5, "y": 0.0, "z": 0.0}, wait_time=2.0)
    await robot.execute_command("Move", {"x": -0.5, "y": 0.0, "z": 0.0}, wait_time=2.0)
    await robot.execute_command("Move", {"x": 0.0, "y": 0.3, "z": 0.0}, wait_time=2.0)
    await robot.execute_command("Move", {"x": 0.0, "y": -0.3, "z": 0.0}, wait_time=2.0)


async def ensure_programmatic_control(robot: Go2RobotHelper) -> None:
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


async def restore_defaults(robot: Go2RobotHelper) -> None:
    """Restore safe defaults so this script doesn't impact others."""
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


async def main(args) -> None:
    # Minimal console output
    logging.getLogger().setLevel(logging.ERROR)

    connection_method = {
        "ap": WebRTCConnectionMethod.LocalAP,
        "sta": WebRTCConnectionMethod.LocalSTA,
        "remote": WebRTCConnectionMethod.Remote,
    }[args.method]

    async with Go2RobotHelper(
        connection_method=connection_method,
        serial_number=args.serial,
        ip=args.ip,
        username=args.username,
        password=args.password,
        enable_state_monitoring=False,
        detailed_state_display=False,
        logging_level=logging.ERROR,
    ) as robot:
        # Prepare
        await robot.ensure_mode("normal")
        await robot.execute_command("StandUp", wait_time=1.5)
        await ensure_programmatic_control(robot)

        # Execute
        if args.sequence:
            await run_sequence(robot)
        else:
            await run_single_move(robot, args.x, args.y, args.z, args.wait)

        # Cleanup/restore
        await restore_defaults(robot)
        await robot.execute_command("StandUp", wait_time=1.0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minimal Move command tester for Go2")
    parser.add_argument("--method", choices=["ap", "sta", "remote"], default="sta")
    parser.add_argument("--ip", type=str, default=None, help="Robot IP for STA mode")
    parser.add_argument("--serial", type=str, default=None, help="Robot serial number")
    parser.add_argument("--username", type=str, default=None, help="Username for remote mode")
    parser.add_argument("--password", type=str, default=None, help="Password for remote mode")

    # Single-move parameters
    parser.add_argument("--x", type=float, default=0.5, help="Forward/backward velocity")
    parser.add_argument("--y", type=float, default=0.0, help="Left/right velocity")
    parser.add_argument("--z", type=float, default=0.0, help="Yaw rate")
    parser.add_argument("--wait", type=float, default=2.0, help="Wait time after command")

    # Sequence flag
    parser.add_argument("--sequence", action="store_true", help="Run default sequence instead of single move")

    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass

