"""
What foul-play is known to ignore

Anything PS sends that is not covered here (or parsed by `fp.battle.protocol_messages`)
is reported as drift. When a new message type or keyword argument is investigated and
found to be harmless, add it here with a comment saying why.
"""

# message types that do not affect anything foul-play tracks
IGNORED_MESSAGE_TYPES = {
    "",  # `|` spacer lines between turns (inference uses these as separators)
    # room / server framing
    "init",
    "title",
    "j",
    "J",
    "l",
    "L",
    "n",
    "N",
    "c",
    "c:",
    "chat",
    "t:",
    "raw",
    "html",
    "uhtml",
    "uhtmlchange",
    "message",
    "debug",
    "error",  # checked separately: see detectors.py
    "bigerror",
    "deinit",
    "expire",
    # battle metadata
    "gametype",
    "gen",
    "tier",
    "rule",
    "rated",
    "seed",
    "teamsize",
    "teampreview",
    "updatepoke",
    "showteam",
    "win",
    "tie",
    # cosmetic / informational
    "-message",
    "-hint",
    "-hitcount",
    "-notarget",
    "-nothing",
    "-center",
    "-combine",
    "-waiting",
    "-ohko",
    "-fieldactivate",
    "-block",
    "-zbroken",
    "-candynamax",
    # followed by a `detailschange` that carries the state change
    "-primal",
    "-burst",
}

# message types that DO change state foul-play tracks, but are not handled yet.
# reported as known gaps rather than drift
KNOWN_UNHANDLED_MESSAGE_TYPES = {
    "-copyboost": "psych up copies boosts",
    "-swapboost": "heart swap / power swap / guard swap swap boosts",
    "-invertboost": "topsy-turvy inverts boosts",
    "swap": "doubles only: allies swap positions",
}

# keyword arguments (`[key] value`) that PS is known to send
KNOWN_KWARGS = {
    "from",
    "of",
    "still",
    "silent",
    "weaken",
    "anim",
    "miss",
    "move",
    "upkeep",
    "persistent",
    "partiallytrapped",
    "ohko",
    "zeffect",
    "msg",
    "damage",
    "weak",
    "notarget",
    "interrupt",
    "source",
    "eat",
    "consumed",
    "wisher",
    "spread",
    "fromitem",
    "fatigue",
    "block",
    "unidentified",
    "premajor",
    "heavy",
    "forme",
    "fail",
    "broken",
    "ability",
    "identify",
}

# message types whose payload is free text and may legitimately contain `|` or `[`
FREE_TEXT_MESSAGE_TYPES = {
    "request",
    "inactive",
    "inactiveoff",
    "title",
    "raw",
    "html",
    "uhtml",
    "uhtmlchange",
    "message",
    "-message",
    "-hint",
    "c",
    "c:",
    "chat",
    "error",
    "bigerror",
    "debug",
    "rule",
    "tier",
}
