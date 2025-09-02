import argparse
import asyncio
import logging
import sys
from typing import Dict, List

from .robot_helper import Go2RobotHelper


# Supported action names (case-insensitive on input, canonicalized for execution)
SUPPORTED_ACTIONS: List[str] = [
    "StandUp",
    "StandDown",
    "RecoveryStand",
    "Sit",
    "RiseSit",
    "Hello",
    "Stretch",
    "Content",
    "Scrape",
    "Heart",
    "Dance1",
    "Dance2",
    "FrontFlip",
    "LeftFlip",
    "BackFlip",
    "FrontJump",
    "FrontPounce",
    "Handstand",
]


# Human-readable descriptions for actions
ACTION_DESCRIPTIONS: Dict[str, str] = {
    "StandUp": "Stand up from sitting/lying to a stable stance",
    "StandDown": "Lower body to rest (safe stand down)",
    "RecoveryStand": "Recover from a fall and return to standing",
    "Sit": "Sit down",
    "RiseSit": "Rise the body from sitting pose",
    "Hello": "Greeting gesture",
    "Stretch": "Full-body stretch sequence",
    "Content": "Contented/relaxed gesture",
    "Scrape": "Scraping motion with the forelegs",
    "Heart": "Heart gesture with legs",
    "Dance1": "Dance routine 1",
    "Dance2": "Dance routine 2",
    "FrontFlip": "Perform a front flip (advanced)",
    "LeftFlip": "Perform a left flip (advanced)",
    "BackFlip": "Perform a back flip (advanced)",
    "FrontJump": "Jump forward",
    "FrontPounce": "Forward pounce",
    "Handstand": "Enter a handstand pose (advanced)",
}


def _build_name_map() -> Dict[str, str]:
    name_map: Dict[str, str] = {}
    for name in SUPPORTED_ACTIONS:
        name_map[name.lower()] = name
    return name_map


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="go2action",
        description="Execute a single action on the Unitree Go2 via WebRTC",
    )
    parser.add_argument(
        "action",
        nargs="?",
        help="Action to execute. Use --list to see supported actions.",
    )
    parser.add_argument(
        "-w",
        "--wait",
        type=float,
        default=3.0,
        help="Seconds to wait after sending the action (default: 3)",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Enable state monitoring output (disabled by default)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List supported actions and exit",
    )
    return parser.parse_args(argv)


async def _run(action: str, wait_s: float, enable_monitor: bool) -> int:
    # Minimal console verbosity by default
    logging_level = logging.ERROR

    async with Go2RobotHelper(
        enable_state_monitoring=enable_monitor,
        detailed_state_display=False,
        logging_level=logging_level,
    ) as robot:
        await robot.execute_command(action, wait_time=wait_s)
    return 0


def main() -> int:
    args = parse_args(sys.argv[1:])

    if args.list:
        names = sorted(SUPPORTED_ACTIONS)
        width = max(len(n) for n in names) if names else 0
        for n in names:
            desc = ACTION_DESCRIPTIONS.get(n, "")
            print(f"{n.ljust(width)}  -  {desc}")
        return 0

    if not args.action:
        print("Error: action is required. Use --list to see supported actions.")
        return 2

    name_map = _build_name_map()
    key = args.action.strip().lower()
    if key not in name_map:
        print(
            f"Unknown action: {args.action}. Supported: {', '.join(sorted(SUPPORTED_ACTIONS))}"
        )
        return 2

    action = name_map[key]

    try:
        return asyncio.run(_run(action, args.wait, args.monitor))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"Failed to execute {action}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


