"""
Self-play between two foul-play bots against an in-process Pokemon Showdown simulator

Both bots run foul-play's real battle loop (`fp.run_battle.pokemon_battle`) with the
websocket swapped for `FuzzClient` and the search swapped for `fuzz.policy`.
"""

import asyncio
import json
import os
import random
import traceback
from contextvars import ContextVar
from dataclasses import dataclass, field

import fp.modes.base
import fp.modes.battle_factory
import fp.modes.bss
import fp.modes.random_battle
import fp.modes.standard_battle
import fp.run_battle
from fp.config import FoulPlayConfig, SaveReplay
from fp.format_spec import FormatSpec
from fp.modes import battle_mode

from fuzz.detectors import ProtocolObserver
from fuzz.policy import POLICY_RNG, random_pick_move

DRIVER_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ps_driver.js")
SIDES = ("p1", "p2")
USERNAMES = {"p1": "fuzzbot-p1", "p2": "fuzzbot-p2"}

USERNAME: ContextVar[str] = ContextVar("USERNAME")


class _FuzzConfig(type(FoulPlayConfig)):
    # foul-play reads its own username from the global config. Both bots share a process
    # so each asyncio task gets its own username
    @property
    def username(self):
        return USERNAME.get()


def configure_foulplay():
    FoulPlayConfig.__class__ = _FuzzConfig
    FoulPlayConfig.save_replay = SaveReplay.never
    FoulPlayConfig.log_to_file = False
    FoulPlayConfig.file_log_handler = None
    for module in (
        fp.run_battle,
        fp.modes.base,
        fp.modes.random_battle,
        fp.modes.standard_battle,
        fp.modes.battle_factory,
        fp.modes.bss,
    ):
        if hasattr(module, "async_pick_move"):
            module.async_pick_move = random_pick_move


def prepare_format(pokemon_format: str):
    """Load (and download, if not cached) any set data the battle mode needs"""
    FoulPlayConfig.pokemon_format = pokemon_format
    format_spec = FormatSpec.from_format_string(pokemon_format)
    mode = battle_mode(format_spec.battle_type)
    if not mode.requires_team and hasattr(mode, "datasets"):
        mode.datasets.initialize(format_spec)


def derived_seed(*parts) -> str:
    rng = random.Random("-".join(str(p) for p in parts))
    return "gen5,{:016x}".format(rng.getrandbits(64))


class DriverError(Exception):
    pass


class PSDriver:
    """The Node process running `ps_driver.js`"""

    def __init__(self, ps_dir: str):
        self.ps_dir = ps_dir
        self.proc = None
        self.reader = None
        self.queues: dict[str, asyncio.Queue] = {}
        self.end: asyncio.Future | None = None
        self.input_log: asyncio.Future | None = None
        self.errors: list[dict] = []

    async def start(self):
        self.proc = await asyncio.create_subprocess_exec(
            "node",
            DRIVER_JS,
            self.ps_dir,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            limit=2**26,
        )
        self.reader = asyncio.create_task(self._read())

    async def _read(self):
        while line := await self.proc.stdout.readline():
            try:
                out = json.loads(line)
            except json.JSONDecodeError:
                # something in PS wrote to stdout directly
                self.errors.append(
                    {"message": "non-JSON driver output", "stack": line.decode()}
                )
                continue
            match out["type"]:
                case "frame":
                    self.queues[out["side"]].put_nowait(out["data"])
                case "end":
                    if not self.end.done():
                        self.end.set_result(out)
                case "inputlog":
                    if self.input_log is not None and not self.input_log.done():
                        self.input_log.set_result(out["inputLog"])
                case "driver_error":
                    self.errors.append(out)
        error = DriverError("ps_driver.js exited with {}".format(self.proc.returncode))
        for queue in self.queues.values():
            queue.put_nowait(error)

    async def _send(self, cmd: dict):
        self.proc.stdin.write((json.dumps(cmd) + "\n").encode())
        await self.proc.stdin.drain()

    async def new_battle(self, pokemon_format: str, seed: str, roomid: str):
        self.queues = {side: asyncio.Queue() for side in SIDES}
        self.end = asyncio.get_running_loop().create_future()
        self.errors = []
        await self._send(
            {
                "cmd": "start",
                "format": pokemon_format,
                "seed": seed,
                "roomid": roomid,
                **{
                    side: {"name": USERNAMES[side], "seed": derived_seed(seed, side)}
                    for side in SIDES
                },
            }
        )

    async def choose(self, side: str, choice: str):
        await self._send({"cmd": "choose", "side": side, "choice": choice})

    async def get_input_log(self) -> list[str]:
        self.input_log = asyncio.get_running_loop().create_future()
        await self._send({"cmd": "inputlog"})
        return await asyncio.wait_for(self.input_log, 10)

    async def close(self):
        if self.proc is not None and self.proc.returncode is None:
            self.proc.stdin.close()
            await self.proc.wait()


def _to_choice(message: str) -> str | None:
    """Translate the chat command foul-play sends into a sim choice"""
    for command, choice in (
        ("/choose ", ""),
        ("/switch ", "switch "),
        ("/team ", "team "),
    ):
        if message.startswith(command):
            return choice + message.removeprefix(command)
    return None


class FuzzClient:
    """Stands in for `fp.websocket_client.PSWebsocketClient`"""

    def __init__(self, side, driver, observer, receive_timeout):
        self.side = side
        self.driver = driver
        self.observer = observer
        self.receive_timeout = receive_timeout
        self.frames: list[str] = []
        self.sent: list[str] = []
        self.last_rqid = None

    async def receive_message(self):
        try:
            msg = await asyncio.wait_for(
                self.driver.queues[self.side].get(), self.receive_timeout
            )
        except TimeoutError:
            raise TimeoutError(
                "{} waited {}s for a message from PS".format(
                    self.side, self.receive_timeout
                )
            ) from None
        if isinstance(msg, Exception):
            raise msg
        self.frames.append(msg)
        self.observer.observe(msg)
        for line in msg.split("\n"):
            if line.startswith("|request|{"):
                self.last_rqid = json.loads(line.removeprefix("|request|")).get("rqid")
        return msg

    async def send_message(self, room, message_list):
        self.sent.append("|".join(message_list))
        choice = _to_choice(message_list[0])
        if choice is None:
            return

        # PS ignores choices sent with a stale rqid (server/room-battle.ts)
        rqid = message_list[1] if len(message_list) > 1 else ""
        if rqid and rqid != str(self.last_rqid):
            self.observer.error(
                "stale-rqid",
                "choice sent with a stale rqid",
                "sent rqid {} but the last request was {}".format(rqid, self.last_rqid),
                "|".join(message_list),
            )
        await self.driver.choose(self.side, choice.strip())

    async def save_replay(self, battle_tag):
        pass

    async def leave_battle(self, battle_tag):
        pass


@dataclass
class BattleResult:
    battle_id: str
    pokemon_format: str
    seed: str
    winner: str | None = None
    turns: int | None = None
    errors: list[str] = field(default_factory=list)
    # findings of a `stop_severities` severity that this battle added to, e.g. "info fp-log: battle/inference.py:667"
    stop_findings: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    artifact: str | None = None


def _exception_key(e: BaseException) -> str:
    """`ExceptionType @ fp/file.py:123` for the innermost foul-play frame"""
    tb = traceback.extract_tb(e.__traceback__)
    fp_frames = [f for f in tb if "/fp/" in f.filename]
    frame = (fp_frames or tb or [None])[-1]
    where = (
        "{}:{}".format(frame.filename.split("/fp/")[-1], frame.lineno) if frame else "?"
    )
    return "{} @ fp/{}".format(type(e).__name__, where)


async def run_one_battle(
    driver: PSDriver,
    observer: ProtocolObserver,
    pokemon_format: str,
    seed: str,
    battle_number: int,
    receive_timeout: float,
    battle_timeout: float,
    out_dir: str,
    save_artifact: bool = False,
    stop_severities: frozenset = frozenset(),
) -> BattleResult:
    battle_id = "{}:{}".format(pokemon_format, seed)
    observer.battle_id = battle_id
    counts_before = {f.id: f.count for f in observer.findings}
    result = BattleResult(battle_id, pokemon_format, seed)
    loop = asyncio.get_running_loop()
    started = loop.time()

    FoulPlayConfig.pokemon_format = pokemon_format
    roomid = "battle-{}-{}".format(pokemon_format, battle_number)
    clients = {
        side: FuzzClient(side, driver, observer, receive_timeout) for side in SIDES
    }

    async def play(side):
        USERNAME.set(USERNAMES[side])
        POLICY_RNG.set(random.Random("{}-{}-policy".format(seed, side)))
        return await fp.run_battle.pokemon_battle(clients[side], pokemon_format, None)

    await driver.new_battle(pokemon_format, seed, roomid)
    tasks = {side: asyncio.create_task(play(side)) for side in SIDES}
    done, pending = await asyncio.wait(
        tasks.values(), timeout=battle_timeout, return_when=asyncio.FIRST_EXCEPTION
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

    tracebacks = {}
    for side, task in tasks.items():
        if task not in done:
            if not any(t.exception() for t in done):
                observer.error(
                    "battle-timeout",
                    "battle did not finish",
                    "battle did not finish within {}s".format(battle_timeout),
                )
            continue
        exc = task.exception()
        if exc is None:
            continue
        tracebacks[side] = "".join(traceback.format_exception(exc))
        if isinstance(exc, TimeoutError):
            observer.error("stall", "bot stopped receiving messages", str(exc))
        else:
            observer.error(
                "bot-exception",
                _exception_key(exc),
                "{}: {}".format(type(exc).__name__, exc),
                tracebacks[side],
            )

    for error in driver.errors:
        observer.error("driver-error", error["message"], error.get("stack", ""))

    if not pending:
        # the bots return as soon as they see `|win|`, PS reports the end just after
        try:
            await asyncio.wait_for(asyncio.shield(driver.end), 5)
        except TimeoutError:
            pass

    if driver.end.done():
        result.winner = driver.end.result()["winner"]
        result.turns = driver.end.result()["turns"]
        input_log = driver.end.result()["inputLog"]
    else:
        try:
            input_log = await driver.get_input_log()
        except Exception:
            input_log = []

    added = [f for f in observer.findings if f.count > counts_before.get(f.id, 0)]
    result.errors = sorted(
        "{}: {}".format(*f.id) for f in added if f.severity == "error"
    )
    result.stop_findings = sorted(
        "{} {}: {}".format(f.severity, *f.id)
        for f in added
        if f.severity in stop_severities
    )
    result.duration_s = round(loop.time() - started, 2)

    if result.errors or result.stop_findings or save_artifact:
        # replay these with `python -m fuzz.replay <artifact>`
        artifact_dir = os.path.join(
            out_dir,
            "failures" if result.errors or result.stop_findings else "battles",
        )
        result.artifact = os.path.join(
            artifact_dir, "{}-{}.json".format(pokemon_format, seed.replace(",", "-"))
        )
        os.makedirs(artifact_dir, exist_ok=True)
        with open(result.artifact, "w") as f:
            json.dump(
                {
                    "format": pokemon_format,
                    "seed": seed,
                    "errors": result.errors,
                    "stop_findings": result.stop_findings,
                    "tracebacks": tracebacks,
                    "input_log": input_log,
                    "frames": {side: c.frames for side, c in clients.items()},
                    "sent": {side: c.sent for side, c in clients.items()},
                },
                f,
                indent=2,
            )

    return result
