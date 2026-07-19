import pytest

from fp.config import FoulPlayConfig


# generation lookups are strict: an unknown generation raises rather than
# falling back. tests get an explicit default format here and may override
# it (or battle.generation / battle.pokemon_format) for gen-specific cases
@pytest.fixture(autouse=True)
def default_pokemon_format():
    FoulPlayConfig.pokemon_format = "gen9ou"
    yield
    FoulPlayConfig.pokemon_format = ""
