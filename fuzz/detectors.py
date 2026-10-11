"""
Watches every protocol line delivered to a bot and records anything foul-play may not understand

Each line is parsed independently with foul-play's own parser, so a parse failure is
recorded even when it happens in a message the bot would have discarded.
"""

import json
import logging
from collections import Counter
from dataclasses import asdict, dataclass, fields
from enum import StrEnum

from fp.battle.protocol_messages import (
    Message,
    Unknown,
    parse_line,
)
from fp.battle.protocol_types import (
    KWARG_REGEX,
    Effect,
    EffectKind,
    positional_args,
)

from fuzz.allowlist import (
    FREE_TEXT_MESSAGE_TYPES,
    IGNORED_MESSAGE_TYPES,
    KNOWN_KWARGS,
    KNOWN_UNHANDLED_MESSAGE_TYPES,
)


class Severity(StrEnum):
    # foul-play crashed, stalled, or sent something PS rejected
    ERROR = "error"
    # PS sent something foul-play does not know about
    DRIFT = "drift"
    # a protocol signature that is not in the baseline
    NEW_SIGNATURE = "new-signature"
    # a state-changing message foul-play is already known to ignore
    KNOWN_GAP = "known-gap"
    # foul-play logged a warning
    INFO = "info"


FAILING_SEVERITIES = {Severity.ERROR, Severity.DRIFT, Severity.NEW_SIGNATURE}


@dataclass
class Finding:
    severity: Severity
    kind: str
    key: str
    detail: str
    example: str
    count: int = 0
    first_battle: str = ""

    @property
    def id(self) -> tuple[str, str]:
        return self.kind, self.key


class Findings:
    def __init__(self):
        self.by_id: dict[tuple[str, str], Finding] = {}

    def add(self, finding: Finding, battle_id: str, count: int = 1):
        existing = self.by_id.get(finding.id)
        if existing is None:
            finding.count = 0
            finding.first_battle = finding.first_battle or battle_id
            self.by_id[finding.id] = existing = finding
        existing.count += count

    def merge(self, other: "Findings"):
        for finding in other.by_id.values():
            self.add(
                Finding(**{**asdict(finding), "count": 0}),
                finding.first_battle,
                finding.count,
            )

    def __iter__(self):
        return iter(self.by_id.values())


def _line_signature(msg_type: str, split_msg: list[str]) -> str:
    if msg_type in FREE_TEXT_MESSAGE_TYPES:
        return msg_type
    kwarg_keys = sorted(
        {m.group(1).strip() for m in map(KWARG_REGEX.match, split_msg[2:]) if m}
    )
    return "{}/{}/{}".format(
        msg_type, len(positional_args(split_msg)), ",".join(kwarg_keys)
    )


def request_signatures(value, path="request") -> set[str]:
    """The key paths of a request JSON, with list indices collapsed: request.side.pokemon[].ident"""
    if isinstance(value, dict):
        sigs = {path}
        for k, v in value.items():
            sigs |= request_signatures(v, "{}.{}".format(path, k))
        return sigs
    if isinstance(value, list):
        sigs = {path + "[]"}
        for v in value:
            sigs |= request_signatures(v, path + "[]")
        return sigs
    return {path}


def _effects(msg: Message):
    for f in fields(msg):
        value = getattr(msg, f.name)
        if isinstance(value, Effect):
            yield value
    if msg.kwargs.from_ is not None:
        yield msg.kwargs.from_


class ProtocolObserver:
    def __init__(self):
        self.findings = Findings()
        self.message_counts: Counter[str] = Counter()
        self.signatures: Counter[str] = Counter()
        self.battle_id = ""

    def _find(self, severity, kind, key, detail, example):
        self.findings.add(
            Finding(severity, kind, key, detail, example[:500]), self.battle_id
        )

    def error(self, kind, key, detail, example=""):
        self._find(Severity.ERROR, kind, key, detail, example)

    def observe(self, frame: str):
        for line in frame.split("\n"):
            if line.startswith("|"):
                self.observe_line(line)

    def observe_line(self, line: str):
        split_msg = line.split("|")
        msg_type = split_msg[1].strip()
        self.message_counts[msg_type] += 1
        self.signatures[_line_signature(msg_type, split_msg)] += 1

        try:
            msg = parse_line(line)
        except Exception as e:
            self.error(
                "parse-exception",
                "{}: {}".format(msg_type, type(e).__name__),
                "{}: {}".format(type(e).__name__, e),
                line,
            )
            return

        if msg_type == "request":
            self._observe_request(line)
        elif msg_type == "error":
            self._observe_error(line)

        if msg_type in FREE_TEXT_MESSAGE_TYPES:
            return

        if isinstance(msg, Unknown):
            if msg_type in KNOWN_UNHANDLED_MESSAGE_TYPES:
                self._find(
                    Severity.KNOWN_GAP,
                    "unhandled-message",
                    msg_type,
                    KNOWN_UNHANDLED_MESSAGE_TYPES[msg_type],
                    line,
                )
            elif msg_type not in IGNORED_MESSAGE_TYPES:
                self._find(
                    Severity.DRIFT,
                    "unrecognized-message",
                    msg_type,
                    "message type is not parsed by foul-play nor in fuzz/allowlist.py",
                    line,
                )

        for key in msg.kwargs.values:
            if key not in KNOWN_KWARGS:
                self._find(
                    Severity.DRIFT,
                    "unrecognized-kwarg",
                    "{} [{}]".format(msg_type, key),
                    "keyword argument is not in fuzz/allowlist.py",
                    line,
                )

        for effect in _effects(msg):
            # "move: X", "ability: X", "item: X" and "pokemon: X" are understood.
            # any other "prefix: X" is parsed as a bare condition named "prefix: X"
            if effect.kind == EffectKind.CONDITION and ":" in effect.name:
                self._find(
                    Severity.DRIFT,
                    "unrecognized-effect-prefix",
                    "{} {}:".format(msg_type, effect.name.split(":")[0]),
                    "effect prefix is not one of fp.battle.protocol_types.EFFECT_PREFIXES",
                    line,
                )

    def _observe_request(self, line: str):
        payload = line.split("|", 2)[2]
        if not payload.strip():
            return
        for sig in request_signatures(json.loads(payload)):
            self.signatures[sig] += 1

    def _observe_error(self, line: str):
        text = line.split("|", 2)[2]
        if text.startswith("[Invalid choice]"):
            # strip the specifics so the same problem dedupes across battles
            key = text.split(":")[0]
            self.error("invalid-choice", key, text, line)
        elif text.startswith("[Unavailable choice]"):
            self._find(
                Severity.INFO, "unavailable-choice", text.split(":")[0], text, line
            )


class FoulPlayLogCollector(logging.Handler):
    """Records warnings foul-play logs while handling protocol messages"""

    def __init__(self, observer: ProtocolObserver):
        super().__init__(level=logging.WARNING)
        self.observer = observer

    def emit(self, record: logging.LogRecord):
        if not record.name.startswith("fp"):
            return
        severity = Severity.ERROR if record.levelno >= logging.ERROR else Severity.INFO
        # most foul-play logs are pre-formatted strings: group them by call site
        self.observer._find(
            severity,
            "fp-log",
            "{}:{}".format(record.pathname.split("/fp/")[-1], record.lineno),
            record.levelname,
            record.getMessage(),
        )
