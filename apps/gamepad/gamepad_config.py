from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, validator


class AxisMapping(BaseModel):
    """
    Map a joystick axis to a motion parameter.

    - target: which robot control to affect: x (forward/back), y (lateral sidestep), z (yaw)
    - index: joystick axis index
    - scale: multiply raw axis [-1,1] by this factor to get velocity or yaw rate
    - deadzone: ignore small inputs |v| < deadzone
    - invert: if True, multiply by -1 before scaling
    """

    target: Literal["x", "y", "z"]
    index: int
    scale: float = 1.0
    deadzone: float = 0.1
    invert: bool = False

    @validator("deadzone")
    def _deadzone_range(cls, v: float) -> float:
        if v < 0 or v >= 1:
            raise ValueError("deadzone must be in [0, 1)")
        return v


class ButtonAction(BaseModel):
    """
    Map a button to a named robot command.

    name must be a key in go2_webrtc_driver.constants.SPORT_CMD (e.g., "Hello", "StandDown", "Move").
    Optional parameter can be provided, e.g., {"data": True} or {"x": 0.5, "y": 0, "z": 0}
    """

    index: int
    command: str = Field(..., alias="name")
    parameter: Optional[Dict] = None
    wait_time: float = 1.0


class HatMapping(BaseModel):
    """Map D-pad/hat values to commands. Keys are one of up/down/left/right."""

    up: Optional[ButtonAction] = None
    down: Optional[ButtonAction] = None
    left: Optional[ButtonAction] = None
    right: Optional[ButtonAction] = None


class MovementConfig(BaseModel):
    """Continuous movement mapping driven by joystick axes."""

    axes: List[AxisMapping] = Field(default_factory=list)
    # Maximum absolute velocities to clamp final values
    max_x: float = 0.8
    max_y: float = 0.5
    max_z: float = 0.8
    # Send intervals in seconds when holding sticks
    send_interval_s: float = 0.15
    # When sticks return to near zero, send an explicit StopMove
    send_stop_on_idle: bool = True


class ActionConfig(BaseModel):
    """Discrete actions triggered by buttons/hat."""

    buttons: List[ButtonAction] = Field(default_factory=list)
    hat: Optional[HatMapping] = None


class ObstacleConfig(BaseModel):
    """Obstacle avoidance control options."""

    enable_on_start: bool = False
    toggle_button_index: Optional[int] = None


class ConnectionConfig(BaseModel):
    method: Optional[str] = Field(default="sta", description="ap|sta|remote")
    ip: Optional[str] = None
    serial: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class GamepadConfig(BaseModel):
    """Top-level config schema for the gamepad controller."""

    connection: ConnectionConfig = Field(default_factory=ConnectionConfig)
    movement: MovementConfig = Field(default_factory=MovementConfig)
    actions: ActionConfig = Field(default_factory=ActionConfig)
    obstacle: ObstacleConfig = Field(default_factory=ObstacleConfig)


