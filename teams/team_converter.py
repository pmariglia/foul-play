from fp.helpers import normalize_name


def json_to_packed(json_team):
    def from_json(j):
        return "{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{},{},{},{},{},{}".format(
            j["name"],
            j.get("species", ""),
            j["item"],
            j["ability"],
            ",".join(j["moves"]),
            j.get("nature", ""),
            ",".join(str(x) for x in j["evs"].values()),
            j.get("gender", ""),
            ",".join(str(x) for x in j.get("ivs", {}).values()),
            j.get("shiny", ""),
            j.get("level", ""),
            j.get("happiness", ""),
            j.get("pokeball", ""),
            j.get("hiddenpowertype", ""),
            j.get("gigantamax", ""),
            j.get("dynamaxlevel", ""),
            j.get("tera_type", ""),
        )

    packed_team_string = "]".join((from_json(p) for p in json_team))
    return packed_team_string


def single_pokemon_export_to_dict(pkmn_export_string):
    def get_species_in_parentheses(s):
        if "(" in s and ")" in s:
            species = s[s.find("(") + 1 : s.find(")")]
            nickname = s.replace(species, "").replace("()", "")
            return species.strip(), nickname.strip()
        return None, None

    pkmn_dict = {
        "name": "",
        "species": "",
        "level": "",
        "tera_type": "",
        "gender": "",
        "item": "",
        "ability": "",
        "moves": [],
        "shiny": "",
        "nature": "",
        "ivs": {
            "hp": "",
            "atk": "",
            "def": "",
            "spa": "",
            "spd": "",
            "spe": "",
        },
        "evs": {
            "hp": "",
            "atk": "",
            "def": "",
            "spa": "",
            "spd": "",
            "spe": "",
        },
    }
    pkmn_info = pkmn_export_string.split("\n")
    name = pkmn_info[0].split("@")[0]
    if "(M)" in name:
        pkmn_dict["gender"] = "M"
        name = name.replace("(M)", "")
    if "(F)" in name:
        pkmn_dict["gender"] = "F"
        name = name.replace("(F)", "")
    species, nickname = get_species_in_parentheses(name)
    if species:
        pkmn_dict["species"] = normalize_name(species.strip())
        pkmn_dict["name"] = nickname.strip()
    else:
        pkmn_dict["species"] = normalize_name(name.strip())
    if "@" in pkmn_info[0]:
        pkmn_dict["item"] = normalize_name(pkmn_info[0].split("@")[1])
    for line in map(str.strip, pkmn_info[1:]):
        if line.startswith("Ability: "):
            pkmn_dict["ability"] = normalize_name(line.split("Ability: ")[-1])
        if line == "Shiny: Yes":
            pkmn_dict["shiny"] = "S"
        elif line.startswith("Tera Type: "):
            pkmn_dict["tera_type"] = normalize_name(line.split("Tera Type: ")[-1])
        elif line.startswith("Level: "):
            pkmn_dict["level"] = normalize_name(line.split("Level: ")[-1])
        elif line.startswith("EVs: "):
            evs = line.split("EVs: ")[-1]
            for ev in evs.split("/"):
                ev = ev.strip()
                amount = normalize_name(ev.split(" ")[0])
                stat = normalize_name(ev.split(" ")[1])
                pkmn_dict["evs"][stat] = amount
        elif line.startswith("IVs: "):
            ivs = line.split("IVs: ")[-1]
            for iv in ivs.split("/"):
                iv = iv.strip()
                amount = normalize_name(iv.split(" ")[0])
                stat = normalize_name(iv.split(" ")[1])
                pkmn_dict["ivs"][stat] = amount
        elif line.endswith("Nature"):
            pkmn_dict["nature"] = normalize_name(line.split("Nature")[0])
        elif line.startswith("-"):
            pkmn_dict["moves"].append(normalize_name(line[1:]))
    return pkmn_dict


def export_to_packed(export_string):
    team_dict = list()
    team_members = export_string.split("\n\n")
    for pkmn in filter(None, team_members):
        pkmn_dict = single_pokemon_export_to_dict(pkmn)
        team_dict.append(pkmn_dict)

    return json_to_packed(team_dict)


def export_to_dict(export_string):
    team_dict = list()
    team_members = export_string.split("\n\n")
    for pkmn in filter(None, team_members):
        pkmn_dict = single_pokemon_export_to_dict(pkmn)
        team_dict.append(pkmn_dict)

    return team_dict
