"""
Test Acrobatic Commands for Go2 Firmware 1.1.7
===============================================

This script tests various acrobatic commands to determine which ones
still work in firmware version 1.1.7. This helps diagnose if the issue
is specific to handstand or affects all acrobatic functionality.

Commands to test:
- BackFlip (1044)
- FrontFlip (1030) 
- Dance1 (1022)
- Dance2 (1023)
- Stretch (1017)
- FingerHeart (1036)
- Handstand (1301) - for comparison
- StandOut (1039) - alternative handstand method

Usage:
    python test_acrobatic_commands.py
"""

import asyncio
import logging
import json
import sys
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD

# Enable logging for debugging
logging.basicConfig(level=logging.WARNING)

async def test_command(conn, command_name, command_id, parameters=None):
    """Test a single sport command and return success status"""
    try:
        print(f"\n🧪 Testing {command_name} (ID: {command_id})...")
        
        if parameters:
            response = await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], 
                {
                    "api_id": command_id,
                    "parameter": parameters
                }
            )
        else:
            response = await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], 
                {"api_id": command_id}
            )
        
        print(f"   Response: {response}")
        
        # Check if response indicates success
        if response and response.get('data', {}).get('header', {}).get('status', {}).get('code') == 0:
            print(f"   ✅ {command_name} - Command accepted")
            return True
        else:
            print(f"   ❌ {command_name} - Command rejected or failed")
            return False
            
    except Exception as e:
        print(f"   💥 {command_name} - Exception: {e}")
        return False

async def main():
    """Test various acrobatic commands to see what works in firmware 1.1.7"""
    conn = None
    
    try:
        print("=== Go2 Acrobatic Commands Test for Firmware 1.1.7 ===")
        print("Testing which acrobatic commands still work...")
        print("⚠️  Make sure robot has enough space and is on a stable surface!")
        
        # Connect to robot
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)
        await conn.connect()
        print("✅ Connected to robot")
        
        # Wait for user confirmation
        print("\n⚠️  WARNING: This will test acrobatic commands!")
        print("Make sure the robot has enough space and is in a safe position.")
        input("Press Enter to continue or Ctrl+C to cancel...")
        
        # Switch to AI mode (required for acrobatics)
        print("\n🔄 Switching to AI mode...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], 
            {
                "api_id": 1002,
                "parameter": {"name": "ai"}
            }
        )
        await asyncio.sleep(5)
        print("✅ Switched to AI mode")
        
        # Ensure robot is standing
        print("\n🦿 Ensuring robot is standing...")
        await test_command(conn, "StandUp", SPORT_CMD["StandUp"])
        await asyncio.sleep(3)
        
        # Test results tracking
        results = {}
        
        # # Test basic safe commands first
        # print("\n" + "="*50)
        # print("TESTING BASIC SAFE COMMANDS")
        # print("="*50)
        
        # results["Hello"] = await test_command(conn, "Hello", SPORT_CMD["Hello"])
        # await asyncio.sleep(2)
        
        # results["Stretch"] = await test_command(conn, "Stretch", SPORT_CMD["Stretch"])
        # await asyncio.sleep(3)
        
        # results["FingerHeart"] = await test_command(conn, "FingerHeart", SPORT_CMD["FingerHeart"])
        # await asyncio.sleep(3)
        
        # # Test dance commands
        # print("\n" + "="*50)
        # print("TESTING DANCE COMMANDS")
        # print("="*50)
        
        # results["Dance1"] = await test_command(conn, "Dance1", SPORT_CMD["Dance1"])
        # await asyncio.sleep(5)  # Dance takes longer
        
        # results["Dance2"] = await test_command(conn, "Dance2", SPORT_CMD["Dance2"])
        # await asyncio.sleep(5)
        
        # # Test handstand-related commands
        # print("\n" + "="*50)
        # print("TESTING HANDSTAND COMMANDS")
        # print("="*50)
        
        # results["Handstand_Direct"] = await test_command(conn, "Handstand (Direct)", SPORT_CMD["Handstand"])
        # await asyncio.sleep(3)
        
        # results["StandOut_True"] = await test_command(conn, "StandOut (True)", SPORT_CMD["StandOut"], {"data": True})
        # await asyncio.sleep(3)
        
        # results["StandOut_False"] = await test_command(conn, "StandOut (False)", SPORT_CMD["StandOut"], {"data": False})
        # await asyncio.sleep(2)
        
        # Test flip commands (WARNING: These are dangerous!)
        print(f"\n⚠️  DANGER ZONE: Testing flip commands!")
        user_input = input("Test dangerous flip commands? (y/N): ")
        if user_input.lower() == 'y':
            print("\n" + "="*50)
            print("TESTING FLIP COMMANDS (DANGEROUS!)")
            print("="*50)
            
            results["BackFlip"] = await test_command(conn, "BackFlip", SPORT_CMD["BackFlip"])
            await asyncio.sleep(5)
            
            # Return to standing after flip attempt
            await test_command(conn, "StandUp", SPORT_CMD["StandUp"])
            await asyncio.sleep(3)
        else:
            print("Skipping dangerous flip commands")
            results["BackFlip"] = "Skipped"
        
        # Return to normal mode
        print("\n🔄 Returning to normal mode...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], 
            {
                "api_id": 1002,
                "parameter": {"name": "normal"}
            }
        )
        await asyncio.sleep(3)
        
        # Display results
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)
        
        working_commands = []
        broken_commands = []
        
        for command, result in results.items():
            if result == True:
                print(f"✅ {command}: WORKING")
                working_commands.append(command)
            elif result == "Skipped":
                print(f"⏭️  {command}: SKIPPED")
            else:
                print(f"❌ {command}: NOT WORKING")
                broken_commands.append(command)
        
        print(f"\n📊 Summary:")
        print(f"   Working commands: {len(working_commands)}")
        print(f"   Broken commands: {len(broken_commands)}")
        
        if "Handstand_Direct" in broken_commands and "StandOut_True" in broken_commands:
            print(f"\n🎯 CONCLUSION: Handstand functionality appears to be completely broken in firmware 1.1.7")
        elif "Handstand_Direct" in broken_commands and "StandOut_True" in working_commands:
            print(f"\n🎯 CONCLUSION: Direct handstand is broken, but StandOut method might work")
        elif len(broken_commands) > len(working_commands):
            print(f"\n🎯 CONCLUSION: Most acrobatic commands appear to be disabled in firmware 1.1.7")
        else:
            print(f"\n🎯 CONCLUSION: Some commands work, issue may be specific to certain functions")
            
    except KeyboardInterrupt:
        print(f"\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    finally:
        if conn:
            try:
                # Emergency return to safe state
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"], 
                    {"api_id": SPORT_CMD["StandUp"]}
                )
                await asyncio.sleep(2)
                await conn.disconnect()
                print("\n✅ Safely disconnected")
            except:
                pass

if __name__ == "__main__":
    print("⚠️  WARNING: This script will test acrobatic commands on your Go2 robot!")
    print("Make sure you have:")
    print("- Enough space around the robot (at least 2m in all directions)")
    print("- Robot on a stable, flat surface")
    print("- Emergency stop ready (Ctrl+C)")
    print("")
    
    confirm = input("Do you want to proceed? (y/N): ")
    if confirm.lower() != 'y':
        print("Test cancelled")
        sys.exit(0)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest terminated by user")
        sys.exit(0) 