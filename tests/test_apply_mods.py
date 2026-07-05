import copy

import pytest

from fp import constants
from fp.data import all_move_json
from fp.data import pokedex
from fp.battle.helpers import (
    DAMAGE_MULTIPICATION_ARRAY,
    POKEMON_TYPE_INDICES,
)
from fp.data.mods.apply_mods import apply_mods
from fp.format_spec import FormatSpec


class TestApplyMods:
    @pytest.fixture(autouse=True)
    def _setup(self):
        # apply_mods mutates these module-level objects in place and they are
        # shared across the whole test session. snapshot them here and restore
        # them in place on teardown so identity is preserved for the other
        # modules holding references to them
        self.saved_moves = copy.deepcopy(all_move_json)
        self.saved_pokedex = copy.deepcopy(pokedex)
        self.saved_damage_multiplication_array = copy.deepcopy(
            DAMAGE_MULTIPICATION_ARRAY
        )
        yield
        all_move_json.clear()
        all_move_json.update(self.saved_moves)
        pokedex.clear()
        pokedex.update(self.saved_pokedex)
        DAMAGE_MULTIPICATION_ARRAY[:] = self.saved_damage_multiplication_array

    def test_gen3_undoes_physical_special_split(self):
        apply_mods(FormatSpec.from_format_string("gen3ou"))

        # damaging moves get their category from their type in gen3
        assert "special" == all_move_json["firepunch"][constants.CATEGORY]
        assert "physical" == all_move_json["swift"][constants.CATEGORY]
        assert "physical" == all_move_json["tackle"][constants.CATEGORY]

    def test_gen3_steel_resists_ghost_and_dark(self):
        apply_mods(FormatSpec.from_format_string("gen3ou"))

        ghost = POKEMON_TYPE_INDICES["ghost"]
        dark = POKEMON_TYPE_INDICES["dark"]
        steel = POKEMON_TYPE_INDICES["steel"]
        assert 0.5 == DAMAGE_MULTIPICATION_ARRAY[ghost][steel]
        assert 0.5 == DAMAGE_MULTIPICATION_ARRAY[dark][steel]

    def test_gen3_applies_pokedex_mods_from_later_gens(self):
        apply_mods(FormatSpec.from_format_string("gen3ou"))

        # gen3 has no pokedex mods of its own so the gen4 chain is used:
        # rotomheat comes from gen4_pokedex_mods.json, clefable from gen5's
        assert ["electric", "ghost"] == pokedex["rotomheat"][constants.TYPES]
        assert ["normal"] == pokedex["clefable"][constants.TYPES]

    def test_gen1_type_chart_changes(self):
        apply_mods(FormatSpec.from_format_string("gen1ou"))

        ice = POKEMON_TYPE_INDICES["ice"]
        fire = POKEMON_TYPE_INDICES["fire"]
        ghost = POKEMON_TYPE_INDICES["ghost"]
        psychic = POKEMON_TYPE_INDICES["psychic"]
        bug = POKEMON_TYPE_INDICES["bug"]
        poison = POKEMON_TYPE_INDICES["poison"]
        assert 1 == DAMAGE_MULTIPICATION_ARRAY[ice][fire]
        assert 0 == DAMAGE_MULTIPICATION_ARRAY[ghost][psychic]
        assert 2 == DAMAGE_MULTIPICATION_ARRAY[poison][bug]
        assert 2 == DAMAGE_MULTIPICATION_ARRAY[bug][poison]

    def test_gen1_applies_pokedex_mods_on_top_of_gen2_and_gen3_chain(self):
        apply_mods(FormatSpec.from_format_string("gen1ou"))

        # gen1 special stat: alakazam's special-defense becomes its special
        assert (
            135 == pokedex["alakazam"][constants.BASESTATS][constants.SPECIAL_DEFENSE]
        )

        # the gen2/gen3 mods are applied first
        assert "special" == all_move_json["firepunch"][constants.CATEGORY]
        ghost = POKEMON_TYPE_INDICES["ghost"]
        steel = POKEMON_TYPE_INDICES["steel"]
        assert 0.5 == DAMAGE_MULTIPICATION_ARRAY[ghost][steel]

    def test_gen4_move_mods_keep_physical_special_split(self):
        apply_mods(FormatSpec.from_format_string("gen4ou"))

        # drainpunch is modded by gen4_move_mods.json
        assert 60 == all_move_json["drainpunch"]["basePower"]
        # the physical/special split exists in gen4
        assert "physical" == all_move_json["firepunch"][constants.CATEGORY]

    def test_gen5_move_mods_layered_with_later_gen_mods(self):
        apply_mods(FormatSpec.from_format_string("gen5ou"))

        # gen5_move_mods.json is applied last so its value wins
        assert 20 == all_move_json["knockoff"]["basePower"]
        # mods are applied in reverse from gen8 down to gen5, so a
        # gen8-modded value is also present when applying gen5 mods
        assert 80 == all_move_json["wickedblow"]["basePower"]
        # gen5 pokedex mods are applied as well
        assert ["normal"] == pokedex["clefable"][constants.TYPES]

    def test_gen9champions_caps_pp_at_20_and_applies_move_mods(self):
        apply_mods(FormatSpec.from_format_string("gen9championscup"))

        assert 20 == all_move_json["tackle"][constants.PP]
        assert all(mv[constants.PP] <= 20 for mv in all_move_json.values())

        # values from gen9champions_move_mods.json
        assert 90 == all_move_json["anchorshot"]["basePower"]
        assert 5 == all_move_json["banefulbunker"][constants.PP]

    def test_gen9_is_a_noop(self):
        apply_mods(FormatSpec.from_format_string("gen9ou"))

        assert self.saved_moves == all_move_json
        assert self.saved_pokedex == pokedex
        assert self.saved_damage_multiplication_array == DAMAGE_MULTIPICATION_ARRAY

    def test_shared_data_restored_after_previous_tests(self):
        # this test is defined last so it runs after the tests above have
        # mutated and restored the shared data
        assert "physical" == all_move_json["firepunch"][constants.CATEGORY]
        assert 65 == all_move_json["knockoff"]["basePower"]
        assert 35 == all_move_json["tackle"][constants.PP]
        assert ["fairy"] == pokedex["clefable"][constants.TYPES]
        assert 95 == pokedex["alakazam"][constants.BASESTATS][constants.SPECIAL_DEFENSE]

        ghost = POKEMON_TYPE_INDICES["ghost"]
        steel = POKEMON_TYPE_INDICES["steel"]
        ice = POKEMON_TYPE_INDICES["ice"]
        fire = POKEMON_TYPE_INDICES["fire"]
        assert 1 == DAMAGE_MULTIPICATION_ARRAY[ghost][steel]
        assert 0.5 == DAMAGE_MULTIPICATION_ARRAY[ice][fire]
