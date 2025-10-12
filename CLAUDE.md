# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Foul Play is a Pokémon battle-bot that plays on Pokemon Showdown using a Monte Carlo Tree Search (MCTS) algorithm powered by the Rust-based `poke-engine` library. It supports all generations (gen1-gen9) and can play both random battles and standard battles with custom teams.

## Development Commands

### Setup
```bash
# Install dependencies (requires Rust for poke-engine compilation)
pip install -r requirements.txt

# Install dev dependencies (includes ruff for linting and pytest)
pip install -r requirements-dev.txt
```

### Running the Bot
```bash
# Basic example: gen9 random battle
python run.py \
  --websocket-uri wss://sim3.psim.us/showdown/websocket \
  --ps-username 'Username' \
  --ps-password 'password' \
  --bot-mode search_ladder \
  --pokemon-format gen9randombattle

# See all available options
python run.py --help
```

### Testing & Linting
```bash
# Run all tests
pytest tests

# Run specific test file
pytest tests/test_battle.py

# Lint code
make lint          # or: ruff check --fix

# Format code
make fmt           # or: ruff format

# Run full CI suite (lint + format check + tests)
make test          # or: ruff check && pytest tests
```

### Engine Management

The poke-engine must be compiled with generation-specific features. By default it uses the `terastallization` feature (gen9).

```bash
# Re-install engine for a different generation
make poke_engine GEN=gen4
# Expands to: pip uninstall -y poke-engine && pip install -v --force-reinstall --no-cache-dir poke-engine==X.X.X --config-settings="build-args=--features poke-engine/gen4 --no-default-features"

# Install from local poke-engine repo (assumes ../poke-engine exists)
make poke_engine_local GEN=gen4
```

**Important**: pip caches .whl artifacts and can't detect build feature changes, so always use `--force-reinstall --no-cache-dir` when changing generations.

### Docker
```bash
# Build for default generation (gen9)
make docker

# Build for specific generation
make docker GEN=gen4

# Run the Docker image
docker run --rm --network host foul-play:latest \
  --websocket-uri wss://sim3.psim.us/showdown/websocket \
  --ps-username 'Username' \
  --ps-password 'password' \
  --bot-mode search_ladder \
  --pokemon-format gen9randombattle
```

## Architecture

### Core Flow

1. **Initialization** (`run.py`):
   - Configures bot via command-line arguments (see `config.py`)
   - Applies generation-specific mods to move/pokedex data (`data/mods/apply_mods.py`)
   - Connects to Pokemon Showdown websocket (`fp/websocket_client.py`)

2. **Battle Loop** (`fp/run_battle.py`):
   - `start_battle()`: Handles team preview, initializes battle state
   - `pokemon_battle()`: Main battle loop that receives messages, updates state, and sends moves
   - Battle state is tracked in `Battle` object (`fp/battle.py`)

3. **State Updates** (`fp/battle_modifier.py`):
   - Parses Pokemon Showdown protocol messages (switches, moves, damage, status, etc.)
   - Updates `Battle` object with current game state
   - This file is ~4500 lines and contains most protocol parsing logic

4. **Move Selection** (`fp/search/main.py`):
   - `find_best_move()`: Entry point for decision-making
   - Generates multiple battle scenarios based on unknown information (opponent moves/stats/items)
   - Converts Python `Battle` to `poke-engine` state (`fp/search/poke_engine_helpers.py`)
   - Runs parallel MCTS searches via ProcessPoolExecutor
   - Aggregates results and selects move probabilistically

### Key Modules

- **`fp/battle.py`**: Core data structures (`Battle`, `Battler`, `Pokemon`, `Move`)
  - `Battle`: Represents full battle state (both sides, field conditions, weather, etc.)
  - `Battler`: Represents one side (active pokemon, reserves, side conditions)
  - `Pokemon`: Individual pokemon state (stats, moves, HP, status, boosts, etc.)

- **`fp/battle_modifier.py`**: Protocol message parser
  - `async_update_battle()`: Processes incoming Pokemon Showdown messages
  - Handles all battle events: damage, switches, faint, weather, terrain, abilities, etc.

- **`fp/search/`**: MCTS decision engine
  - `main.py`: Orchestrates parallel search across battle scenarios
  - `standard_battles.py`: Prepares battle variations for standard/factory formats
  - `random_battles.py`: Prepares battle variations for random battles
  - `poke_engine_helpers.py`: Converts Python battle state to Rust engine format

- **`data/`**: Game data
  - `pokedex.json`, `moves.json`: Base data for all pokemon/moves
  - `mods/`: Generation-specific modifications applied at startup
  - `pkmn_sets.py`: Smogon sets for inferring opponent pokemon details

- **`config.py`**: Configuration management via argparse
  - Bot modes: `challenge_user`, `accept_challenge`, `search_ladder`
  - Search parameters: `search_time_ms`, `search_parallelism`
  - Logging configuration

### Battle Types

1. **Random Battles**: Bot and opponent have randomly generated teams
2. **Standard Battles**: Custom teams from `teams/` directory
3. **Battle Factory**: Special format with preset teams by tier

### Unknown Information Handling

The bot must handle incomplete information about the opponent:
- **Random battles**: Generate possible teams using `data/pkmn_sets.py` datasets
- **Standard battles**: Use Smogon usage stats to infer spreads/sets
- **Team preview**: Special handling for pokemon with hidden forms (see `smart_team_preview` in `fp/battle.py`)

Multiple battle scenarios are created with different assumptions, each is searched in parallel, and results are weighted by likelihood.

### Data Integrity

The bot performs integrity checks after each battle (`run.py:21-42`) to ensure the shared `pokedex` and `all_move_json` dictionaries were not accidentally mutated during the battle.

## Move Evaluation API (Stockfish-like Analysis)

The bot includes a move evaluation system similar to Stockfish for chess. This allows you to:
- Get optimality scores (0-1) for all available moves
- Analyze post-game: "Was Thunderbolt optimal on turn 5?"
- Compare moves to find mistakes

### Usage

**Enable during live battles:**
```bash
python run.py --enable-evaluation [other args]
```

**Programmatic API:**
```python
from fp.search.main import find_best_move

# Get best move + full evaluation
best_move, evaluation = find_best_move(battle, return_evaluation=True)

# Check specific move
move_eval = evaluation.get_move_evaluation("thunderbolt")
print(f"Optimality: {move_eval.optimality:.1%}")  # 0-1 scale
print(f"Win rate: {move_eval.win_rate:+.3f}")     # -1 to 1

# Get top moves
for move_eval in evaluation.get_top_moves(5):
    print(f"{move_eval.move}: {move_eval.optimality:.3f}")

# Export to JSON
import json
with open("analysis.json", "w") as f:
    json.dump(evaluation.to_dict(), f)
```

### Evaluation Metrics

- **Optimality (0-1)**: Normalized score where 1.0 = best move
- **Visit Percentage**: Proportion of MCTS visits (indicates exploration/confidence)
- **Win Rate (-1 to 1)**: Expected outcome from simulations (1 = guaranteed win)
- **Scenarios**: Number of game states analyzed (handles unknown opponent info)

See `evaluate_position.py` for detailed examples.

## MCP Interface for LLM Control

Foul Play provides an MCP (Model Context Protocol) interface that enables LLMs like Claude to play Pokemon battles. This provides a clean API for:
- Initiating battles (ladder search or user challenge)
- Inspecting battle state (team, opponent, field conditions)
- Executing move decisions with real-time optimality feedback
- Getting available actions with validation

### Architecture

```
LLM (Claude/GPT-4)
    ↓ MCP Protocol
MCP Server (manages battle sessions)
    ↓ Modified battle loop
Foul Play Core → Pokemon Showdown
```

### Core MCP Tools

1. **`initiate_battle(format)`**: Start ladder search, returns battle_id
2. **`challenge_user(opponent, format)`**: Challenge specific user
3. **`get_battle_state(battle_id)`**: Full battle state as JSON (compact reserve mode)
4. **`get_available_actions(battle_id)`**: Legal moves/switches with details
5. **`make_move(battle_id, action, reasoning?)`**: Execute move decision with optimality feedback
6. **`get_pokemon_details(battle_id, pokemon_name, opponent?)`**: Detailed pokemon inspection
7. **`forfeit_battle(battle_id)`**: Forfeit current battle

#### Move Evaluation in make_move

The `make_move` tool includes real-time evaluation powered by MCTS:

```json
{
  "status": "sent",
  "action": "thunderbolt",
  "evaluation": {
    "optimality": 0.950,
    "best_move": "thunderbolt",
    "is_optimal": true,
    "scenarios_analyzed": 4
  }
}
```

- **optimality**: 0-1 scale (1.0 = best move)
- **best_move**: MCTS-recommended move
- **is_optimal**: True if chosen move equals best_move
- **scenarios_analyzed**: Number of game states evaluated

Enable/disable with `ENABLE_EVALUATION` environment variable (default: true).

### Implementation Details

**Battle Session Management**:
- Each battle gets unique ID and websocket connection
- Battle loop runs async in background
- Pauses at decision points to wait for LLM input
- Validates all moves before sending to server

**State Serialization**:
- Full battle state → JSON (~5-10KB)
- Reserve pokemon shown in compact mode to save tokens
- Properly handles hidden opponent info
- Use `get_pokemon_details()` for full inspection of specific pokemon

**Move Evaluation**:
- Runs MCTS evaluation after validation
- ~100ms overhead per move (configurable)
- Deep copies battle state to avoid mutation
- Gracefully handles evaluation failures

**Key Files**:
- `fp_mcp/server.py`: Main MCP server with @mcp.tool() decorators (7 tools)
- `fp_mcp/battle_session.py`: Session management with async decision queue
- `fp_mcp/battle_loop.py`: Modified battle loop that waits for LLM
- `fp_mcp/serialization.py`: Battle state → JSON with compact/full modes

### Usage

**Start MCP Server:**
```bash
export PS_USERNAME="your_username"
export PS_PASSWORD="your_password"
export ENABLE_EVALUATION="true"  # Optional, default is true
python -m fp_mcp.server
```

**Claude Desktop Configuration:**
Add to `~/.config/claude-code/config.json`:
```json
{
  "mcpServers": {
    "foul-play": {
      "command": "python3",
      "args": ["-m", "fp_mcp.server"],
      "cwd": "/absolute/path/to/foul-play",
      "env": {
        "PS_USERNAME": "your_username",
        "PS_PASSWORD": "your_password",
        "ENABLE_EVALUATION": "true"
      }
    }
  }
}
```

**Example Prompts:**
- "Start a gen9 random battle"
- "What's my team? Show me the battle state"
- "Use Thunderbolt against Gyarados"
- "Get details about my Charizard"

**Documentation:**
- `MCP.md`: Complete setup and usage guide
- `MCP_DESIGN.md`: Technical specification
- `fp_mcp/README.md`: API reference
- `EVALUATION_IMPLEMENTATION_COMPLETE.md`: Evaluation integration details

## Important Notes

- Python 3.11+ required
- Rust must be installed for poke-engine compilation
- The engine must be rebuilt when switching between generations
- Protocol parsing in `battle_modifier.py` is generation-aware
- Data mods are applied once at startup based on `--pokemon-format`
- Dynamax and Z-moves are not fully supported yet
