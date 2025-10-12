"""
Markdown formatters for MCP tool responses.

Converts battle state data into human-readable markdown format.
"""

from typing import Optional
from fp.battle import Battle, Pokemon
from fp_mcp.serialization import pokemon_to_dict, battler_to_dict


def format_battle_state_md(
    battle_id: str,
    status: str,
    awaiting_decision: bool,
    battle: Optional[Battle] = None,
    winner: Optional[str] = None,
    error_message: Optional[str] = None,
    error_log: Optional[str] = None,
    message: Optional[str] = None,
) -> str:
    """Format battle state as markdown."""

    lines = [f"# Battle: {battle_id}", ""]

    # Status
    lines.append(f"**Status:** {status}")
    lines.append(f"**Awaiting Decision:** {'Yes' if awaiting_decision else 'No'}")
    lines.append("")

    if error_message:
        lines.append(f"## Error")
        lines.append(f"```\n{error_message}\n```")
        if error_log:
            lines.append("<details><summary>Detailed Error Log</summary>")
            lines.append(f"\n```\n{error_log}\n```\n")
            lines.append("</details>")
        return "\n".join(lines)

    if message:
        lines.append(f"_{message}_")
        return "\n".join(lines)

    if winner:
        lines.append(f"## Winner: {winner}")
        lines.append("")

    # Active battle state
    if battle:
        lines.append(f"## Turn {battle.turn}")
        lines.append("")

        # Your active Pokemon
        if battle.user.active:
            active_dict = pokemon_to_dict(battle.user.active, hide_unknowns=False, compact=False)
            hp_percent = int((active_dict['hp'] / active_dict['max_hp']) * 100) if active_dict['max_hp'] > 0 else 0
            lines.append(f"### Your Active: **{active_dict['name'].title()}** (Lv{active_dict['level']})")
            lines.append(f"- HP: {active_dict['hp']}/{active_dict['max_hp']} ({hp_percent}%)")
            if active_dict['status']:
                lines.append(f"- Status: {active_dict['status'].upper()}")
            lines.append(f"- Type: {'/'.join(t.title() for t in active_dict['types'])}")
            if active_dict.get('ability'):
                lines.append(f"- Ability: {active_dict['ability'].title()}")
            if active_dict.get('item'):
                lines.append(f"- Item: {active_dict['item'].title()}")

            # Stat boosts
            if active_dict.get('boosts'):
                boosts_str = ", ".join(f"{k}:{v:+d}" for k, v in active_dict['boosts'].items() if v != 0)
                if boosts_str:
                    lines.append(f"- Boosts: {boosts_str}")

            lines.append("")
            lines.append("**Moves:**")
            for move in active_dict.get('moves', []):
                move_line = f"- **{move['name']}**"
                if move.get('type'):
                    move_line += f" ({move['type'].title()}"
                    if move.get('category'):
                        move_line += f"/{move['category'].title()}"
                    move_line += ")"
                if move.get('power'):
                    move_line += f" | Power: {move['power']}"
                if move.get('accuracy') is not None and move['accuracy'] not in [True, 100]:
                    move_line += f" | Acc: {move['accuracy']}"
                move_line += f" | PP: {move['pp']}/{move['max_pp']}"
                if move.get('disabled'):
                    move_line += " [DISABLED]"
                lines.append(move_line)
            lines.append("")

        # Your reserves
        if battle.user.reserve:
            alive_reserves = [p for p in battle.user.reserve if p.is_alive]
            if alive_reserves:
                lines.append(f"### Your Reserves ({len(alive_reserves)} alive)")
                for pkmn in alive_reserves:
                    hp_percent = int((pkmn.hp / pkmn.max_hp) * 100) if pkmn.max_hp > 0 else 0
                    status_str = f" ({pkmn.status.upper()})" if pkmn.status else ""
                    lines.append(f"- **{pkmn.name.title()}**: {pkmn.hp}/{pkmn.max_hp} HP ({hp_percent}%){status_str}")
                lines.append("")

        # Opponent's active Pokemon
        if battle.opponent.active:
            opp_dict = pokemon_to_dict(battle.opponent.active, hide_unknowns=True, compact=False)
            hp_percent = int((opp_dict['hp'] / opp_dict['max_hp']) * 100) if opp_dict['max_hp'] > 0 else 0
            lines.append(f"### Opponent's Active: **{opp_dict['name'].title()}** (Lv{opp_dict['level']})")
            lines.append(f"- HP: {opp_dict['hp']}/{opp_dict['max_hp']} ({hp_percent}%)")
            if opp_dict['status']:
                lines.append(f"- Status: {opp_dict['status'].upper()}")
            lines.append(f"- Type: {'/'.join(t.title() for t in opp_dict['types'])}")
            if opp_dict.get('ability') and opp_dict['ability'] != "unknown":
                lines.append(f"- Ability: {opp_dict['ability'].title()}")
            if opp_dict.get('item') and opp_dict['item'] != "unknown":
                lines.append(f"- Item: {opp_dict['item'].title()}")

            # Stat boosts
            if opp_dict.get('boosts'):
                boosts_str = ", ".join(f"{k}:{v:+d}" for k, v in opp_dict['boosts'].items() if v != 0)
                if boosts_str:
                    lines.append(f"- Boosts: {boosts_str}")

            # Known moves
            if opp_dict.get('moves'):
                lines.append("")
                lines.append("**Known Moves:**")
                for move in opp_dict['moves']:
                    move_line = f"- **{move['name']}**"
                    if move.get('type') and move['type'] != "unknown":
                        move_line += f" ({move['type'].title()})"
                    lines.append(move_line)
            lines.append("")

        # Opponent's reserves
        if battle.opponent.reserve:
            alive_reserves = [p for p in battle.opponent.reserve if p.is_alive]
            if alive_reserves:
                lines.append(f"### Opponent's Reserves ({len(alive_reserves)} alive)")
                for pkmn in alive_reserves:
                    if pkmn.hp > 0:
                        hp_percent = int((pkmn.hp / pkmn.max_hp) * 100) if pkmn.max_hp > 0 else 0
                        status_str = f" ({pkmn.status.upper()})" if pkmn.status else ""
                        lines.append(f"- **{pkmn.name.title()}**: {pkmn.hp}/{pkmn.max_hp} HP ({hp_percent}%){status_str}")
                lines.append("")

        # Field conditions
        has_conditions = False
        field_lines = []

        if battle.weather:
            field_lines.append(f"- Weather: **{battle.weather.title()}**")
            has_conditions = True
        if battle.field:
            field_lines.append(f"- Terrain: **{battle.field.title()}**")
            has_conditions = True
        if battle.trick_room:
            field_lines.append(f"- Trick Room: Active")
            has_conditions = True

        if has_conditions:
            lines.append("### Field Conditions")
            lines.extend(field_lines)
            lines.append("")

        # Available actions
        if awaiting_decision and hasattr(battle, 'request_json') and battle.request_json:
            from fp_mcp.serialization import get_detailed_actions
            actions = get_detailed_actions(battle)

            if actions:
                lines.append("### Available Actions")

                moves = [a for a in actions if a['type'] == 'move']
                switches = [a for a in actions if a['type'] == 'switch']

                if moves:
                    lines.append("**Moves:**")
                    for act in moves:
                        line = f"- `{act['action']}`"
                        details = act.get('details', {})
                        if details.get('type'):
                            line += f" ({details['type'].title()}, {details.get('power', 'Status')} power)"
                        lines.append(line)
                    lines.append("")

                if switches:
                    lines.append("**Switches:**")
                    for act in switches:
                        lines.append(f"- `{act['action']}`")
                    lines.append("")

    return "\n".join(lines)


def format_actions_md(battle_id: str, actions: list, constraints: dict) -> str:
    """Format available actions as markdown."""

    lines = [f"# Available Actions - {battle_id}", ""]

    if constraints.get('force_switch'):
        lines.append("**FORCED SWITCH** - Your active Pokemon fainted, you must switch!")
        lines.append("")
    elif constraints.get('trapped'):
        lines.append("**TRAPPED** - You cannot switch!")
        lines.append("")

    # Separate moves and switches
    moves = [a for a in actions if a['type'] == 'move']
    switches = [a for a in actions if a['type'] == 'switch']

    # Moves
    if moves:
        lines.append("## Moves")
        for act in moves:
            line = f"### `{act['action']}`"
            lines.append(line)

            details_list = []
            details = act.get('details', {})
            if details.get('type'):
                details_list.append(f"Type: {details['type'].title()}")
            if details.get('category'):
                details_list.append(f"Category: {details['category'].title()}")
            if details.get('power'):
                details_list.append(f"Power: {details['power']}")
            if details.get('accuracy') is not None and details['accuracy'] not in [True, 100]:
                details_list.append(f"Accuracy: {details['accuracy']}")
            if details.get('pp'):
                details_list.append(f"PP: {details['pp']}")

            if details_list:
                lines.append("- " + " | ".join(details_list))

            if details.get('disabled'):
                lines.append("- **DISABLED**")

            lines.append("")

    # Switches
    if switches:
        lines.append("## Switches")
        for act in switches:
            pkmn_name = act['action'].replace('switch ', '')
            lines.append(f"- `{act['action']}` → Switch to **{pkmn_name.title()}**")
        lines.append("")

    # Capabilities
    cap_lines = []
    if constraints.get('can_mega'):
        cap_lines.append("- Can Mega Evolve (add `-mega` suffix)")
    if constraints.get('can_tera'):
        tera_type = constraints.get('can_tera')
        if tera_type:
            cap_lines.append(f"- Can Terastallize to {tera_type} (add `-tera` suffix)")

    if cap_lines:
        lines.append("## Special Capabilities")
        lines.extend(cap_lines)

    return "\n".join(lines)


def format_move_result_md(
    battle_id: str,
    status: str,
    action: str,
    message: str,
    validation: dict,
    evaluation: Optional[dict] = None,
    error: Optional[str] = None,
) -> str:
    """Format move execution result as markdown."""

    lines = [f"# Move Result - {battle_id}", ""]

    if error:
        lines.append(f"## Error")
        lines.append(f"```\n{error}\n```")
        return "\n".join(lines)

    if not validation['valid']:
        lines.append(f"## Invalid Move")
        lines.append(f"**Action:** `{action}`")
        lines.append(f"**Reason:** {validation['reason']}")
        return "\n".join(lines)

    lines.append(f"## Move Sent Successfully")
    lines.append(f"**Action:** `{action}`")
    lines.append("")

    if evaluation:
        lines.append("### Evaluation")
        optimality = evaluation['optimality'] * 100
        lines.append(f"**Optimality:** {optimality:.1f}%")
        lines.append(f"**Best Move:** `{evaluation['best_move']}`")
        lines.append(f"**Scenarios Analyzed:** {evaluation['scenarios_analyzed']}")

        if evaluation['is_optimal']:
            lines.append("")
            lines.append("**This is the optimal move!**")
        elif optimality >= 90:
            lines.append("")
            lines.append("**This is a very good move**")
        elif optimality >= 70:
            lines.append("")
            lines.append("**This is a decent move**")
        elif optimality >= 50:
            lines.append("")
            lines.append(f"**This move is suboptimal** - consider using `{evaluation['best_move']}` instead")
        else:
            lines.append("")
            lines.append(f"**This move is significantly suboptimal** - `{evaluation['best_move']}` is much better")

    return "\n".join(lines)


def format_pokemon_details_md(details: dict) -> str:
    """Format pokemon details as markdown."""

    lines = [f"# Pokemon Details - {details.get('battle_id', 'Unknown')}", ""]

    if details.get('error'):
        lines.append(f"## Error: {details['error']}")
        if details.get('available_pokemon'):
            lines.append("")
            lines.append("**Available Pokemon:**")
            for name in details['available_pokemon']:
                lines.append(f"- {name.title()}")
        return "\n".join(lines)

    # Header
    owner = "Opponent's" if details.get('is_opponent') else "Your"
    lines.append(f"## {owner} Pokemon: **{details['name'].title()}**")
    lines.append("")

    # Basic info
    lines.append(f"**Level:** {details.get('level', '?')}")
    hp = details.get('hp', 0)
    max_hp = details.get('max_hp', 1)
    hp_percent = int((hp / max_hp) * 100) if max_hp > 0 else 0
    lines.append(f"**HP:** {hp}/{max_hp} ({hp_percent}%)")

    if details.get('status'):
        lines.append(f"**Status:** {details['status'].upper()}")

    if details.get('types'):
        types_str = "/".join(t.title() for t in details['types'])
        lines.append(f"**Type:** {types_str}")

    if details.get('ability') and details['ability'] != 'unknown':
        lines.append(f"**Ability:** {details['ability'].title()}")

    if details.get('item') and details['item'] != 'unknown':
        lines.append(f"**Item:** {details['item'].title()}")

    if details.get('tera_type'):
        lines.append(f"**Tera Type:** {details['tera_type'].title()}")
        if details.get('terastallized'):
            lines.append("  _(Currently Terastallized)_")

    lines.append("")

    # Stats
    if details.get('stats'):
        lines.append("### Stats")
        stats = details['stats']
        for stat_name in ['attack', 'defense', 'special-attack', 'special-defense', 'speed']:
            if stat_name in stats:
                display_name = stat_name.replace('-', ' ').title()
                lines.append(f"- **{display_name}:** {stats[stat_name]}")
        lines.append("")

    # Boosts
    if details.get('boosts'):
        boosts = details['boosts']
        active_boosts = {k: v for k, v in boosts.items() if v != 0}
        if active_boosts:
            lines.append("### Stat Changes")
            for stat, value in active_boosts.items():
                sign = "+" if value > 0 else ""
                lines.append(f"- **{stat.title()}:** {sign}{value}")
            lines.append("")

    # Moves
    if details.get('moves'):
        lines.append("### Moves")
        for move in details['moves']:
            move_line = f"**{move['name'].title()}**"

            move_details = []
            if move.get('type'):
                move_details.append(f"Type: {move['type'].title()}")
            if move.get('category'):
                move_details.append(f"Category: {move['category'].title()}")
            if move.get('power'):
                move_details.append(f"Power: {move['power']}")
            if move.get('accuracy') is not None and move['accuracy'] is not True:
                move_details.append(f"Accuracy: {move['accuracy']}")
            if 'pp' in move and 'max_pp' in move:
                move_details.append(f"PP: {move['pp']}/{move['max_pp']}")

            if move_details:
                move_line += " (" + ", ".join(move_details) + ")"

            if move.get('disabled'):
                move_line += " [DISABLED]"

            lines.append(f"- {move_line}")
        lines.append("")

    # Volatile statuses
    if details.get('volatile_statuses'):
        lines.append("### Volatile Status Effects")
        for status in details['volatile_statuses']:
            lines.append(f"- {status.title()}")
        lines.append("")

    return "\n".join(lines)
