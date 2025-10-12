# Foul Play MCP Interface

Model Context Protocol (MCP) server for LLM-controlled Pokemon battles.

## Overview

The MCP interface enables LLMs like Claude to play Pokemon battles by exposing 7 core tools:

1. **initiate_battle** - Start ladder search (waits for match to start)
2. **challenge_user** - Challenge specific user (gen9randombattle only, waits for acceptance)
3. **get_battle_state** - Get current battle state (team, opponent, field)
4. **get_available_actions** - Get legal moves with details
5. **make_move** - Execute move decision with optimality evaluation
6. **get_pokemon_details** - Get detailed info about a specific pokemon
7. **forfeit_battle** - Forfeit battle

**Battle IDs**: The tools use actual Pokemon Showdown battle tags (e.g., `battle-gen9randombattle-2460601996`), not custom generated IDs.

## Quick Start

### 1. Set Environment Variables

```bash
export PS_USERNAME="your_pokemon_showdown_username"
export PS_PASSWORD="your_password"
export PS_SERVER="wss://sim3.psim.us/showdown/websocket"
```

### 2. Start MCP Server

```bash
# For Claude Desktop integration (stdio)
python -m fp_mcp.server

# Or directly
python fp_mcp/server.py

# For testing/development
python mcp_example.py
```

### 3. Claude Desktop Configuration

Add to your Claude Desktop MCP settings:

```json
{
  "mcpServers": {
    "foul-play": {
      "command": "python",
      "args": ["-m", "fp_mcp.server"],
      "cwd": "/path/to/foul-play",
      "env": {
        "PS_USERNAME": "your_username",
        "PS_PASSWORD": "your_password"
      }
    }
  }
}
```

## Architecture

```
┌─────────────────┐
│  LLM (Claude)   │
│  MCP Client     │
└────────┬────────┘
         │ MCP Protocol (stdio/JSON-RPC)
         │
┌────────▼────────────────────────────┐
│      MCP Server (fp_mcp/server.py)     │
│  - Tool registration & routing      │
│  - Battle session management        │
│  - State serialization              │
└────────┬────────────────────────────┘
         │
┌────────▼────────────────────────────┐
│   Battle Loop (fp_mcp/battle_loop.py)  │
│  - Modified pokemon_battle()        │
│  - Pauses for LLM decisions         │
│  - Validates and executes moves     │
└────────┬────────────────────────────┘
         │
┌────────▼────────────────────────────┐
│      Foul Play Core                 │
│  - Battle state tracking            │
│  - Pokemon Showdown protocol        │
│  - Websocket communication          │
└─────────────────────────────────────┘
```

## Tools Reference

### initiate_battle

Start searching for a random battle. **This function waits for a match to be found before returning.**

**Input:**
```json
{
  "format": "gen9randombattle"  // Optional, defaults to gen9randombattle
}
```

**Output:**
```json
{
  "battle_id": "battle-gen9randombattle-2460601996",
  "status": "active",
  "format": "gen9randombattle",
  "message": "Battle started: battle-gen9randombattle-2460601996"
}
```

**Notes:**
- Timeout: 60 seconds if no opponent found
- Battle ID is the actual Pokemon Showdown battle tag
- Returns only when battle has started

---

### challenge_user

Challenge a specific user to a gen9randombattle. **This function waits for the opponent to accept before returning.**

**Input:**
```json
{
  "opponent": "osmosisfoul"
}
```

**Output:**
```json
{
  "battle_id": "battle-gen9randombattle-2460601997",
  "status": "active",
  "format": "gen9randombattle",
  "opponent": "osmosisfoul",
  "message": "Challenge accepted! Battle started: battle-gen9randombattle-2460601997"
}
```

**Notes:**
- Only supports gen9randombattle format (hardcoded)
- Timeout: 2 minutes if opponent doesn't accept
- Battle ID is the actual Pokemon Showdown battle tag
- Returns only when opponent accepts and battle starts

---

### get_battle_state

Get the current state of a battle.

**Input:**
```json
{
  "battle_id": "battle-gen9randombattle-1730000001"
}
```

**Output:**
```json
{
  "battle_id": "battle-gen9randombattle-1730000001",
  "status": "waiting_move",
  "awaiting_decision": true,
  "state": {
    "meta": {
      "turn": 5,
      "time_remaining": 120,
      "generation": "gen9",
      "force_switch": false
    },
    "user": {
      "active": { /* your active pokemon */ },
      "reserve": [ /* your reserve pokemon */ ],
      "side_conditions": { /* hazards, screens */ }
    },
    "opponent": {
      "active": { /* opponent active (partial info) */ },
      "reserve": [ /* revealed reserve pokemon */ ]
    },
    "field": {
      "weather": "raindance",
      "terrain": null,
      "trick_room": false
    },
    "available_actions": [
      "thunderbolt",
      "voltswitch",
      "switch charizard",
      "thunderbolt-tera"
    ]
  }
}
```

---

### get_available_actions

Get detailed information about legal actions.

**Input:**
```json
{
  "battle_id": "battle-gen9randombattle-1730000001"
}
```

**Output:**
```json
{
  "battle_id": "battle-gen9randombattle-1730000001",
  "actions": [
    {
      "action": "thunderbolt",
      "type": "move",
      "details": {
        "name": "Thunderbolt",
        "type": "electric",
        "category": "special",
        "power": 90,
        "accuracy": 100,
        "pp": 24
      }
    },
    {
      "action": "switch charizard",
      "type": "switch",
      "details": {
        "name": "Charizard",
        "types": ["fire", "flying"],
        "hp": "297/297",
        "status": null
      }
    }
  ],
  "constraints": {
    "force_switch": false,
    "trapped": false,
    "can_mega": false,
    "can_tera": true
  }
}
```

---

### make_move

Execute a move decision.

**Input:**
```json
{
  "battle_id": "battle-gen9randombattle-1730000001",
  "action": "thunderbolt",
  "reasoning": "Super effective on Landorus-T (4x)"  // Optional
}
```

**Output:**
```json
{
  "battle_id": "battle-gen9randombattle-1730000001",
  "status": "sent",
  "action": "thunderbolt",
  "message": "Move sent successfully",
  "validation": {
    "valid": true,
    "reason": null
  }
}
```

**Error Response:**
```json
{
  "battle_id": "battle-gen9randombattle-1730000001",
  "status": "invalid",
  "action": "flamethrower",
  "message": "Invalid action",
  "validation": {
    "valid": false,
    "reason": "Move 'flamethrower' is not available. Available moves: thunderbolt, voltswitch, irontail, surf"
  }
}
```

---

### get_pokemon_details

Get detailed information about a specific pokemon on your team or the opponent's team.

**Input:**
```json
{
  "battle_id": "battle-gen9randombattle-2460601996",
  "pokemon_name": "charizard",
  "opponent": false  // Optional, defaults to false (your team)
}
```

**Output:**
```json
{
  "battle_id": "battle-gen9randombattle-2460601996",
  "is_opponent": false,
  "name": "charizard",
  "species": "Charizard",
  "types": ["fire", "flying"],
  "hp": "297/297",
  "status": null,
  "stats": {
    "atk": 189,
    "def": 192,
    "spa": 269,
    "spd": 206,
    "spe": 236
  },
  "moves": [
    {"name": "flamethrower", "pp": 24, "maxpp": 24},
    {"name": "airslash", "pp": 24, "maxpp": 24}
  ],
  "ability": "blaze",
  "item": "charcoal"
}
```

**Notes:**
- Use this to inspect reserve pokemon in detail
- For opponent pokemon, only revealed information is shown
- Pokemon names should be lowercase without spaces (e.g., "landorustherian")

---

### forfeit_battle

Forfeit the current battle.

**Input:**
```json
{
  "battle_id": "battle-gen9randombattle-2460601996"
}
```

**Output:**
```json
{
  "battle_id": "battle-gen9randombattle-2460601996",
  "status": "forfeited",
  "message": "Battle forfeited successfully"
}
```

---

## Files

- **server.py** - Main MCP server with tool registration
- **battle_session.py** - Session management for active battles
- **battle_loop.py** - Modified battle loop with LLM control
- **serialization.py** - Battle state → JSON conversion
- **README.md** - This file

## Example LLM Workflow

1. **Start Battle**
   ```
   LLM: initiate_battle({"format": "gen9randombattle"})
   → Returns battle_id
   ```

2. **Wait for Turn**
   ```
   LLM: get_battle_state({"battle_id": "..."})
   → Returns state with awaiting_decision: true
   ```

3. **Analyze State**
   ```
   LLM analyzes:
   - Your team (full info)
   - Opponent team (partial info)
   - Field conditions
   - Available moves
   ```

4. **Make Decision**
   ```
   LLM: make_move({
     "battle_id": "...",
     "action": "thunderbolt",
     "reasoning": "Super effective"
   })
   → Move executed
   ```

5. **Repeat**
   ```
   Continue steps 2-4 until battle finishes
   ```

## Development

### Running Tests

```bash
# Test imports
python -c "from mcp import BattleSession, battle_to_llm_json"

# Run example
python mcp_example.py

# Test with actual server
python mcp_example.py --real
```

### Logging

Set log level via environment:
```bash
export LOG_LEVEL=DEBUG
python -m fp_mcp.server
```

## Troubleshooting

**"Battle not found"**
- Battle ID may be invalid or session expired
- Check that battle_id matches response from initiate_battle

**"Battle is not waiting for a decision"**
- Called make_move when not your turn
- Check `awaiting_decision` in get_battle_state response

**"Decision timeout"**
- Must respond within 150 seconds (Pokemon Showdown timer)
- Battle will auto-forfeit on timeout

**"Invalid action"**
- Move is not in available_actions list
- Check get_available_actions for legal moves
- Ensure proper format: "thunderbolt" not "Thunderbolt"

## See Also

- [MCP_DESIGN.md](../MCP_DESIGN.md) - Complete design specification
- [CLAUDE.md](../CLAUDE.md) - General Foul Play documentation
- [MCP Protocol](https://modelcontextprotocol.io/) - MCP specification
