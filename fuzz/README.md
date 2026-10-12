# Protocol fuzzing

Detects Pokemon Showdown protocol changes that foul-play's parsing does not understand.

Two copies of foul-play's real battle loop (`fp.run_battle.pokemon_battle`) play each other against
an in-process PS simulator. The websocket is replaced by `FuzzClient` and the search by a random
choice among the options foul-play derives from the request (`fuzz/policy.py`), so a battle takes
well under a second. Every protocol line either bot receives is re-parsed with foul-play's parser
and checked by `fuzz/detectors.py`.

## Setup

```bash
# a pokemon-showdown checkout, built
git clone https://github.com/smogon/pokemon-showdown ../pokemon-showdown
(cd ../pokemon-showdown && npm install && node build)
```

## Running

```bash
python -m fuzz.run --ps-dir ../pokemon-showdown --battles 200 --jobs 8 --formats gen9randombattle
python -m fuzz.run --ps-dir ../pokemon-showdown --battles 200 --jobs 8 --formats gen4randombattle,gen4ou
```

Like `fp/main.py`, the fuzzer applies the generation's data mods (`fp/data/mods/apply_mods.py`:
pokedex, move and type chart changes) before the battles. They change foul-play's data for the
whole process, so all the formats of one run must be from the same generation; run each
generation separately. poke-engine is built for one generation too: build it for the generation
being fuzzed (`make poke_engine_local GEN=gen4` from the foul-play root, which builds
`../poke-engine`), or damage calcs use the wrong generation's mechanics.

To find problems one at a time, run until the first battle with a finding instead of a fixed
number of battles:

```bash
python -m fuzz.run --ps-dir ../pokemon-showdown --jobs 8 --formats gen9randombattle --until-finding
python -m fuzz.run ... --until-finding --time-limit 600           # give up after 10 minutes
python -m fuzz.run ... --until-finding --stop-on error,drift       # ignore foul-play's log warnings
```

`--stop-on` takes the severities that end the run (default `error,drift,info`; `new-signature`
is only known once the run ends, so it cannot stop one). The battle that stopped the run always has
its artifact written to `failures/`, and the summary prints the `fuzz.replay` commands for it. With
`--jobs`, the other workers finish the battle they are in and stop. `--battles` still caps the run,
and `--time-limit` also works without `--until-finding`. A given `--seed` plays the same battles
either way.

The exit code is non-zero when any `error`, `drift` or `new-signature` finding is reported, or
when `--until-finding` stopped on a finding.
`fuzz/out/<timestamp>-<seed>/report.json` holds every finding, per-battle results, message counts
and signatures. Battles with errors also write `failures/<format>-<seed>.json` containing the
tracebacks, every frame each bot received, every message each bot sent, and the PS input log.

A battle is fully determined by its seed (teams, PS RNG and both bots' choices), so a failure can
be re-run on its own, e.g. against a different PS commit:

```bash
python -m fuzz.run --ps-dir ../pokemon-showdown --formats gen7randombattle --battle-seed gen5,01215bcfec00cf47
```

## Debugging a failure

Every battle with an `error` writes `failures/<format>-<seed>.json`. Pass `--save-artifacts` to
write one for every battle (into `battles/`), e.g. when re-running a `drift` finding's seed.

Replay one bot's side of it through foul-play, without PS:

```bash
python -m fuzz.replay fuzz/out/<run>/failures/<format>-<seed>.json             # side that raised
python -m fuzz.replay <artifact> --side p2 --verbose --log-level DEBUG         # print every frame/choice
python -m fuzz.replay <artifact> --pdb                                         # post-mortem at the exception
```

The replay feeds the recorded frames to `fp.run_battle.pokemon_battle`, so it reproduces the
failure while you change foul-play, and `breakpoint()` anywhere in `fp/` works. It reports the
index and contents of the frame being handled when foul-play raised, plus any detector findings.

To re-run the whole battle against live PS instead (e.g. after updating PS), use the seed from a
finding's `first_battle` (`<format>:<seed>`) with `--battle-seed`.

## Findings

| severity        | meaning                                                                                                           |
|-----------------|-------------------------------------------------------------------------------------------------------------------|
| `error`         | foul-play raised, stalled, sent a choice PS rejected (`[Invalid choice]`, stale rqid), or a line failed to parse  |
| `drift`         | a message type, `[kwarg]` or `prefix: Effect` that foul-play does not parse and `fuzz/allowlist.py` does not list |
| `new-signature` | a line shape (`type/positional-arity/kwargs`) or request JSON key path missing from `--baseline`                  |
| `known-gap`     | a state-changing message foul-play is known to ignore (`KNOWN_UNHANDLED_MESSAGE_TYPES`)                           |
| `info`          | foul-play logged a warning, grouped by call site                                                                  |

When a `drift` finding turns out to be harmless, add it to `fuzz/allowlist.py` with a comment.

## Detecting upstream drift with a baseline

Signatures only mean something relative to a known-good PS commit:

```bash
# once, against a PS commit foul-play is known to work with. Repeat with more seeds until
# the number of signatures stops growing
(cd ../pokemon-showdown && git checkout <known-good> && node build)
python -m fuzz.run --battles 2000 --jobs 8 --formats ... --baseline fuzz/baseline.json --update-baseline

# then, against master
(cd ../pokemon-showdown && git checkout master && git pull && node build)
python -m fuzz.run --battles 2000 --jobs 8 --formats ... --baseline fuzz/baseline.json
```

A `new-signature` against master that never appears against the known-good commit when run with
the same seeds is protocol drift.

## Triaging a report

A run leaves a `report.json` behind. For each failing finding you want to answer two questions:
what went wrong, and where the bug lives. It is usually in foul-play's protocol handling, sometimes
in foul-play's other logic, and occasionally in the fuzzer itself.

### Before you start

- Use `venv/bin/python` from the foul-play root for everything. That venv has a local poke-engine
  build (`make poke_engine_local GEN=terastallization` from the foul-play root, which builds
  `../poke-engine`) rather than the version pinned in `requirements.txt`.
- `fuzz.run` needs a built Pokemon Showdown checkout at `../pokemon-showdown` (or `$PS_DIR`).
  `fuzz.replay` does not need PS at all.
- poke-engine's source is in `../poke-engine`, if you need to check how the search treats something.
- foul-play no longer supports gen1, so skip gen1 findings and leave gen1 out of runs.
- Run the tests with `venv/bin/python -m pytest tests -q`, and lint with `venv/bin/ruff format`
  and `venv/bin/ruff check`.

### How the fuzzer fits together

| file                | role                                                                                           |
|---------------------|------------------------------------------------------------------------------------------------|
| `fuzz/run.py`       | the command line: runs the battles (in parallel with `--jobs`), collects findings, writes `report.json` |
| `fuzz/harness.py`   | plays one battle: two foul-play bots in one process, with `FuzzClient` standing in for the websocket; writes the artifacts |
| `fuzz/ps_driver.js` | a small Node process that runs PS's `sim.Battle` and frames its output the way `server/room-battle.ts` does |
| `fuzz/policy.py`    | picks a random move instead of running the search (`fp.modes.base.async_pick_move`)            |
| `fuzz/detectors.py` | checks every line and request the bots receive (`ProtocolObserver`) and collects foul-play's log warnings |
| `fuzz/allowlist.py` | message types and keyword arguments that are known and deliberately ignored                    |
| `fuzz/replay.py`    | plays one side's recorded messages back through foul-play, without PS                          |

Most bugs it finds are in these foul-play modules:

- `fp/battle/protocol_messages.py` turns protocol lines into dataclasses.
- `fp/battle/protocol.py` applies those messages to the battle state (see `MESSAGE_HANDLERS`).
- `fp/battle/request.py` parses the request JSON.
- `fp/battle/state.py` holds `Battle`, `Battler` and `Pokemon`, including `update_from_request`.
- `fp/battle/inference.py` infers speed, items and damage from what happened in a turn.

### Reading `report.json`

- `ps_commit` is the PS commit the run used, marked `(dirty)` if it had local changes.
- `seed` and `formats` are the arguments the run was started with.
- `findings` lists what was found. Each entry has a `severity`, a `kind`, a `key` that groups
  similar findings, a `detail`, an `example` (the protocol line or log message that triggered it),
  a `count`, and `first_battle` (`<format>:<battle seed>`) to reproduce it.
- `battles` has one entry per battle, with its seed, its errors, and `artifact`: the path to its
  recording, written for every battle that had an error.
- `message_counts` and `signatures` feed the baseline comparison and can usually be ignored.

Only `error`, `drift` and `new-signature` findings fail a run; `known-gap` and `info` are there for
context.

### Reading an artifact (`failures/<format>-<seed>.json`)

- `errors` is the same list as in the report, for example
  `bot-exception: KeyError @ fp/battle/inference.py:222`.
- `tracebacks` holds the full Python traceback for each side (`p1`, `p2`) that raised.
- `frames` holds every websocket message each side received, in order. Each one starts with
  `>battle-...`, and requests are the `|request|{json}` lines.
- `sent` holds every message each side sent, such as `/choose move tackle|12`, where `12` is the
  request id it answers.
- `input_log` is PS's own input log, which is enough to replay the battle inside PS.

Artifacts get big. It is easier to load one with a few lines of Python (or `jq`) and print only the
frames around the failure, or the request just before a rejected choice, than to open the whole file.

### Working through a report

1. Group the failing findings by `kind` and pick one battle from each group, either its
   `first_battle` or any `battles[].artifact` with the same error. Different seeds with the same
   error key are usually the same bug.
2. If foul-play raised (`bot-exception`), replay it with `venv/bin/python -m fuzz.replay <artifact>`.
   It shows the traceback and the frame foul-play was handling when it raised. Add `--verbose` to see
   every frame and choice, or `--pdb` to land in a debugger at the exception. To watch a particular
   function, a short script that wraps it to print its arguments and then calls
   `fuzz.replay.main([...])` works well.
3. If PS rejected a choice (`invalid-choice`, usually followed by a `stall`), look at the request
   just before the `|error|` line in that side's `frames`, and at the last few messages in `sent`.
   Work out why the bot sent something the request did not allow.
4. Decide which part is at fault (the pitfalls below cover the usual surprises), fix it there, and
   add a test in `tests/` that fails without the fix.
5. Check the fix three ways: the replay ends with `Replayed all N frames without an exception`; the
   original battle passes against PS
   (`venv/bin/python -m fuzz.run --formats <format> --battle-seed <seed>`); and a wider run with the
   report's `seed` and `formats` shows no new errors.

### What each kind of finding means

| kind                         | meaning                                                                                      |
|------------------------------|----------------------------------------------------------------------------------------------|
| `bot-exception`              | foul-play raised. The key is `ExceptionType @ fp/file.py:line`, the innermost foul-play frame. Replay the artifact |
| `parse-exception`            | `parse_line` in `fp/battle/protocol_messages.py` failed on the `example` line. Fix the parser |
| `invalid-choice`             | PS rejected a choice with `[Invalid choice] ...`. The fuzzer does not retry, so a `stall` follows |
| `stall`                      | a bot waited `--receive-timeout` seconds for a message. Nearly always a side effect of another error in the same battle |
| `battle-timeout`             | the battle took longer than `--battle-timeout`                                               |
| `stale-rqid`                 | the bot answered an older request than the latest one                                        |
| `driver-error`               | `ps_driver.js` or PS itself failed. Check that PS is built and `--ps-dir` points at it       |
| `unrecognized-message`       | (`drift`) a message type foul-play does not parse. Parse it, or add it to `allowlist.py` with a reason |
| `unrecognized-kwarg`         | (`drift`) a `[kwarg]` missing from `KNOWN_KWARGS`                                            |
| `unrecognized-effect-prefix` | (`drift`) a `prefix: Effect` foul-play does not recognise                                    |
| `unhandled-message`          | (`known-gap`) a message listed in `KNOWN_UNHANDLED_MESSAGE_TYPES`                            |
| `unavailable-choice`         | (`info`) `[Unavailable choice]`: PS revealing something the bot could not know, such as a disabled move. Expected now and then |
| `fp-log`                     | foul-play logged a warning (`info`) or an error (`error`). The key is where in `fp/` it was logged |

### Pitfalls

Each of these has led to a wrong diagnosis at least once.

- **The fuzzer can be the bug.** `fuzz/policy.py` picks at random from the options foul-play's
  state allows after `update_from_request`. Some rules live only in poke-engine, though, so the
  real bot would never make a choice the random picker does. For example, foul-play re-enables
  Gigaton Hammer and Blood Moon after PS disables them
  (`Battler._initialize_user_active_from_request`), because poke-engine already refuses to pick
  them twice in a row; the picker has to apply the same rule (`CANNOT_USE_TWICE_IN_A_ROW`). Before
  blaming foul-play for an `invalid-choice`, ask whether the search would really have chosen that.
- **Protocol lines are applied late.** `update_battle` in `fp/battle/protocol.py` holds lines in
  `battle.msg_list` and applies them only when the next `|request|` arrives. So by the time a
  mid-turn message is handled, `battle.request` already shows the end of the turn: a pokemon may have
  fainted, reverted its forme, or been revived. Find the bot's own pokemon in the request by
  nickname, not by species.
- **Some turns span two requests.** Decisions made in the middle of a turn, like a forced switch
  after U-turn or picking a Revival Blessing target, split one turn's lines into two batches.
  Inference that treats a batch as a whole turn, such as `check_speed_ranges`, has to skip these.
- **Some shortcuts are deliberate.** foul-play answers a Revival Blessing target prompt with
  `/choose default` (`fp/run_battle.py`), because neither foul-play nor poke-engine implements the
  mechanic yet.
- **Not every crash is a protocol bug.** A poke-engine panic or a problem in the search is outside
  what this tool is for. Note it, and keep it separate from the protocol fixes.
- **Drift needs a baseline.** A `new-signature` only means something if it does not also show up
  against a known-good PS commit with the same seeds.
