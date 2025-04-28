import logging
import requests

import customtkinter as ctk
from tkinter import messagebox, SEL, INSERT, END

import constants
from config import FoulPlayConfig, init_logging
from data.mods.apply_mods import apply_mods
from data.pkmn_sets import SmogonSets, TeamDatasets
from fp.battle import Battle, Pokemon
from fp.battle_modifier import process_battle_updates
from fp.battle_bots.mcts_parallel.main import BattleBot
from fp.helpers import normalize_name, calculate_stats
from teams.team_converter import export_to_dict

logger = logging.getLogger(__name__)

init_logging("INFO", False)


def reconfigure_logging(level: str):
    FoulPlayConfig.stdout_log_handler.setLevel(level)


def set_players(replay_str: str, battle: Battle, username: str):
    players = [l for l in replay_str.split("\n") if l.startswith("|player|")][:2]
    assert len(players) == 2, "Replay must contain two players"
    p1 = players[0].split("|")[3]
    p2 = players[1].split("|")[3]

    if p1 == username:
        battle.user.name = "p1"
        battle.opponent.name = "p2"
    elif p2 == username:
        battle.user.name = "p2"
        battle.opponent.name = "p1"
    else:
        raise ValueError("Username not found in replay")


def set_bots_team(battle: Battle, team_export_string: str):
    team_dict = export_to_dict(team_export_string)
    for pkmn_dict in team_dict:
        evs = (
            int(pkmn_dict["evs"]["hp"]) if pkmn_dict["evs"]["hp"] else 0,
            int(pkmn_dict["evs"]["atk"]) if pkmn_dict["evs"]["atk"] else 0,
            int(pkmn_dict["evs"]["def"]) if pkmn_dict["evs"]["def"] else 0,
            int(pkmn_dict["evs"]["spa"]) if pkmn_dict["evs"]["spa"] else 0,
            int(pkmn_dict["evs"]["spd"]) if pkmn_dict["evs"]["spd"] else 0,
            int(pkmn_dict["evs"]["spe"]) if pkmn_dict["evs"]["spe"] else 0,
        )
        pkmn = Pokemon(
            pkmn_dict["species"],
            pkmn_dict["level"] or 100,
            nature=pkmn_dict["nature"],
            evs=evs,
        )
        pkmn.ability = pkmn_dict["ability"]
        pkmn.item = pkmn_dict["item"]
        pkmn.tera_type = pkmn_dict["tera_type"]
        for mv in pkmn_dict["moves"]:
            mv_name = normalize_name(mv)
            if mv_name.startswith("hiddenpower"):
                mv_name = mv_name.replace("]", "")
                mv_name = mv_name.replace("[", "")
            pkmn.add_move(mv_name)

        battle.user.reserve.append(pkmn)


def initialize_datasets(battle: Battle, battle_format: str):
    our_side_pkmn_names = set(p.name for p in battle.user.reserve)
    SmogonSets.initialize(
        FoulPlayConfig.smogon_stats or battle_format, our_side_pkmn_names
    )
    TeamDatasets.initialize(battle_format, our_side_pkmn_names)


def re_calculate_all_pkmn_hp(battle: Battle):
    active = battle.user.active
    if active is not None and active.max_hp == 100:
        hp = calculate_stats(
            active.base_stats, active.level, nature=active.nature, evs=active.evs
        )["hp"]
        active.max_hp = hp
        active.hp = active.hp * active.max_hp / 100

    for pkmn in battle.user.reserve:
        if pkmn.max_hp != 100:
            continue
        hp = calculate_stats(
            pkmn.base_stats, pkmn.level, nature=pkmn.nature, evs=pkmn.evs
        )["hp"]
        pkmn.max_hp = hp
        pkmn.hp = pkmn.hp * pkmn.max_hp / 100


def get_replay_log(replay_link: str) -> str:
    return requests.get(f"{replay_link}.log").text


def get_generation(replay_log: str):
    return f"gen{replay_log.split('|gen|')[1].split('|')[0].strip()}"


def get_tier(replay_log: str):
    return normalize_name(replay_log.split('|tier|')[1].split("|")[0].strip().replace("[", "").replace("]", ""))


def main(
    replay_log: str,
    username: str,
    team_export: str,
    parallelism: int,
    search_time_ms: int,
    turns: list[int],
):
    FoulPlayConfig.parallelism = parallelism
    FoulPlayConfig.search_time_ms = search_time_ms
    FoulPlayConfig.pokemon_mode = get_tier(replay_log)

    btl = BattleBot(None)
    btl.generation = get_generation(replay_log)
    btl.game_review = True
    btl.battle_type = constants.STANDARD_BATTLE
    apply_mods(FoulPlayConfig.pokemon_mode)

    set_players(replay_log, btl, username)
    set_bots_team(btl, team_export)
    initialize_datasets(btl, FoulPlayConfig.pokemon_mode)

    choices = {}
    replay_split = replay_log.split("|t:|")
    for line in replay_split:
        if any(l.startswith("|win|") for l in line.split("\n")):
            print("Battle Finished")
            break
        re_calculate_all_pkmn_hp(btl)
        btl.msg_list = line.split("\n")
        process_battle_updates(btl)

        if btl.turn and btl.turn in turns:
            if btl.turn not in choices:
                choices[btl.turn] = []
            choice = btl.find_best_move()
            choices[btl.turn].append(choice)
            logger.info(f"Turn {btl.turn}: {choice}")
        elif btl.turn > turns[-1]:
            break

    for k, v in choices.items():
        print(f"Turn {k}: {v}")

    return choices


def select_all_text(event):
    widget = event.widget
    widget.tag_add(SEL, "1.0", END)
    widget.mark_set(INSERT, "1.0")
    widget.see(INSERT)
    return "break"


def select_all_entry(event):
    widget = event.widget
    widget.select_range(0, END)
    widget.icursor(0)
    return "break"


class GameReviewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pokémon Showdown Game Reviewer")
        self.root.geometry("900x900")
        self.root.resizable(False, False)

        # Set CustomTkinter theme
        ctk.set_appearance_mode("Dark")  # "Light", "Dark", or "System"
        ctk.set_default_color_theme("blue")  # You can change to green/dark-blue

        header_font = ctk.CTkFont("Arial", size=16, weight="bold")

        row = 0

        ### Replay Information ###

        # Replay Information Header
        self.replay_info_label = ctk.CTkLabel(
            root, text="Replay Information", font=header_font
        )
        self.replay_info_label.grid(row=row, column=0, padx=10, pady=10, sticky="e")
        row += 1

        # Replay Link
        self.replay_label = ctk.CTkLabel(root, text="Replay Link:")
        self.replay_label.grid(row=row, column=0, sticky="e", padx=35, pady=5)
        self.replay_entry = ctk.CTkEntry(
            root, width=600, placeholder_text="Enter the replay link here"
        )
        self.replay_entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        self.replay_entry.bind("<Control-Key-a>", select_all_entry)
        row += 1

        # Replay Link
        self.username_label = ctk.CTkLabel(root, text="Username:")
        self.username_label.grid(row=row, column=0, sticky="e", padx=35, pady=5)
        self.username_entry = ctk.CTkEntry(
            root, width=600, placeholder_text="Enter the username to review here"
        )
        self.username_entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        self.username_entry.bind("<Control-Key-a>", select_all_entry)
        row += 1

        # Team Export String
        self.team_label = ctk.CTkLabel(root, text="Team Export:")
        self.team_label.grid(row=row, column=0, sticky="ne", padx=35, pady=5)
        self.team_text = ctk.CTkTextbox(root, width=600, height=150)
        self.team_text.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        self.team_text.bind("<Control-Key-a>", select_all_text)
        row += 1

        ### Engine Configurations ###

        # Engine Information Header
        self.engine_info_label = ctk.CTkLabel(
            root, text="Engine Information", font=header_font
        )
        self.engine_info_label.grid(row=row, column=0, padx=10, pady=10, sticky="e")
        row += 1

        # Turn selector
        self.turn_label = ctk.CTkLabel(root, text="Turns:")
        self.turn_label.grid(row=row, column=0, sticky="e", padx=35, pady=5)
        self.turn_entry = ctk.CTkEntry(
            root,
            width=400,
            placeholder_text="Enter the turns to review here. e.g. 1,2,5-8,11",
        )
        self.turn_entry.grid(row=row, column=1, pady=5, sticky="w")
        self.turn_entry.bind("<Control-Key-a>", select_all_entry)
        row += 1

        # Parallelism selector
        self.parallelism_label = ctk.CTkLabel(root, text="Parallelism:")
        self.parallelism_label.grid(row=row, column=0, sticky="e", padx=35, pady=5)
        self.parallelism_entry = ctk.CTkEntry(
            root,
            width=400,
            textvariable=ctk.StringVar(value="2"),
        )
        self.parallelism_entry.grid(row=row, column=1, pady=5, sticky="w")
        self.parallelism_entry.bind("<Control-Key-a>", select_all_entry)
        row += 1

        # Search Time selector
        self.search_time_label = ctk.CTkLabel(root, text="Search Time (ms):")
        self.search_time_label.grid(row=row, column=0, sticky="e", padx=35, pady=5)
        self.search_time_entry = ctk.CTkEntry(
            root,
            width=400,
            textvariable=ctk.StringVar(value="2000"),
        )
        self.search_time_entry.grid(row=row, column=1, pady=5, sticky="w")
        self.search_time_entry.bind("<Control-Key-a>", select_all_entry)
        row += 1

        ### Output Configurations ###

        # Output
        self.engine_info_label = ctk.CTkLabel(root, text="Output", font=header_font)
        self.engine_info_label.grid(row=row, column=0, padx=10, pady=10, sticky="e")
        row += 1

        # Output window
        self.output_label = ctk.CTkLabel(root, text="Review Output:")
        self.output_label.grid(row=row, column=0, sticky="ne", padx=35, pady=5)
        self.output_text = ctk.CTkTextbox(root, width=600, height=300, state="disabled")
        self.output_text.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        row += 1

        # Start Review Button
        self.start_button = ctk.CTkButton(
            root, text="Start Game Review", command=self.start_review
        )
        self.start_button.grid(row=row, column=1, pady=10, sticky="e")
        row += 1

    def get_turns(self, turns_input: str):
        turns = []
        turns_split = turns_input.split(",")
        for turn in turns_split:
            if "-" in turn:
                start, end = turn.split("-")
                start, end = int(start), int(end)
                turns.extend(range(start, end + 1))
            else:
                turns.append(int(turn))

        return turns

    def start_review(self):
        replay_link = self.replay_entry.get()
        battler = self.username_entry.get()
        team_export = self.team_text.get("1.0", "end").strip()
        turns_text = self.turn_entry.get().strip()
        parallelism = self.parallelism_entry.get().strip()
        search_time = self.search_time_entry.get().strip()

        try:
            turns = self.get_turns(turns_text)
        except ValueError:
            messagebox.showerror("Error", "Turns must be integers.")
            return

        if not replay_link or not battler or not team_export:
            messagebox.showerror(
                "Error", "Must provide an export, battler, and replay link."
            )
            return

        try:
            parallelism = int(parallelism)
        except ValueError:
            messagebox.showerror("Error", "Parallelism must be an integer.")
            return None

        try:
            search_time = int(search_time)
        except ValueError:
            messagebox.showerror("Error", "Search time must be an integer.")
            return None

        try:
            replay_log = requests.get(f"{replay_link}.log").text
        except requests.RequestException:
            messagebox.showerror("Error", "Could not get replay log from link.")
            return

        try:
            moves = main(
                replay_log, battler, team_export, parallelism, search_time, turns
            )
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
            return

        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        for turn, moves in moves.items():
            for move in moves:
                self.output_text.insert("end", f"Turn: {turn}: {move}" + "\n")
        self.output_text.configure(state="disabled")


if __name__ == "__main__":
    root = ctk.CTk()  # <-- CustomTkinter root
    app = GameReviewApp(root)
    root.mainloop()
