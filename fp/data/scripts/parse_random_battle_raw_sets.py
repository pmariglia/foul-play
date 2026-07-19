"""
Parses a text file with lines containing the format:
    pkmn_name|level|move1|move2|move3|move4|ability|item

Creates a JSON file with the data arranged in a way that the bot can use to understand
This was made for the purposes of random battles
"""

import json
from copy import deepcopy
from fp import constants
from fp.battle.helpers import normalize_name

fp = "../../sets.txt"
pokedex_path = "../pokedex.json"


all_pokemon_dict = dict()


def add_thing_to_dict_or_increment(d, second_key, thing):
    if thing in d[second_key]:
        d[second_key][thing] += 1
    else:
        d[second_key][thing] = 1


with open(pokedex_path, "r") as f:
    pokedex = json.load(f)


with open(fp, "r") as f:
    lines = f.readlines()

for line in lines:
    split_lines = line.strip().split("|")
    if len(split_lines) != 8:
        continue
    pkmn = split_lines[0]
    level = int(split_lines[1])
    if pkmn in ["unown", "ditto"]:
        moves = [split_lines[2]]
        ability = split_lines[3]
        item = split_lines[4]
    else:
        moves = split_lines[2:6]
        ability = split_lines[6]
        item = split_lines[7]

    if item.endswith("ite") and item != "eviolite":
        pkmn = pkmn + "mega"
        ability = normalize_name(pokedex[pkmn]["most_likely_ability"])
    elif item.endswith("itex"):
        pkmn = pkmn + "megax"
        ability = normalize_name(pokedex[pkmn]["most_likely_ability"])
    elif item.endswith("itey"):
        pkmn = pkmn + "megay"
        ability = normalize_name(pokedex[pkmn]["most_likely_ability"])

    identifier = "{}".format(pkmn)
    if identifier in all_pokemon_dict:
        all_pokemon_dict[identifier][constants.COUNT] += 1
    else:
        all_pokemon_dict[identifier] = {
            constants.SETS: dict(),
            constants.MOVES: dict(),
            constants.ABILITIES: dict(),
            constants.ITEMS: dict(),
            constants.COUNT: 1,
        }

    this_pkmn_dict = all_pokemon_dict[identifier]
    for i, m in enumerate(moves[:]):
        if m == "return":
            m = "return102"
            moves[i] = "return102"
        add_thing_to_dict_or_increment(this_pkmn_dict, constants.MOVES, m)

    this_set = "|".join(sorted(moves))  # + "|" + ability + "|" + item

    moves_identifier = "|".join(sorted(moves))

    add_thing_to_dict_or_increment(this_pkmn_dict, constants.ABILITIES, ability)
    add_thing_to_dict_or_increment(this_pkmn_dict, constants.ITEMS, item)
    add_thing_to_dict_or_increment(this_pkmn_dict, constants.SETS, this_set)


# change raw numbers to percentages
new_json = deepcopy(all_pokemon_dict)
for k, v in all_pokemon_dict.items():
    count = v["count"]
    for move_name, move_count in v["moves"].items():
        new_json[k]["moves"][move_name] = round(move_count * 100 / count, 3)

    for item_name, item_count in v["items"].items():
        new_json[k]["items"][item_name] = round(item_count * 100 / count, 3)

    for ability_name, ability_count in v["abilities"].items():
        new_json[k]["abilities"][ability_name] = round(ability_count * 100 / count, 3)

    for set_name, set_count in v["sets"].items():
        new_json[k]["sets"][set_name] = round(set_count * 100 / count, 3)


# put values in list instead of dict
final_json = deepcopy(new_json)
for k, v in new_json.items():
    final_json[k]["abilities"] = list()
    for name, value in v["abilities"].items():
        final_json[k]["abilities"].append((name, value))
    final_json[k]["items"] = list()
    for name, value in v["items"].items():
        final_json[k]["items"].append((name, value))
    final_json[k]["moves"] = list()
    for name, value in v["moves"].items():
        final_json[k]["moves"].append((name, value))
    final_json[k]["spreads"] = [("serious", "85,85,85,85,85,85", 100.0)]

# dont use ditto sets
final_json.pop("ditto", None)


# dont include pkmn not in pokedex (sometimes the raw file has errors)
for k, v in deepcopy(final_json).items():
    if k not in pokedex:
        final_json.pop(k)


with open("out.json", "w") as f:
    json.dump(final_json, f, indent=4, sort_keys=True)
