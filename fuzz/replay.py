"""
Replay one bot's side of a recorded battle through foul-play, without Pokemon Showdown

    python -m fuzz.replay fuzz/out/<run>/failures/<battle>.json [--side p1] [--pdb]

The artifact is prompted for when it is not given.

The bot runs the same loop as during fuzzing (`fp.run_battle.pokemon_battle`), but it reads
the frames recorded in the artifact instead of talking to PS, and its choices go nowhere.
Because the frames are fixed, the replay is unaffected by changes to PS or to the policy,
so it keeps reproducing a parsing failure while you edit foul-play.
"""

import argparse
import asyncio
import json
import logging
import os
import pdb
import random
import sys
import traceback

import fp.run_battle

from fuzz.detectors import FoulPlayLogCollector, ProtocolObserver
from fuzz.harness import USERNAME, USERNAMES, configure_foulplay, prepare_format
from fuzz.policy import POLICY_RNG


class ReplayFinished(Exception):
    pass


class ReplayClient:
    """Stands in for `fp.websocket_client.PSWebsocketClient`, reading recorded frames"""

    def __init__(self, frames, observer, verbose):
        self.frames = frames
        self.observer = observer
        self.verbose = verbose
        self.index = -1

    @property
    def current_frame(self) -> str | None:
        return self.frames[self.index] if 0 <= self.index < len(self.frames) else None

    async def receive_message(self):
        self.index += 1
        if self.index >= len(self.frames):
            raise ReplayFinished()
        frame = self.frames[self.index]
        if self.verbose:
            print("<<< frame {}\n{}".format(self.index, frame))
        self.observer.observe(frame)
        return frame

    async def send_message(self, room, message_list):
        if self.verbose:
            print(">>> {}".format("|".join(message_list)))

    async def save_replay(self, battle_tag):
        pass

    async def leave_battle(self, battle_tag):
        pass


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "artifact",
        nargs="?",
        help="A failures/*.json or battles/*.json file (prompted for if omitted)",
    )
    parser.add_argument(
        "--side",
        choices=["p1", "p2"],
        default=None,
        help="Which bot to replay (default: the first side that raised, else p1)",
    )
    parser.add_argument(
        "--pdb", action="store_true", help="Open pdb where foul-play raises"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print every frame and choice"
    )
    parser.add_argument("--log-level", default="WARNING", help="foul-play's log level")
    return parser.parse_args(argv)


async def replay(client, artifact, side):
    USERNAME.set(USERNAMES[side])
    # the policy's choices feed foul-play's inference, so use the same RNG as the fuzz run
    POLICY_RNG.set(random.Random("{}-{}-policy".format(artifact["seed"], side)))
    try:
        await fp.run_battle.pokemon_battle(client, artifact["format"], None)
    except ReplayFinished:
        pass


def prompt_for_artifact() -> str:
    while True:
        try:
            path = input("Artifact to replay: ").strip()
        except EOFError:
            sys.exit("No artifact given")
        if not path:
            continue
        path = os.path.expanduser(path)
        if os.path.isfile(path):
            return path
        print("{} is not a file".format(path))


def main(argv=None):
    args = parse_args(argv)
    # keep our output in order with tracebacks and logs on stderr
    sys.stdout.reconfigure(line_buffering=True)
    if args.artifact is None:
        args.artifact = prompt_for_artifact()
    with open(args.artifact) as f:
        artifact = json.load(f)
    side = args.side or next(iter(artifact.get("tracebacks") or {}), "p1")

    logging.basicConfig(level=args.log_level.upper())
    configure_foulplay()
    prepare_format(artifact["format"])
    observer = ProtocolObserver()
    logging.getLogger().addHandler(FoulPlayLogCollector(observer))

    print("Replaying {} {} as {}".format(artifact["format"], artifact["seed"], side))
    if artifact.get("errors"):
        print("Recorded errors: {}".format("; ".join(artifact["errors"])))
    if artifact.get("stop_findings"):
        print("Recorded findings: {}".format("; ".join(artifact["stop_findings"])))

    client = ReplayClient(artifact["frames"][side], observer, args.verbose)
    try:
        asyncio.run(replay(client, artifact, side))
    except Exception:
        traceback.print_exc()
        print(
            "\nfoul-play raised while handling frame {} of {}:\n{}\n".format(
                client.index, len(client.frames), client.current_frame
            )
        )
        if args.pdb:
            pdb.post_mortem(sys.exc_info()[2])
        return 1
    finally:
        findings = [f for f in observer.findings if f.severity != "info"]
        for f in findings:
            print("[{}] {} {}: {}".format(f.severity, f.kind, f.key, f.example[:200]))

    print("Replayed all {} frames without an exception".format(len(client.frames)))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
