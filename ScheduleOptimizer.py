import datetime
import enum
import itertools
import pathlib
import pickle
import typing

from ortools.sat.python import cp_model

from Game import Game
from Team import Team


class ScheduleSolutionCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self, schedule_variables, num_games_vs_variables, num_empty, num_lonely, num_full, num_double_headers, teams, games):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.schedule = schedule_variables
        self.num_games_vs = num_games_vs_variables
        self.__solution_count = 0
        self.teams = teams
        self.games = games
        self.empty_draws: typing.Optional[cp_model.IntVar] = num_empty
        self.lonely_draws: typing.Optional[cp_model.IntVar] = num_lonely
        self.full_draws: typing.Optional[cp_model.IntVar] = num_full
        self.num_double_headers: typing.Optional[cp_model.IntVar] = num_double_headers

    def on_solution_callback(self):
        self.__solution_count += 1
        assignment = [[team for t, team in enumerate(self.teams) if self.Value(self.schedule[g][t]) == 1] for g in range(len(self.games))]
        print("Solution #", self.solution_count())
        print("Schedule:")
        print("\n".join(["{}: {}".format(game, " vs ".join(str(t) for t in assignment[g])) for g, game in enumerate(self.games)]))
        print("Num games A vs B:")
        print("\n".join("{}: {}".format(v, self.Value(v)) for v in self.num_games_vs.values()))
        if None not in [self.empty_draws, self.full_draws, self.lonely_draws]:
            print("Empty Draws:", self.Value(self.empty_draws),
                  "Lonely Draws:", self.Value(self.lonely_draws),
                  "Full Draws:", self.Value(self.full_draws))
        if self.num_double_headers is not None:
            print("Double Headers:", self.Value(self.num_double_headers))
        print("Objective Value:", self.ObjectiveValue(), "Best Objective Bound:", self.BestObjectiveBound())
        print("NumBools:", self.NumBooleans(), "NumConflicts:", self.NumConflicts(), "NumBranches:", self.NumBranches())
        print("Wall Time:", self.WallTime(), "User Time:", self.UserTime())
        with open(pathlib.Path.cwd().joinpath(f"solution_{self.solution_count()}.pickle"), "wb") as out:
            pickle.dump({
                "teams": self.teams,
                "games": self.games,
                "assignment": assignment,
                "objective_value": self.ObjectiveValue(),
                "best_objective_bound": self.BestObjectiveBound(),
                "num_booleans": self.NumBooleans(),
                "num_conflicts": self.NumConflicts(),
                "num_branches": self.NumBranches(),
                "wall_time": self.WallTime(),
                "user_time": self.UserTime(),
                "empty_draws": self.Value(self.empty_draws),
                "lonely_draws": self.Value(self.lonely_draws),
                "full_draws": self.Value(self.full_draws),
            }, out)

    def solution_count(self):
        return self.__solution_count


class ScheduleOptimizer:
    class Constraints(enum.Enum):
        TeamsPerGame = enum.auto()
        DoubleScheduling = enum.auto()
        ExactlyEqualGames = enum.auto()
        AlmostEqualGames = enum.auto()
        RoundRobin = enum.auto()
        ExactNumGames = enum.auto()
        MinimumRequiredGames = enum.auto()
        NoDoubleHeaders = enum.auto()
        Unavailability = enum.auto()

    class Objectives(enum.Enum):
        MaximizeNumGames = enum.auto()
        NoRepeatGames = enum.auto()
        MinimizeDoubleHeaders = enum.auto()
        IceMakers = enum.auto()
        EmptyFullDraws = enum.auto()

    def __init__(self, games: typing.List[Game], teams: typing.List[Team]):
        self.num_teams_per_game = 2
        self.games = games
        self.teams = teams
        self.constraints: typing.Set["ScheduleOptimizer.Constraints"] = set()
        self.objectives: typing.Dict["Scheduler.Objectives", typing.Dict] = dict()
        self.model = cp_model.CpModel()
        self.schedule = [[self.model.NewBoolVar("T: {} | G: {}".format(team, game))
                          for team in self.teams] for game in self.games]
        self.venue_in_use = [self.model.NewBoolVar("Use {}?".format(game)) for game in self.games]
        start_times = list(set(game.game_start for game in self.games))
        self.max_venues: typing.Dict[datetime.datetime, int] = \
            {start: sum(1 if game.game_start == start else 0 for game in games) for start in start_times}
        self.venues_per_start: typing.Dict[datetime.datetime, cp_model.IntVar] = \
            {start: self.model.NewIntVar(0, self.max_venues[start], f"Games at {start}") for start in start_times}
        [self.model.Add(sum(self.venue_in_use[g] for g, game in enumerate(self.games) if game.game_start == start) == self.venues_per_start[start])
            for start in self.venues_per_start.keys()]
        self.num_games_vs: typing.Dict[typing.Tuple, cp_model.IntVar] = \
            {tuple(sorted(_teams)): self.model.NewIntVar(0, len(self.teams), " vs ".join([str(t) for t in _teams]))
                             for _teams in itertools.combinations(self.teams, self.num_teams_per_game)}
        self.num_games_vars: typing.List[cp_model.IntVar] = []
        self.temp_variables: typing.List[cp_model.IntVar] = []
        self.empty_draws: typing.Optional[cp_model.IntVar] = None
        self.lonely_draws: typing.Optional[cp_model.IntVar] = None
        self.full_draws: typing.Optional[cp_model.IntVar] = None
        self.num_double_headers: typing.Optional[cp_model.IntVar] = None

    def teams_per_game_constraint(self):
        if ScheduleOptimizer.Constraints.TeamsPerGame in self.constraints:
            return
        for d in range(len(self.games)):
            self.model.Add(sum(self.schedule[d]) == self.num_teams_per_game).OnlyEnforceIf(self.venue_in_use[d])
            self.model.Add(sum(self.schedule[d]) == 0).OnlyEnforceIf(self.venue_in_use[d].Not())
        self.constraints.add(ScheduleOptimizer.Constraints.TeamsPerGame)

    def no_double_scheduling_constraint(self):
        if ScheduleOptimizer.Constraints.DoubleScheduling in self.constraints:
            return
        overlapping_games = [[i] for i in range(len(self.games))]
        for a, b in itertools.permutations(enumerate(self.games), 2):
            a: typing.Tuple[int, Game]
            b: typing.Tuple[int, Game]
            if a[1].overlaps(b[1]):
                overlapping_games[a[0]].append(b[0])
        for overlap in overlapping_games:
            for t in range(len(self.teams)):
                self.model.Add(sum(self.schedule[i][t] for i in overlap) <= 1)
        self.constraints.add(ScheduleOptimizer.Constraints.DoubleScheduling)

    def equal_games_constraint(self, exact: bool):
        if exact:
            if ScheduleOptimizer.Constraints.ExactlyEqualGames in self.constraints:
                return
            elif ScheduleOptimizer.Constraints.AlmostEqualGames in self.constraints:
                raise RuntimeError("Cannot have both constraints for almost and exactly equal games")
            self.num_games_vars = [self.model.NewIntVar(0, len(self.games), "Games Per Team")]
            for t in range(len(self.teams)):
                self.model.Add(sum(self.schedule[g][t] for g in range(len(self.games))) == self.num_games_vars[0])
            self.constraints.add(ScheduleOptimizer.Constraints.ExactlyEqualGames)
        else:
            if ScheduleOptimizer.Constraints.AlmostEqualGames in self.constraints:
                return
            elif ScheduleOptimizer.Constraints.ExactlyEqualGames in self.constraints:
                raise RuntimeError("Cannot have both constraints for almost and exactly equal games")
            self.num_games_vars = [self.model.NewIntVar(0, len(self.games), "Games for {}".format(team)) for team in self.teams]
            for t in range(len(self.teams)):
                self.model.Add(sum(self.schedule[g][t] for g in range(len(self.games))) == self.num_games_vars[t])
            for t1, t2 in itertools.permutations(self.num_games_vars, 2):
                self.model.AddLinearConstraint(t1 - t2, -1, 1)
            self.constraints.add(ScheduleOptimizer.Constraints.AlmostEqualGames)

    def round_robin_constraint(self):
        if ScheduleOptimizer.Constraints.RoundRobin in self.constraints:
            return
        teams_per_game_constant = self.model.NewConstant(self.num_teams_per_game)
        for teams in itertools.combinations(enumerate(self.teams), self.num_teams_per_game):
            team_tuple = tuple(sorted([team for _, team in teams]))
            temp = [self.model.NewBoolVar("{} all there".format(teams)) for _ in range(len(self.games))]
            [self.model.AddMultiplicationEquality(temp[g], [self.schedule[g][t] for t, _ in teams]) for g in range(len(self.games))]
            self.model.Add(sum(temp) == self.num_games_vs[team_tuple])
            self.temp_variables.extend(temp)
        for g1, g2 in itertools.permutations(self.num_games_vs.values(), 2):
            self.model.AddLinearConstraint(g1 - g2, -1, 1)
        self.constraints.add(ScheduleOptimizer.Constraints.RoundRobin)

    def unavailable_constraint(self, data: typing.Dict[Team, typing.List[typing.Union[datetime.date, datetime.datetime]]]):
        if ScheduleOptimizer.Constraints.Unavailability in self.constraints:
            return
        team_indices = {team: self.teams.index(team) for team in data.keys()}
        for team in data.keys():
            for start in data[team]:
                g_s = [g for g, game in enumerate(self.games) if
                       (isinstance(start, datetime.date) and game.game_start.date() == start) or
                       (isinstance(start, datetime.datetime) and game.game_start == start)]
                for g in g_s:
                    self.model.Add(self.schedule[g][team_indices[team]] == 0)
        self.constraints.add(ScheduleOptimizer.Constraints.Unavailability)

    def icemaker_objective(self, icemakers: typing.List[Team], weight: float = 4.0):
        if ScheduleOptimizer.Objectives.IceMakers in self.constraints:
            return
        icemaker_indices = [t for t, team in enumerate(self.teams) if team in icemakers]
        first_draw_times = list(set([game.game_start for game in self.games]))
        first_draw_times = list(filter(lambda start: any(other < start for other in first_draw_times), first_draw_times))
        first_draw_games = [g for start in first_draw_times for g, game in enumerate(self.games) if game.game_start == start]
        self.model.Add(sum(self.schedule[g][t] for g in first_draw_games for t in icemaker_indices) > 0)
        objective: cp_model.LinearExpr = sum(self.schedule[g][t] for g in first_draw_games for t in icemaker_indices)
        self.objectives[ScheduleOptimizer.Objectives.IceMakers] = \
            {"weight": weight, "objective": objective}

    def disallow_double_headers(self):
        if ScheduleOptimizer.Constraints.NoDoubleHeaders in self.constraints:
            return
        dates = set(game.game_start.date() for game in self.games).union(game.game_end.date() for game in self.games)
        for date in dates:
            same_day_games = [g for g, game in enumerate(self.games) if game.game_start.date() == date or game.game_end.date() == date]
            for t, team in enumerate(self.teams):
                self.model.Add(sum(self.schedule[g][t] for g in same_day_games) == 1)
        self.constraints.add(ScheduleOptimizer.Constraints.NoDoubleHeaders)

    def minimize_double_headers(self, weight: float = 1.0):
        if ScheduleOptimizer.Constraints.NoDoubleHeaders in self.constraints:
            raise RuntimeError("Cant minimize double headers if they are not allowed to be scheduled")
        if ScheduleOptimizer.Objectives.MinimizeDoubleHeaders in self.objectives:
            return
        dates = list(set(game.game_start.date() for game in self.games).union(game.game_end.date() for game in self.games))
        team_double_header_vars = {}
        for t, team in enumerate(self.teams):
            team_double_headers = []
            for date in dates:
                temp = self.model.NewBoolVar(f"{team} double header on {date}")
                self.model.Add(sum(self.schedule[g][t] for g, game in enumerate(self.games)
                                   if game.game_start.date() == date or game.game_end.date() == date) > 1).OnlyEnforceIf(temp)
                self.model.Add(sum(self.schedule[g][t] for g, game in enumerate(self.games)
                                   if game.game_start.date() == date or game.game_end.date() == date) <= 1).OnlyEnforceIf(temp.Not())
                team_double_headers.append(temp)
            team_double_header_vars[team] = self.model.NewIntVar(0, len(self.games), f"{team} double headers")
            self.model.Add(sum(v for v in team_double_headers) == team_double_header_vars[team])
        self.num_double_headers = self.model.NewIntVar(0, len(self.teams) * len(self.games), "Double Headers")
        self.model.Add(self.num_double_headers == sum(team_double_header_vars.values()))
        self.objectives[ScheduleOptimizer.Objectives.MinimizeDoubleHeaders] = {"weight": -abs(weight), "objective": self.num_double_headers}

    def maximize_games_objective(self, weight: float = 1.0):
        if ScheduleOptimizer.Constraints.ExactNumGames in self.objectives:
            raise RuntimeError("Cannot add an optimization objective to maximize the number of games when the number of games is a constraint")
        objective_fn: cp_model.LinearExpr = sum(sum(self.schedule[d]) for d in range(len(self.games)))
        self.objectives[ScheduleOptimizer.Objectives.MaximizeNumGames] = {"weight": weight, "objective": objective_fn}

    def require_num_games(self, num_games: int, exact: bool = True, max_games: typing.Optional[int] = None):
        if exact:
            if max_games is not None:
                raise ValueError("Cant use max_games when exact = True")
            if ScheduleOptimizer.Objectives.MaximizeNumGames in self.objectives:
                raise RuntimeError("Cannot require a specific number of games if an optimization objective is to maximize the number of games")
            if not ScheduleOptimizer.Constraints.ExactlyEqualGames in self.constraints:
                self.equal_games_constraint(exact=True)
            self.num_games_vars = [self.model.Add(v == num_games) for v in self.num_games_vars]
            self.constraints.add(ScheduleOptimizer.Constraints.ExactNumGames)
        else:
            if max_games <= num_games:
                raise ValueError("max_games (if given) must be greater than num_games")
            if not ScheduleOptimizer.Constraints.ExactlyEqualGames in self.constraints:
                self.equal_games_constraint(exact=False)
            self.num_games_vars = [self.model.Add(v >= num_games) for v in self.num_games_vars]
            if max_games is not None:
                self.num_games_vars = [self.model.Add(max_games >= num_games) for v in self.num_games_vars]
            self.constraints.add(ScheduleOptimizer.Constraints.MinimumRequiredGames)

    def empty_full_draw_objective(self, overall_weight: float = 1.0,
                                  weight_empty: float = 2.0, weight_full: float = 1.0, weight_lonely: float = -3.0):
        if ScheduleOptimizer.Objectives.EmptyFullDraws in self.objectives:
            return
        unique_draws = len(list(self.venues_per_start.keys()))
        empty_bools = {start: self.model.NewBoolVar(f"{start} is empty") for start in self.venues_per_start.keys()}
        [self.model.Add(self.venues_per_start[start] == 0).OnlyEnforceIf(empty_bools[start]) for start in empty_bools.keys()]
        [self.model.Add(self.venues_per_start[start] > 0).OnlyEnforceIf(empty_bools[start].Not()) for start in empty_bools.keys()]
        self.empty_draws = self.model.NewIntVar(0, unique_draws, "Empty Draws")
        self.model.Add(self.empty_draws == sum(empty_bools[start] for start in empty_bools.keys()))
        lonely_bools = {start: self.model.NewBoolVar(f"{start} is lonely") for start in self.venues_per_start.keys()}
        [self.model.Add(self.venues_per_start[start] == 1).OnlyEnforceIf(lonely_bools[start]) for start in lonely_bools.keys()]
        [self.model.Add(self.venues_per_start[start] != 1).OnlyEnforceIf(lonely_bools[start].Not()) for start in lonely_bools.keys()]
        self.lonely_draws = self.model.NewIntVar(0, unique_draws, "Lonely Draws")
        self.model.Add(self.lonely_draws == sum(lonely_bools[start] for start in lonely_bools.keys()))
        full_bools = {start: self.model.NewBoolVar(f"{start} is full") for start in self.venues_per_start.keys()}
        [self.model.Add(self.venues_per_start[start] == self.max_venues[start]).OnlyEnforceIf(full_bools[start]) for start in full_bools.keys()]
        [self.model.Add(self.venues_per_start[start] < self.max_venues[start]).OnlyEnforceIf(full_bools[start].Not()) for start in full_bools.keys()]
        self.full_draws = self.model.NewIntVar(0, unique_draws, "Full Draws")
        self.model.Add(self.full_draws == sum(full_bools[start] for start in full_bools.keys()))
        self.objectives[ScheduleOptimizer.Objectives.EmptyFullDraws] = {
            "weight": overall_weight, "objective": self.empty_draws * weight_empty + self.lonely_draws * weight_lonely + self.full_draws * weight_full,
        }

    def solve(self, verbose: bool = False):
        if len(self.objectives) > 0:
            self.model.Maximize(sum(v["weight"] * v["objective"] for v in self.objectives.values()))
        print(*[(t, team) for t, team in enumerate(self.teams)])
        print("Model valid:", self.model.Validate())
        solver = cp_model.CpSolver()
        solution_callback = ScheduleSolutionCallback(self.schedule, self.num_games_vs, self.empty_draws,
            self.lonely_draws, self.full_draws, self.num_double_headers, self.teams, self.games)
        solver.parameters.enumerate_all_solutions = False
        solver.parameters.log_search_progress = verbose
        import os
        solver.parameters.num_search_workers = os.cpu_count() // 2
        solver.log_callback = lambda s: print("Solver log:", s)
        print("Solving, please wait...")
        status = solver.Solve(self.model, solution_callback)

        print("Solution Info:", solver.SolutionInfo())
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            if None not in [self.empty_draws, self.full_draws, self.lonely_draws]:
                print("Empty Draws:", solver.Value(self.empty_draws),
                      "Lonely Draws:", solver.Value(self.lonely_draws),
                      "Full Draws:", solver.Value(self.full_draws))
            if self.num_double_headers is not None:
                print("Double Headers:", solver.Value(self.num_double_headers))
            assignment = [[team for t, team in enumerate(self.teams) if solver.Value(self.schedule[g][t]) == 1] for g in range(len(self.games))]
            print("\n".join(["{}: {}".format(game, " vs ".join(str(t) for t in assignment[g])) for g, game in enumerate(self.games)]))
            print("\n".join("{}: {}".format(v, solver.Value(v)) for v in self.num_games_vs.values()))
            print("Solution Strength:", solver.ObjectiveValue())
            return assignment
        else:
            raise RuntimeError("No solution found!")

