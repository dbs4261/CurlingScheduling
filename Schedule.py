import copy
import dataclasses
import datetime
import itertools
import numpy as np
import pathlib
import typing

from Game import Game
from Venue import Venue, venue_type_from_str
from Weekday import Weekday
from Team import Team
from ScheduleOptimizer import ScheduleOptimizer


class Schedule:
    def __init__(self, games: typing.List[Game] = None,
                 assignments: typing.List[typing.List[Team]] = None):
        self._games: typing.List[Game] = games if games is not None else []
        self._assignments: typing.List[typing.List[Team]] = assignments if assignments is not None else []
        if not len(self._assignments) == len(self._games):
            if len(self._assignments) > 0:
                raise ValueError("Improper matchup between number of games and number of team assignments")
            self._assignments = [[]] * len(self._games)

    def __str__(self):
        return "\n".join(["{}: {}".format(game, teams) for game, teams in zip(self._games, self._assignments)])

    def start_times(self) -> typing.Set[datetime.datetime]:
        return set(game.game_start for game in self._games)

    def venues(self) -> typing.Set[Venue]:
        return set(game.venue for game in self._games if game.venue is not None)

    def venue_type(self) -> typing.Type:
        venues_set = self.venues()
        if len(venues_set) == 0:
            raise RuntimeError("No venues are assigned and therefore the type is unknown")
        venue_types = set(type(v) for v in venues_set)
        if len(venue_types) != 1:
            raise TypeError("Venues are not all the same type")
        return venue_types.pop()

    def teams_assigned(self) -> bool:
        return len(self._assignments) > 0 and any(len(teams) > 0 for teams in self._assignments)

    def teams(self) -> typing.Set[Team]:
        return set(team for matchup in self._assignments for team in matchup)

    def same_num_teams_per_game(self) -> bool:
        return len(set(len(matchup) for matchup in self._assignments)) == 1

    def teams_per_game(self) -> int:
        teams_per_game = set(len(matchup) for matchup in self._assignments if len(matchup) != 0)
        if len(teams_per_game) != 1:
            raise RuntimeError("Uneven number of teams assigned to each game")
        return teams_per_game.pop()

    def games_against_matrix(self) -> np.ndarray:
        num_teams = len(self.teams())
        assert(num_teams <= np.iinfo(np.uint8).max)
        game_matrix = np.zeros(shape=[num_teams] * self.teams_per_game(), dtype=np.uint8)
        team_to_idx_map = {t: i for i, t in enumerate(sorted(list(self.teams())))}
        for _, teams in zip(self._games, self._assignments):
            if len(teams) == 0:
                continue
            for indices in itertools.permutations([team_to_idx_map[t] for t in teams]):
                game_matrix[indices] += 1
        return game_matrix

    def games_per_venue(self) -> typing.Dict[Team, typing.Dict[Venue, int]]:
        out: typing.Dict[Team, typing.Dict[Venue, int]] = {}
        venues = {venue: 0 for venue in self.venues()}
        for game, teams in zip(self._games, self._assignments):
            for team in teams:
                if team not in out:
                    out[team] = copy.deepcopy(venues)
                out[team][game.venue] += 1
        return out

    @staticmethod
    def from_csv(path: pathlib.Path, teams: typing.List[Team] = None):
        with open(path, "rt") as csv_file:
            header = [el.strip() for el in csv_file.readline().strip().split(",")]
            if header[:len(Game.header()[:3])] != Game.header()[:3]:
                raise RuntimeError("Schedule CSV {}: has an improper header".format(path))
            team_indices = [idx for idx, el in enumerate(header) if el.lower().startswith("team ")]
            VenueType: typing.Type = venue_type_from_str(header[Game.header_venue_idx()])
            games: typing.List[Game] = []
            assignments: typing.List[typing.List[Team]] = []
            team_dict = {t.name: t for t in teams} if teams is not None else dict()
            for line in (l.strip() for l in csv_file):
                if line[0] == "#":
                    continue
                split_line = [el.strip() for el in line.split(",")]
                games.append(Game.from_csv(split_line[:len(Game.header())], VenueType))
                if len(team_dict) > 0:
                    assignments.append([team_dict[split_line[idx]] for idx in team_indices
                                        if idx < len(split_line) and split_line[idx] != ''])
                else:
                    assignments.append([Team(split_line[idx]) for idx in team_indices
                                        if idx < len(split_line) and split_line[idx] != ''])
            return Schedule(games, assignments)

    def to_csv(self, path: pathlib.Path):
        with open(path, "wt") as csv_file:
            header = Game.header()
            teams_per_game = self.teams_per_game()
            if len(self._assignments) > 0:
                header.extend(["Team {}".format(i) for i in range(teams_per_game)])
            csv_file.write(", ".join(header).format(Venue_Type=self.venue_type().__name__) + "\n")
            for game, teams in zip(self._games, self._assignments):
                if len(teams) == 0:
                    team_names = [""] * teams_per_game
                else:
                    team_names = [t.name for t in teams]
                csv_file.write(", ".join([game.to_csv(), *team_names]) + "\n")

    @staticmethod
    def naive_schedule(start_date: datetime.date, end_date: datetime.date,
                       game_times: typing.Union[datetime.time, typing.List[datetime.time]],
                       weekdays: typing.Union[None, Weekday, typing.List[Weekday]] = None,
                       game_length: typing.Optional[datetime.timedelta] = None,
                       venues: typing.Optional[typing.List[Venue]] = None):
        if weekdays is None or (isinstance(weekdays, list) and len(weekdays) == 0):
            weekdays = [Weekday.from_date(start_date)]
        if isinstance(weekdays, Weekday):
            weekdays = [weekdays]
        if isinstance(game_times, datetime.time):
            game_times = [game_times]
        if start_date > end_date:
            raise ValueError("Start date is after end date")
        starting_days = [Weekday.Next(start_date, w) for w in weekdays]
        days: typing.List[datetime.date] = [d for d in starting_days if d <= end_date]
        num_weeks = 1
        max_date = max(starting_days)
        while max_date <= end_date:
            days.extend([d for d in [d + datetime.timedelta(weeks=num_weeks) for d in starting_days] if d <= end_date])
            max_date += datetime.timedelta(weeks=1)
            num_weeks += 1
        assert(max(days) <= end_date)
        if venues is None or len(venues) == 0:
            return Schedule(games=[Game(d, t, game_length) for d, t in itertools.product(days, game_times)])
        else:
            return Schedule(games=[Game(d, t, game_length, v) for d, t, v in itertools.product(days, game_times, venues)])

    def populate_venues(self, venues: typing.List[Venue]):
        if not all(g.venue is None for g in self._games):
            raise RuntimeError("Venues are already assigned")
        if not all(len(teams) == 0 for teams in self._assignments):
            raise RuntimeError("Teams are already assigned to games")
        self._games = [Game(date=g.date, start_time=g.start_time, game_length=g.game_length, venue=v)
                       for g, v in itertools.product(self._games, venues)]

    def assign(self, teams: typing.List[Team], required_games: int = None):
        optimizer = ScheduleOptimizer(self._games, teams)
        optimizer.no_double_scheduling_constraint()
        optimizer.teams_per_game_constraint()
        optimizer.equal_games_constraint(exact=True)
        optimizer.round_robin_constraint()
        if required_games is not None:
            optimizer.require_num_games(required_games)
        else:
            optimizer.maximize_games_objective(weight=1.0)
        optimizer.disallow_double_headers()
        self._assignments = optimizer.solve()
