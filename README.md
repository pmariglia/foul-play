# Foul Play ![umbreon](https://play.pokemonshowdown.com/sprites/xyani/umbreon.gif)
A Pokémon battle-bot that can play battles on [Pokemon Showdown](https://pokemonshowdown.com/).

Foul Play can play single battles in all generations
though currently dynamax and z-moves are not supported.

![badge](https://github.com/pmariglia/foul-play/actions/workflows/ci.yml/badge.svg)

## Python version
Requires Python 3.10+.

## Getting Started

### Configuration
Environment variables are used for configuration.
You may either set these in your environment before running,
or populate them in the [env](https://github.com/pmariglia/foul-play/blob/main/env) file.

The configurations available are:

| Config Name             |  Type  |                Required                | Description                                                                                                                                                      |
|-------------------------|:------:|:--------------------------------------:|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **`BATTLE_BOT`**        | string |                  yes                   | The BattleBot to use. More on this below in the Battle Bots section                                                                                              |
| **`WEBSOCKET_URI`**     | string |                  yes                   | The address to use to connect to the Pokemon Showdown websocket                                                                                                  |
| **`PS_USERNAME`**       | string |                  yes                   | Pokemon Showdown username                                                                                                                                        |
| **`PS_PASSWORD`**       | string |                  yes                   | Pokemon Showdown password                                                                                                                                        |
| **`PS_AVATAR`**         | string |                  yes                   | Pokemon Showdown avatar. e.g. `lucas`, `dawn`, etc.                                                                                                              |
| **`BOT_MODE`**          | string |                  yes                   | What to do after logging-in. Options are: <br/>- `CHALLENGE_USER`<br/>- `SEARCH_LADDER` <br/>- `ACCEPT_CHALLENGE`                                                |
| **`POKEMON_MODE`**      | string |                  yes                   | The type of game this bot will play: `gen8ou`, `gen7randombattle`, etc.                                                                                          |
| **`USER_TO_CHALLENGE`** | string | only if `BOT_MODE` is `CHALLENGE_USER` | If `BOT_MODE` is `CHALLENGE_USER`, this is the name of the user to challenge                                                                                     |
| **`SMOGON_STATS`**      | string |                   no                   | If set, use the smogon stats for this format instead of the ones defined by `POKEMON_MODE`. This is useful when `POKEMON_MODE` does not have a smogon stats page |
| **`RUN_COUNT`**         |  int   |                   no                   | The number of games to play before quitting                                                                                                                      |
| **`SEARCH_TIME_MS`**    |  int   |                   no                   | The amount of time to spend looking for a move in milliseconds. This applies to monte-carlo search, as well as expectiminimax when using iterative-deepening     |
| **`TEAM_NAME`**         | string |                   no                   | The name of the file that contains the team you want to use. More on this below in the Specifying Teams section.                                                 |
| **`ROOM_NAME`**         | string |                   no                   | If `BOT_MODE` is `ACCEPT_CHALLENGE`, join this chatroom while waiting for a challenge.                                                                           |
| **`SAVE_REPLAY`**       |  str   |                   no                   | Whether or not to save replays of the battles (`Always` / `Never` / `OnLoss`)                                                                                    |
| **`LOG_LEVEL`**         | string |                   no                   | The Python logging level for stdout logs (`DEBUG`, `INFO`, etc.)                                                                                                 |
| **`LOG_TO_FILE`**       | string |                   no                   | If `True` then `DEBUG` logs are written to a file in `./logs` regardless of what `LOG_LEVEL` is set to. A new file is created per battle                         |

### Running Locally

**1. Clone**

Clone the repository with `git clone https://github.com/pmariglia/foul-play.git`

**2. Install Requirements**

Install the requirements with `pip install -r requirements.txt`.

Note: Requires Rust to be installed on your machine to build the engine.

**3. Configure your [env](https://github.com/pmariglia/foul-play/blob/main/env) file**

Here is a sample:
```
BATTLE_BOT=safest
WEBSOCKET_URI=wss://sim3.psim.us/showdown/websocket
PS_USERNAME=MyUsername
PS_PASSWORD=MyPassword
BOT_MODE=SEARCH_LADDER
POKEMON_MODE=gen7randombattle
RUN_COUNT=1
```

**4. Run**

Run with `python run.py`

### Running with Docker

**1. Clone the repository**

`git clone https://github.com/pmariglia/foul-play.git`

**2. Build the Docker image**

Use the `Makefile` to build a Docker image
```shell
make docker
```

or for a specific generation:
```shell
make docker GEN=gen4
```

**3. Run with an environment variable file**
`docker run --env-file env foul-play:latest`

## Engine

This project uses [poke-engine](https://github.com/pmariglia/poke-engine) to search through battles.
See [the engine docs](https://poke-engine.readthedocs.io/en/latest/) for more information.

The engine must be built from source if installing locally so you must have rust installed on your machine.

### Re-Installing the Engine

It is common to want to re-install the engine for different generations of Pokémon.

`pip` will used cached .whl artifacts when installing packages
and cannot detect the `--config-settings` flag that was used to build the engine.

The following command will ensure that the engine is re-installed properly:
```shell
pip uninstall -y poke-engine && pip install -v --force-reinstall --no-cache-dir poke-engine --config-settings="build-args=--features poke-engine/<GENERATION> --no-default-features"
```

Or using the Makefile:
```shell
make poke_engine GEN=<generation>
```

For example, to re-install the engine for generation 4:
```shell
make poke_engine GEN=gen4
```

## Battle Bots

The Battle Bot decides which algorithm to use to pick a move

### Monte-Carlo Tree Search
use `BATTLE_BOT=mcts`

Uses poke-engine to perform a
[monte-carlo tree search](https://en.wikipedia.org/wiki/Monte_Carlo_tree_search) to determine the best move to make.

### Expectiminimax
use `BATTLE_BOT=minimax`

Uses poke-engine to perform an
[expectiminimax search](https://en.wikipedia.org/wiki/Expectiminimax) and picks the move that minimizes the loss
for the turn.

## Specifying Teams
You can specify teams by setting the `TEAM_NAME` environment variable.
Examples can be found in `teams/teams/`.

Passing in a directory will cause a random team to be selected from that directory.

The path specified should be relative to `teams/teams/`.

#### Examples

Specify a file:
```
TEAM_NAME=gen8/ou/clef_sand
```

Specify a directory:
```
TEAM_NAME=gen8/ou
```
