#!/usr/bin/env python3
import argparse
import asyncio
import logging
import sys
from typing import Dict, Tuple

import os
import time
import random
import json
import pygame
import yaml

from go2_webrtc_driver import Go2RobotHelper
from go2_webrtc_driver.constants import WebRTCConnectionMethod, RTC_TOPIC, DATA_CHANNEL_TYPE

# Allow running as a standalone script without package context
try:
    from .gamepad_config import GamepadConfig  # type: ignore
except Exception:  # pragma: no cover - fallback for script execution
    sys.path.append(os.path.dirname(__file__))
    from gamepad_config import GamepadConfig  # type: ignore


class RateLimiter:
    def __init__(self, interval_s: float) -> None:
        self.interval_s = interval_s
        self._last_ts: float = 0.0

    def allow(self, now: float) -> bool:
        if now - self._last_ts >= self.interval_s:
            self._last_ts = now
            return True
        return False


def apply_deadzone(value: float, dz: float) -> float:
    return 0.0 if abs(value) < dz else value


async def ensure_programmatic_control(robot: Go2RobotHelper) -> None:
    # Disable joystick/free-walk and set speed level; best-effort
    for payload in ({"data": False}, {"enable": False}):
        try:
            await robot.execute_command("SwitchJoystick", payload, wait_time=0.1)
            break
        except Exception:
            continue
    for payload in ({"data": False}, {"enable": False}):
        try:
            await robot.execute_command("FreeWalk", payload, wait_time=0.1)
            break
        except Exception:
            continue
    for payload in ({"level": 3}, {"data": 3}):
        try:
            await robot.execute_command("SpeedLevel", payload, wait_time=0.1)
            break
        except Exception:
            continue
    try:
        await robot.execute_command("StopMove", wait_time=0.1)
    except Exception:
        pass


def connection_ready(robot: Go2RobotHelper) -> bool:
    try:
        conn = getattr(robot, "conn", None)
        if not conn or not getattr(conn, "isConnected", False):
            return False
        dc = getattr(conn, "datachannel", None)
        return bool(dc and dc.is_open())
    except Exception:
        return False


async def safe_execute(
    robot: Go2RobotHelper,
    command: str,
    parameter: Dict | None = None,
    wait_time: float = 0.0,
) -> bool:
    """Execute command with connection check and single reconnect attempt."""
    try:
        if not connection_ready(robot):
            # Attempt quick reconnect
            try:
                await robot.conn.reconnect()  # type: ignore[attr-defined]
            except Exception:
                return False
            # small grace period
            await asyncio.sleep(0.2)
        await robot.execute_command(command, parameter, wait_time=wait_time)
        return True
    except Exception:
        return False


def _dbg(enabled: bool, msg: str) -> None:
    if enabled:
        print(msg)


async def run_controller(cfg: GamepadConfig, debug: bool = False) -> None:
    # Minimal logs
    logging.getLogger().setLevel(logging.ERROR)

    # Map method string to enum
    connection_method = {
        "ap": WebRTCConnectionMethod.LocalAP,
        "sta": WebRTCConnectionMethod.LocalSTA,
        "remote": WebRTCConnectionMethod.Remote,
    }.get(cfg.connection.method or "sta", WebRTCConnectionMethod.LocalSTA)

    async with Go2RobotHelper(
        connection_method=connection_method,
        serial_number=cfg.connection.serial,
        ip=cfg.connection.ip,
        username=cfg.connection.username,
        password=cfg.connection.password,
        enable_state_monitoring=False,
        detailed_state_display=False,
        logging_level=logging.ERROR,
    ) as robot:
        await ensure_programmatic_control(robot)
        _dbg(debug, "[dbg] Programmatic control prepared (joystick/free-walk disabled, speed set)")

        # Optional: enable obstacle avoidance on start and allow remote API control for avoid-move
        obstacle_enabled = False
        if cfg.obstacle.enable_on_start:
            ok = await robot.obstacle_detection("enable")
            if ok:
                obstacle_enabled = True
                _dbg(debug, "[dbg] Obstacle avoidance ENABLE requested: ok")
                try:
                    await robot.conn.datachannel.pub_sub.publish_request_new(  # type: ignore[attr-defined]
                        RTC_TOPIC["OBSTACLES_AVOID"],
                        {
                            "api_id": 1004,
                            "parameter": {"is_remote_commands_from_api": True},
                        },
                    )
                    _dbg(debug, "[dbg] Set remote API control (1004) -> True: ok")
                except Exception:
                    _dbg(debug, "[dbg] Set remote API control (1004) -> True: failed")

        # Init pygame
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            print("No gamepad detected. Connect a gamepad and retry.")
            return
        joystick = pygame.joystick.Joystick(0)
        joystick.init()

        clock = pygame.time.Clock()
        limiter = RateLimiter(cfg.movement.send_interval_s)
        last_move: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        idle_sent = True
        last_avoid_keepalive = 0.0

        try:
            running = True
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.type == pygame.JOYBUTTONDOWN:
                        btn = event.button
                        # Toggle obstacle detection if configured
                        if cfg.obstacle.toggle_button_index is not None and btn == cfg.obstacle.toggle_button_index:
                            status = await robot.obstacle_detection("status")
                            if status is not None:
                                new_state = not status
                                ok = await robot.obstacle_detection("enable" if new_state else "disable")
                                if ok:
                                    obstacle_enabled = new_state
                                    _dbg(debug, f"[dbg] Obstacle avoidance toggled -> {'ENABLED' if new_state else 'DISABLED'}")
                                    try:
                                        await robot.conn.datachannel.pub_sub.publish_request_new(  # type: ignore[attr-defined]
                                            RTC_TOPIC["OBSTACLES_AVOID"],
                                            {
                                                "api_id": 1004,
                                                "parameter": {"is_remote_commands_from_api": new_state},
                                            },
                                        )
                                        _dbg(debug, f"[dbg] Set remote API control (1004) -> {new_state}: ok")
                                    except Exception:
                                        _dbg(debug, f"[dbg] Set remote API control (1004) -> {new_state}: failed")
                            continue
                        for ba in cfg.actions.buttons:
                            if ba.index == btn:
                                await safe_execute(robot, ba.command, ba.parameter, wait_time=ba.wait_time)
                                break
                    elif event.type == pygame.JOYHATMOTION:
                        # Single hat assumed (index 0)
                        x, y = event.value
                        hat_cfg = cfg.actions.hat
                        action = None
                        if y > 0 and hat_cfg and hat_cfg.up:
                            action = hat_cfg.up
                        elif y < 0 and hat_cfg and hat_cfg.down:
                            action = hat_cfg.down
                        elif x < 0 and hat_cfg and hat_cfg.left:
                            action = hat_cfg.left
                        elif x > 0 and hat_cfg and hat_cfg.right:
                            action = hat_cfg.right
                        if action:
                            await safe_execute(robot, action.command, action.parameter, wait_time=action.wait_time)

                # Continuous axes → Move
                now = pygame.time.get_ticks() / 1000.0

                # Keep 1004 true while avoidance is enabled (module can drop this)
                if obstacle_enabled and (now - last_avoid_keepalive) > 3.0:
                    try:
                        await robot.conn.datachannel.pub_sub.publish_request_new(  # type: ignore[attr-defined]
                            RTC_TOPIC["OBSTACLES_AVOID"],
                            {
                                "api_id": 1004,
                                "parameter": {"is_remote_commands_from_api": True},
                            },
                        )
                        _dbg(debug, "[dbg] Keepalive: 1004 -> True")
                    except Exception:
                        _dbg(debug, "[dbg] Keepalive: 1004 -> True (failed)")
                    last_avoid_keepalive = now
                if limiter.allow(now):
                    x, y, z = 0.0, 0.0, 0.0
                    for am in cfg.movement.axes:
                        raw = joystick.get_axis(am.index)
                        raw = -raw if am.invert else raw
                        val = apply_deadzone(raw, am.deadzone) * am.scale
                        if am.target == "x":
                            x += val
                        elif am.target == "y":
                            y += val
                        elif am.target == "z":
                            z += val

                    # Clamp
                    x = max(-cfg.movement.max_x, min(cfg.movement.max_x, x))
                    y = max(-cfg.movement.max_y, min(cfg.movement.max_y, y))
                    z = max(-cfg.movement.max_z, min(cfg.movement.max_z, z))

                    # Send only on change beyond small epsilon
                    eps = 1e-3
                    changed = (
                        abs(x - last_move[0]) > eps or
                        abs(y - last_move[1]) > eps or
                        abs(z - last_move[2]) > eps
                    )
                    if changed:
                        ok = False
                        if obstacle_enabled:
                            # Send obstacle-aware move via OBSTACLES_AVOID.Move (1003)
                            try:
                                _dbg(debug, f"[dbg] Avoid-Move 1003 send: x={x:.3f}, y={y:.3f}, yaw={z:.3f}")
                                await robot.conn.datachannel.pub_sub.publish_request_new(  # type: ignore[attr-defined]
                                    RTC_TOPIC["OBSTACLES_AVOID"],
                                    {
                                        "api_id": 1003,
                                        "parameter": {"x": x, "y": y, "yaw": z, "mode": 0},
                                    },
                                )
                                ok = True
                            except Exception:
                                # Fallback to fire-and-forget
                                try:
                                    req_id = int(time.time() * 1000) % 2147483648 + random.randint(0, 1000)
                                    robot.conn.datachannel.pub_sub.publish_without_callback(  # type: ignore[attr-defined]
                                        RTC_TOPIC["OBSTACLES_AVOID"],
                                        {
                                            "header": {"identity": {"id": req_id, "api_id": 1003}},
                                            "parameter": json.dumps({"x": x, "y": y, "yaw": z, "mode": 0}),
                                        },
                                        DATA_CHANNEL_TYPE["REQUEST"],
                                    )
                                    ok = True
                                except Exception:
                                    _dbg(debug, "[dbg] Avoid-Move send failed (both modes)")
                                    ok = False
                        else:
                            _dbg(debug, f"[dbg] Sport-Move 1008 send: x={x:.3f}, y={y:.3f}, z={z:.3f}")
                            ok = await safe_execute(robot, "Move", {"x": x, "y": y, "z": z}, wait_time=0.0)
                        if ok:
                            last_move = (x, y, z)
                            idle_sent = False
                    else:
                        # If near zero and not yet stopped, send StopMove optionally
                        if cfg.movement.send_stop_on_idle and not idle_sent and abs(x) < eps and abs(y) < eps and abs(z) < eps:
                            if obstacle_enabled:
                                try:
                                    req_id = int(time.time() * 1000) % 2147483648 + random.randint(0, 1000)
                                    _dbg(debug, f"[dbg] Avoid-Stop 1003 zero send: id={req_id}")
                                    robot.conn.datachannel.pub_sub.publish_without_callback(  # type: ignore[attr-defined]
                                        RTC_TOPIC["OBSTACLES_AVOID"],
                                        {
                                            "header": {"identity": {"id": req_id, "api_id": 1003}},
                                            "parameter": json.dumps({"x": 0.0, "y": 0.0, "yaw": 0.0, "mode": 0}),
                                        },
                                        DATA_CHANNEL_TYPE["REQUEST"],
                                    )
                                except Exception:
                                    _dbg(debug, "[dbg] Avoid-Stop send failed")
                                    pass
                            else:
                                _dbg(debug, "[dbg] Sport StopMove send")
                                await safe_execute(robot, "StopMove", wait_time=0.0)
                            idle_sent = True

                clock.tick(120)
        finally:
            try:
                await robot.conn.datachannel.pub_sub.publish_request_new(  # type: ignore[attr-defined]
                    RTC_TOPIC["OBSTACLES_AVOID"],
                    {
                        "api_id": 1004,
                        "parameter": {"is_remote_commands_from_api": False},
                    },
                )
                _dbg(debug, "[dbg] Set remote API control (1004) -> False: ok")
            except Exception:
                _dbg(debug, "[dbg] Set remote API control (1004) -> False: failed")
            await safe_execute(robot, "StopMove", wait_time=0.1)
            await safe_execute(robot, "StandUp", wait_time=1.0)


def load_config(path: str) -> GamepadConfig:
    with open(path, "r") as f:
        data: Dict = yaml.safe_load(f) or {}
    return GamepadConfig.parse_obj(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gamepad → Go2 controller")
    parser.add_argument("--config", type=str, default=None, help="Path to YAML mapping file")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug prints")
    args = parser.parse_args()

    config_path = args.config or (
        __file__.replace("gamepad_controller.py", "gamepad_mapping.yaml")
    )
    cfg = load_config(config_path)

    try:
        asyncio.run(run_controller(cfg, debug=args.debug))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


