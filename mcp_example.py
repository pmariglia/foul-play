#!/usr/bin/env python3
"""
Example script showing how to use the Foul Play MCP server from Python.

This demonstrates the MCP client side - how an LLM (or any Python code)
would interact with the battle server.

Note: For actual Claude Desktop integration, the MCP server runs via stdio.
This example shows programmatic usage for testing and development.
"""

import asyncio
import json
import logging

# Note: ClientSession is from the official mcp package, not our local mcp module
try:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    MCP_CLIENT_AVAILABLE = True
except ImportError:
    MCP_CLIENT_AVAILABLE = False
    ClientSession = None
    stdio_client = None


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_battle():
    """
    Example: Play a battle using the MCP interface.

    This simulates what an LLM would do:
    1. Start a battle
    2. Get battle state
    3. Analyze and make decisions
    4. Repeat until battle ends
    """

    # Connect to MCP server (assumes server is running)
    # For this example, we'll show the tool calls that would be made

    print("="*60)
    print("EXAMPLE: LLM-Controlled Pokemon Battle via MCP")
    print("="*60)
    print()

    # Step 1: Initiate battle
    print("Step 1: Starting battle search...")
    print("Tool: initiate_battle")
    print("Args: {\"format\": \"gen9randombattle\"}")
    print()

    # Simulated response
    battle_id = "battle-gen9randombattle-1730000001"
    print(f"Response: {json.dumps({
        'battle_id': battle_id,
        'status': 'searching',
        'format': 'gen9randombattle',
        'message': 'Searching for gen9randombattle match...'
    }, indent=2)}")
    print()

    # Step 2: Poll for battle state
    print("Step 2: Waiting for battle to start...")
    print(f"Tool: get_battle_state")
    print(f"Args: {{\"battle_id\": \"{battle_id}\"}}")
    print()

    # Simulated: Battle found and started
    print("Response: Battle found! Turn 1 starting...")
    print()

    # Step 3: Get battle state
    print("Step 3: Analyzing battle state...")
    print(f"Tool: get_battle_state")
    print(f"Args: {{\"battle_id\": \"{battle_id}\"}}")
    print()

    # Simulated battle state
    state_example = {
        "battle_id": battle_id,
        "status": "waiting_move",
        "awaiting_decision": True,
        "state": {
            "meta": {
                "turn": 1,
                "time_remaining": 150,
                "generation": "gen9",
                "format": "gen9randombattle",
                "force_switch": False,
            },
            "user": {
                "active": {
                    "name": "pikachu",
                    "hp": 250,
                    "max_hp": 250,
                    "status": None,
                    "ability": "static",
                    "moves": [
                        {"name": "thunderbolt", "pp": 24, "max_pp": 24, "disabled": False},
                        {"name": "voltswitch", "pp": 32, "max_pp": 32, "disabled": False},
                        {"name": "irontail", "pp": 24, "max_pp": 24, "disabled": False},
                        {"name": "surf", "pp": 24, "max_pp": 24, "disabled": False},
                    ],
                    "can_terastallize": True,
                },
            },
            "opponent": {
                "active": {
                    "name": "landorustherian",
                    "hp": 312,
                    "max_hp": 312,
                    "status": None,
                    "ability": "intimidate",
                },
            },
            "available_actions": [
                "thunderbolt",
                "voltswitch",
                "irontail",
                "surf",
                "thunderbolt-tera",
            ],
        }
    }

    print(f"Response: {json.dumps(state_example, indent=2)}")
    print()

    # Step 4: LLM analyzes and makes decision
    print("Step 4: LLM Decision Process")
    print("-" * 60)
    print("Analysis:")
    print("- My Pikachu (Electric) vs Opponent's Landorus-Therian (Ground/Flying)")
    print("- Thunderbolt is super effective (4x) against Ground/Flying")
    print("- Landorus-Therian is commonly Choice Scarfed")
    print("- Decision: Use Thunderbolt for likely OHKO")
    print()

    # Step 5: Execute decision
    print("Step 5: Executing move...")
    print(f"Tool: make_move")
    print(f"Args: {{")
    print(f"  \"battle_id\": \"{battle_id}\",")
    print(f"  \"action\": \"thunderbolt\",")
    print(f"  \"reasoning\": \"Thunderbolt is 4x super effective on Landorus-T\"")
    print(f"}}")
    print()

    print(f"Response: {json.dumps({
        'battle_id': battle_id,
        'status': 'sent',
        'action': 'thunderbolt',
        'message': 'Move sent successfully',
        'validation': {'valid': True, 'reason': None}
    }, indent=2)}")
    print()

    # Step 6: Continue battle
    print("Step 6: Continue until battle ends...")
    print("(Repeat steps 3-5 for each turn)")
    print()

    print("="*60)
    print("Example complete! See mcp/server.py for actual implementation.")
    print("="*60)


async def real_mcp_client_example():
    """
    Example of actual MCP client connection (requires server running).

    To run this:
    1. Start the MCP server: python -m mcp.server
    2. Run this script

    Note: Requires mcp client package installed separately
    """
    if not MCP_CLIENT_AVAILABLE:
        print("MCP client not available.")
        print("Install with: pip install mcp-client")
        print("Note: This is the official MCP client, not our server module.")
        return

    try:
        # Connect to MCP server via stdio
        server_params = {
            "command": "python",
            "args": ["-m", "mcp.server"],
        }

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize
                await session.initialize()

                # List available tools
                tools = await session.list_tools()
                print("Available tools:")
                for tool in tools.tools:
                    print(f"  - {tool.name}: {tool.description}")

                # Example: Initiate battle
                result = await session.call_tool(
                    "initiate_battle",
                    {"format": "gen9randombattle"}
                )

                print(f"\nBattle initiated: {result.content}")

    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: This requires the MCP server to be running.")
        print("For testing, run the simulated example instead:")
        print("  python mcp_example.py --simulate")


if __name__ == "__main__":
    import sys

    if "--real" in sys.argv:
        print("Running real MCP client example...")
        asyncio.run(real_mcp_client_example())
    else:
        print("Running simulated example (use --real for actual MCP connection)")
        asyncio.run(example_battle())
