# -*- coding: utf-8 -*-
import requests
import json
import copy
import subprocess
import os


"""
This can be run to create a new_moves.json

There is logic in this file to adjust the PokemonShowdown moves.ts into a JSON file
that this bot can use.

Requires `tsc` and `node` on your system

Versions used when writing this:

➜  ~ node --version
v15.3.0
➜  ~ tsc --version
Version 4.2.3

"""


# Fetch latest version
data = requests.get(
    "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/moves.ts"
).text

# write .ts temp file
with open("/tmp/moves.ts", "w") as f:
    f.write(data)

# compile the .ts file into .js. Requires `tsc` on your system
p = subprocess.Popen(
    ["tsc", "--module", "commonjs", "/tmp/moves.ts"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
stdout = p.stdout.read()
stderr = p.stderr.read()

# exit if stderr is not empty
if stderr:
    print("Something went wrong? stderr: {}".format(stderr))

p.wait()
os.rename("/tmp/moves.js", "/tmp/moves.cjs")

# add a console log to the .cjs file. This will error if the file doesn't exist
with open("/tmp/moves.cjs", "a") as f:
    f.write("console.log(JSON.stringify(exports.Moves));")

# run node on the .cjs file to get the console log we added
# Requires `node` on your system
p = subprocess.Popen(
    ["node", "/tmp/moves.cjs"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
stdout = p.stdout.read()
stderr = p.stderr.read()

if stderr:
    print("Something went wrong? stderr: {}".format(stderr))

# stdout should now be parse-able as JSON
moves_dict = json.loads(stdout)

# make modifications to some values for the bot
# shallow copy the dictionary because we might delete things from it
for k, v in moves_dict.copy().items():
    # the bot doesn't care about Z-Moves or Gmax moves. They're omitted entirely
    if v.get("isZ") or v.get("isMax"):
        del [moves_dict[k]]
        continue

    # the bot needs an `id` attribute
    moves_dict[k]["id"] = k

    # some secondary effects had javascript code for them
    # JSON.stringify would've left only the chance reminaing - remove these
    if v.get("secondary") and len(v["secondary"]) == 1 and "chance" in v["secondary"]:
        v["secondary"] = None

    if "secondary" not in v:
        v["secondary"] = None

    if "sideCondition" in v:
        moves_dict[k]["side_conditions"] = moves_dict[k].pop("sideCondition")

    if "forceSwitch" in v and v["forceSwitch"]:
        moves_dict[k]["flags"]["drag"] = 1
        moves_dict[k].pop("forceSwitch")

    # the bot wants some attributes to be lowercase
    moves_dict[k]["category"] = v["category"].lower()
    moves_dict[k]["type"] = v["type"].lower()

    # the bot doesn't care about some attributes
    # they can be removed from this list if the bot
    # ever wants to start using them
    moves_dict[k].pop("selfSwitch", None)
    moves_dict[k].pop("stallingMove", None)
    moves_dict[k].pop("condition", None)
    moves_dict[k].pop("smartTarget", None)
    moves_dict[k].pop("onDamagePriority", None)
    moves_dict[k].pop("contestType", None)
    moves_dict[k].pop("critRatio", None)
    moves_dict[k].pop("num", None)
    moves_dict[k].pop("zMove", None)
    moves_dict[k].pop("isNonstandard", None)
    moves_dict[k].pop("ignoreImmunity", None)
    moves_dict[k].pop("overrideOffensiveStat", None)
    moves_dict[k].pop("maxMove", None)
    moves_dict[k].pop("slotCondition", None)
    moves_dict[k].pop("noSketch", None)
    moves_dict[k].pop("ignoreDefensive", None)
    moves_dict[k].pop("pseudoWeather", None)
    moves_dict[k].pop("ignoreEvasion", None)
    moves_dict[k].pop("hasCrashDamage", None)
    moves_dict[k].pop("realMove", None)
    moves_dict[k].pop("breaksProtect", None)
    moves_dict[k].pop("secondaries", None)
    moves_dict[k].pop("pressureTarget", None)
    moves_dict[k].pop("mindBlownRecoil", None)
    moves_dict[k].pop("selfdestruct", None)
    moves_dict[k].pop("nonGhostTarget", None)
    moves_dict[k].pop("isFutureMove", None)

    if k.startswith("hiddenpower") and k != "hiddenpower":
        hp_move = moves_dict.pop(k)
        moves_dict[f"{k}60"] = hp_move
        moves_dict[f"{k}60"]["id"] = f"{k}60"
        moves_dict[f"{k}70"] = copy.deepcopy(hp_move)
        moves_dict[f"{k}70"]["id"] = f"{k}70"
        moves_dict[f"{k}70"]["basePower"] = 70


# the bot needs these keys to be named differently
string_json = json.dumps(moves_dict)
string_json = string_json.replace('"atk"', '"attack"')
string_json = string_json.replace('"def"', '"defense"')
string_json = string_json.replace('"spa"', '"special-attack"')
string_json = string_json.replace('"spd"', '"special-defense"')
string_json = string_json.replace('"spe"', '"speed"')
moves_dict = json.loads(string_json)

# custom changes for the bot to work
# some of these are dumb, but here we are

moves_dict["return"]["basePower"] = 102
moves_dict["return102"] = copy.deepcopy(moves_dict["return"])
moves_dict["return102"]["id"] = "return102"

moves_dict["obstruct"]["volatileStatus"] = "protect"

moves_dict["roost"]["volatileStatus"] = "roost"

moves_dict["saltcure"]["volatileStatus"] = "saltcure"
moves_dict["saltcure"]["secondary"] = None

# it is easier for the bot to assume the opponent
# has a 110bp move. It will cut this in half if the
# opponent is assumed to have an item
moves_dict["acrobatics"]["basePower"] = 110

moves_dict["bellydrum"]["boosts"] = {"attack": 6}
moves_dict["bellydrum"]["heal"] = [-1, 2]
moves_dict["bellydrum"]["heal_target"] = "self"

moves_dict["explosion"]["heal"] = [-1, 1]
moves_dict["explosion"]["heal_target"] = "self"

moves_dict["healingwish"]["heal"] = [-1, 1]
moves_dict["healingwish"]["heal_target"] = "self"
moves_dict["healingwish"]["side_conditions"] = "healingwish"

moves_dict["wish"]["side_conditions"] = "wish"

moves_dict["ceaselessedge"]["side_conditions"] = "spikes"
moves_dict["stoneaxe"]["side_conditions"] = "stealthrock"

moves_dict["rest"]["heal"] = [1, 1]
moves_dict["rest"]["heal_target"] = "self"
moves_dict["rest"]["status"] = "slp"

moves_dict["mistyexplosion"]["heal"] = [-1, 1]
moves_dict["mistyexplosion"]["heal_target"] = "self"

moves_dict["selfdestruct"]["heal"] = [-1, 1]
moves_dict["selfdestruct"]["heal_target"] = "self"

moves_dict["finalgambit"]["heal"] = [-1, 1]
moves_dict["finalgambit"]["heal_target"] = "self"

moves_dict["healorder"]["heal_target"] = "self"
moves_dict["slackoff"]["heal_target"] = "self"
moves_dict["softboiled"]["heal_target"] = "self"

moves_dict["junglehealing"]["heal"] = [1, 4]
moves_dict["junglehealing"]["heal_target"] = "self"

moves_dict["lunarblessing"]["heal"] = [1, 4]
moves_dict["lunarblessing"]["heal_target"] = "self"

moves_dict["memento"]["heal"] = [-1, 1]
moves_dict["memento"]["heal_target"] = "self"

moves_dict["milkdrink"]["heal_target"] = "self"

moves_dict["roost"]["heal_target"] = "self"

moves_dict["recover"]["heal_target"] = "self"

moves_dict["mindblown"]["heal"] = [-1, 2]
moves_dict["mindblown"]["heal_target"] = "self"

moves_dict["chloroblast"]["heal"] = [-1, 2]
moves_dict["chloroblast"]["heal_target"] = "self"

moves_dict["synthesis"]["heal"] = [1, 2]
moves_dict["synthesis"]["heal_target"] = "self"

moves_dict["moonlight"]["heal"] = [1, 2]
moves_dict["moonlight"]["heal_target"] = "self"

moves_dict["morningsun"]["heal"] = [1, 2]
moves_dict["morningsun"]["heal_target"] = "self"

moves_dict["explosion"]["heal"] = [-1, 1]

moves_dict["healingwish"]["heal_target"] = "self"

moves_dict["curse"]["boosts"] = {"attack": 1, "defense": 1, "speed": -1}
moves_dict["curse"]["target"] = "normal"

moves_dict["defog"]["boosts"] = {"evasion": -1}

moves_dict["fakeout"]["secondary"]["chance"] = 0

moves_dict["doubleedge"]["recoil"] = [1, 3]
moves_dict["flareblitz"]["recoil"] = [1, 3]
moves_dict["volttackle"]["recoil"] = [1, 3]
moves_dict["woodhammer"]["recoil"] = [1, 3]

moves_dict["leechseed"]["flags"]["powder"] = 1

moves_dict["throatchop"]["volatileStatus"] = "throatchop"

moves_dict["nothing"] = {
    "accuracy": True,
    "basePower": 0,
    "category": "status",
    "flags": {"gravity": 1},
    "id": "nothing",
    "name": "Splash",
    "pp": 40,
    "priority": 0,
    "secondary": None,
    "target": "self",
    "type": "normal",
}

moves_dict["recharge"] = {
    "accuracy": True,
    "basePower": 0,
    "category": "status",
    "flags": {},
    "id": "recharge",
    "name": "Recharge",
    "pp": 40,
    "priority": 0,
    "secondary": None,
    "target": "self",
    "type": "normal",
}

moves_dict["tidyup"]["boosts"] = {"attack": 1, "speed": 1}

del moves_dict["diamondstorm"]["self"]
moves_dict["diamondstorm"]["secondary"] = {
    "chance": 50,
    "self": {"boosts": {"defense": 2}},
}

moves_dict["partingshot"]["boosts"] = {"attack": -1, "special-attack": -1}

del moves_dict["clangoroussoul"]["boosts"]
del moves_dict["filletaway"]["boosts"]

moves_dict["clangingscales"]["self"] = moves_dict["clangingscales"]["selfBoost"]
del moves_dict["clangingscales"]["selfBoost"]

moves_dict["scaleshot"]["self"] = moves_dict["scaleshot"]["selfBoost"]
del moves_dict["scaleshot"]["selfBoost"]

moves_dict["jumpkick"]["crash"] = [1, 2]
moves_dict["highjumpkick"]["crash"] = [1, 2]
moves_dict["axekick"]["crash"] = [1, 2]

with open("data/new_moves.json", "w") as f:
    json.dump(moves_dict, f, indent=4, sort_keys=True)
a = 5
