import random
import os
from .team_converter import export_to_packed, export_to_dict

TEAM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "teams")


def load_team(name):
    if name is None:
        return "null", "", ""

    path = os.path.join(TEAM_DIR, "{}".format(name))
    if os.path.isdir(path):
        team_file_names = list()
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.startswith("."):
                    continue
                full_path = os.path.join(root, f)
                if os.path.isfile(full_path):
                    team_file_names.append(full_path)
        if not team_file_names:
            raise ValueError("No team files found in dir: {}".format(name))
        file_path = random.choice(team_file_names)

    elif os.path.isfile(path):
        file_path = path
    else:
        raise ValueError("Path must be file or dir: {}".format(name))

    with open(file_path, "r") as f:
        team_export = f.read()

    return (
        export_to_packed(team_export),
        export_to_dict(team_export),
        os.path.relpath(file_path, path),
    )
