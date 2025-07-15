"""
Simple Stand Example
===================

Minimal example: Connect, Stand Up, Disconnect, Exit.
"""

import asyncio
import logging
from go2_webrtc_driver import Go2RobotHelper


async def main():
    # Minimal logging and no state monitoring for simplest operation
    async with Go2RobotHelper(
        enable_state_monitoring=False,
        logging_level=logging.ERROR
    ) as robot:
        print("🤖 Standing up...")
        await robot.execute_command("StandUp")
        print("✅ Done!")


if __name__ == "__main__":
    asyncio.run(main()) 
