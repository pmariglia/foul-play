import unittest

from teams.team_converter import single_pokemon_export_to_dict


class TestSinglePokemonExportToDict(unittest.TestCase):
    def setUp(self):
        self.expected_pkmn_dict = {
            "name": "",
            "species": "",
            "level": "",
            "gender": "",
            "item": "",
            "ability": "",
            "moves": [],
            "nature": "",
            "shiny": "",
            "tera_type": "",
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

    def test_pokemon_with_item(self):
        export_string = "Tyranitar @ Leftovers"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["item"] = "leftovers"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_pokemon_with_level(self):
        export_string = "Tyranitar\n" "Level: 5  "

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["level"] = "5"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_pkmn_with_space_in_name(self):
        export_string = "Mr. Mime"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "mrmime"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_pkmn_with_space_in_name_with_gender(self):
        export_string = "Mr. Mime (M)"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "mrmime"
        self.expected_pkmn_dict["gender"] = "M"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_pkmn_with_space_in_name_with_gender_and_item(self):
        export_string = "Mr. Mime (M) @ Leftovers"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "mrmime"
        self.expected_pkmn_dict["gender"] = "M"
        self.expected_pkmn_dict["item"] = "leftovers"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_pokemon_without_item(self):
        export_string = "Tyranitar"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_gendered_pokemon_with_item(self):
        export_string = "Tyranitar (M) @ Leftovers"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["item"] = "leftovers"
        self.expected_pkmn_dict["gender"] = "M"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_gendered_pokemon_without_item(self):
        export_string = "Tyranitar (M)"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["gender"] = "M"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_pkmn_with_evs(self):
        export_string = "Tyranitar\n" "EVs: 1 Atk / 2 Def / 3 Spa / 4 SpD / 5 Spe"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["evs"]["atk"] = "1"
        self.expected_pkmn_dict["evs"]["def"] = "2"
        self.expected_pkmn_dict["evs"]["spa"] = "3"
        self.expected_pkmn_dict["evs"]["spd"] = "4"
        self.expected_pkmn_dict["evs"]["spe"] = "5"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_pkmn_with_ability(self):
        export_string = "Tyranitar\n" "Ability: Sand Stream"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["ability"] = "sandstream"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_pkmn_with_nature(self):
        export_string = "Tyranitar\n" "Adamant Nature"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["nature"] = "adamant"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_pkmn_with_moves(self):
        export_string = "Tyranitar\n" "- Crunch\n" "- Stone Edge\n" "- Earthquake"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["moves"] = [
            "crunch",
            "stoneedge",
            "earthquake",
        ]

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_pkmn_with_moves_in_random_places(self):
        export_string = (
            "Tyranitar\n"
            "- Crunch\n"
            "Ability: Sand Stream\n"
            "- Stone Edge\n"
            "Adamant Nature\n"
            "- Earthquake"
        )

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["ability"] = "sandstream"
        self.expected_pkmn_dict["nature"] = "adamant"
        self.expected_pkmn_dict["moves"] = [
            "crunch",
            "stoneedge",
            "earthquake",
        ]

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_deals_with_nicknames(self):
        export_string = "Ty Ty (Tyranitar)\n"

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["name"] = "Ty Ty"
        self.expected_pkmn_dict["species"] = "tyranitar"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_deals_with_space_after_line(self):
        export_string = (
            "Tyranitar\n" "Adamant Nature "  # intentional whitespace after "Nature"
        )

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["nature"] = "adamant"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_deals_with_newline_after_line(self):
        export_string = (
            "Tyranitar\n" "Adamant Nature\n"  # intentional newline after "Nature"
        )

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["nature"] = "adamant"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_deals_with_carriagereturn_after_line(self):
        export_string = "Tyranitar\n" "Adamant Nature \r "

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["nature"] = "adamant"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)

    def test_parses_terra_type(self):
        export_string = "Tyranitar\n" "Tera Type: Water \r "

        pkmn_dict = single_pokemon_export_to_dict(export_string)
        self.expected_pkmn_dict["species"] = "tyranitar"
        self.expected_pkmn_dict["tera_type"] = "water"

        self.assertEqual(self.expected_pkmn_dict, pkmn_dict)
