# -*- coding: utf-8 -*-
import requests
import re
import json
from fp.helpers import normalize_name

# Fetch latest version
data = requests.get(
    "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/pokedex.ts"
).text

# get rid of beginning Typescript object definitions
data = data.split("= {")
assert len(data) == 2, f"expecting data to have length=2: {[i[:50] for i in data]}"
data = "{" + data[1]

# Get rid of tabs
data = data.replace("\t", " ")

# Remove comments
data = re.sub(r" +//.+", "", data)  # end-of-line comments
data = re.sub(r"\/\*[\s\S]*?\*\/", "", data)  # multi-line comments

# double newlines are unnecessary
while "\n\n" in data:
    data = data.replace("\n\n", "\n")

# get rid of commas on the final attribute of objects. These aren't valid JSON
data = re.sub(r",\n( *)([\}\]])", r"\n\1\2", data)

# add double-quotes to keys that do not have them
data = re.sub(r"([\w\d]+): ", r'"\1": ', data)

# Correct double-quoted text inside double-quoted text
data = re.sub(r': ""(.*)":(.*)",', r': "\1:\2",', data)

# remove semicolon at end of file
data = data.replace("};", "}")

data = re.sub(r"'([^'\n]*)'", r'"\1"', data)

# should be parseable as JSON now
data_json = json.loads(data)
data_keys = list(data_json.keys())

# some custom changes for this project
for k in data_keys:
    v = data_json[k]
    if v.get("isCosmeticForme"):
        del data_json[k]
    else:
        v["baseStats"] = {
            "hp": v["baseStats"]["hp"],
            "attack": v["baseStats"]["atk"],
            "defense": v["baseStats"]["def"],
            "special-attack": v["baseStats"]["spa"],
            "special-defense": v["baseStats"]["spd"],
            "speed": v["baseStats"]["spe"],
        }
        v["types"] = [i.lower() for i in v["types"]]
        v["name"] = v["name"].lower()

# re-create the dictionary in order of pokedex numbers
# put negative numbers at the end
new_dict = {}
sorted_dex = sorted(data_json.items(), key=lambda x: x[1]["num"])
negative_nums = [i for i in sorted_dex if i[1]["num"] <= 0]
sorted_dex = [i for i in sorted_dex if i[1]["num"] > 0]
for k, v in sorted_dex:
    new_dict[k] = v
    if v.get("cosmeticFormes"):
        for forme in v["cosmeticFormes"]:
            new_dict[normalize_name(forme)] = v

with open("pokedex_new.json", "w") as f:
    json.dump(new_dict, f, indent=4)
