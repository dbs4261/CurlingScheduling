import functools
import pathlib
import typing


@functools.total_ordering
class Team:
    def __init__(self, name: str, members: typing.List[str] = None):
        self.name: str = name
        self.members: typing.List[str] = members if members is not None else []
        self.members.sort()

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return "Team: {} {}".format(self.name, self.members)

    def __eq__(self, other: "Team") -> bool:
        return isinstance(other, Team) and self.name == other.name and \
               all(m in other.members for m in self.members)

    def __lt__(self, other: "Team") -> bool:
        if self.name == other.name:
            if len(self.members) == len(other.members):
                return self.members < other.members
            else:
                return len(self.members) < len(other.members)
        else:
            return self.name < other.name

    def __hash__(self):
        return hash((self.name, *self.members))


def team_list_header() -> typing.List[str]:
    return ["Team Name", "Short Name", "Abbreviation", "Members..."]


def members_header_index() -> int:
    return 3


def ParseHeader(header: typing.List[str]):
    first_name_idx: int = -1
    last_name_idx: int = -1
    teammate_idxs: typing.List[int] = []
    team_name_idx: int = -1
    for col, element in enumerate((e.lower() for e in header)):
        el_first = element.find("first")
        el_last = element.find("last")
        el_team = element.find("team")
        el_mate = element.find("mate")
        el_name = element.find("name")
        if el_first != -1 and el_name != -1 and first_name_idx == -1:
            first_name_idx = col
        if el_last != -1 and el_name != -1 and last_name_idx == -1:
            last_name_idx = col
        if el_team != -1 and el_name != -1 and el_mate != -1:
            teammate_idxs.append(col)
        if el_team != -1 and el_name != -1 and el_mate == -1 and team_name_idx == -1:
            team_name_idx = col
    return first_name_idx, last_name_idx, teammate_idxs, team_name_idx


def read_team_csv(path: pathlib.Path) -> typing.List[Team]:
    out: typing.List[Team] = []
    with open(path, "rt") as csv_file:
        header = [el.strip() for el in csv_file.readline().strip().split(",")]
        first_name_idx, last_name_idx, teammate_idxs, team_name_idx = ParseHeader(header)
        if team_name_idx < 0:
            raise ValueError("Invalid teams.csv header")
        for line in (l.strip().split(",") for l in csv_file):
            teammates = [""]
            if first_name_idx != -1:
                teammates[0] += line[first_name_idx].strip()
            if last_name_idx != -1:
                if first_name_idx != -1:
                    teammates[0] += " "
                teammates[0] += line[last_name_idx].strip()
            for idx in teammate_idxs:
                teammates.append(line[idx].strip())
            out.append(Team(name=line[team_name_idx].strip(), members=teammates))
    return out
