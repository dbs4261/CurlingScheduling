import enum
import functools
import itertools
import typing

from ortools.sat.python import cp_model

from Game import Game
from Team import Team

class ScheduleOptimizer:
    class Constraints(enum.Enum):
        TeamsPerGame = enum.auto()
        DoubleScheduling = enum.auto()
        ExactlyEqualGames = enum.auto()
        AlmostEqualGames = enum.auto()
        RoundRobin = enum.auto()
        ExactNumGames = enum.auto()
        NoDoubleHeaders = enum.auto()

    class Objectives(enum.Enum):
        MaximizeNumGames = enum.auto()
        NoRepeatGames = enum.auto()

    def __init__(self, games: typing.List[Game], teams: typing.List[Team]):
        self.num_teams_per_game = 2
        self.games = sorted(games)
        self.teams = sorted(teams)
        self.constraints: typing.Set["ScheduleOptimizer.Constraints"] = set()
        self.objectives: typing.Dict["Scheduler.Objectives", typing.Dict] = dict()
        self.model = cp_model.CpModel()
        self.schedule = [[self.model.NewBoolVar("T: {} | G: {}".format(team, game))
                          for team in self.teams] for game in self.games]
        self.venue_in_use = [self.model.NewBoolVar("Use {}?".format(game)) for game in self.games]
        self.num_games_vs: typing.Dict[typing.Tuple, cp_model.IntVar] = {tuple(sorted(_teams)): self.model.NewIntVar(0, len(self.teams),
                                " vs ".join([str(t) for t in _teams]))
                             for _teams in itertools.combinations(self.teams, self.num_teams_per_game)}
        self.num_games_vars: typing.List[cp_model.IntVar] = []
        self.temp_variables: typing.List[cp_model.IntVar] = []

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

    def disallow_double_headers(self):
        if ScheduleOptimizer.Constraints.NoDoubleHeaders in self.constraints:
            return
        dates = set(game.game_start.date() for game in self.games).union(game.game_end.date() for game in self.games)
        for date in dates:
            same_day_games = [g for g, game in enumerate(self.games) if game.game_start.date() == date or game.game_end.date() == date]
            for t, team in enumerate(self.teams):
                self.model.Add(sum(self.schedule[g][t] for g in same_day_games) == 1)
        self.constraints.add(ScheduleOptimizer.Constraints.NoDoubleHeaders)

    def maximize_games_objective(self, weight: float = 1.0):
        if ScheduleOptimizer.Constraints.ExactNumGames in self.objectives:
            raise RuntimeError("Cannot add an optimization objective to maximize the number of games when the number of games is a constraint")
        objective_fn: cp_model.LinearExpr = sum(sum(self.schedule[d]) for d in range(len(self.games)))
        self.objectives[ScheduleOptimizer.Objectives.MaximizeNumGames] = {"weight": weight, "objective": objective_fn}

    def require_num_games(self, num_games: int):
        if ScheduleOptimizer.Objectives.MaximizeNumGames in self.objectives:
            raise RuntimeError("Cannot require a specific number of games if an optimization objective is to maximize the number of games")
        if not ScheduleOptimizer.Constraints.ExactlyEqualGames in self.constraints:
            self.equal_games_constraint(exact=True)
        self.num_games_vars = [self.model.Add(v == num_games) for v in self.num_games_vars]
        self.constraints.add(ScheduleOptimizer.Constraints.ExactNumGames)

    def solve(self):
        self.model.Maximize(sum(v["weight"] * v["objective"] for v in self.objectives.values()))
        print("Model valid:", self.model.Validate())
        solver = cp_model.CpSolver()
        solver.log_callback = lambda s: print("Callback", s)
        status = solver.Solve(self.model)

        print("Solution Info:", solver.SolutionInfo())
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            assignment = [[team for t, team in enumerate(self.teams) if solver.Value(self.schedule[g][t]) == 1] for g in range(len(self.games))]
            print("\n".join(["{}: {}".format(game, " vs ".join(str(t) for t in assignment[g])) for g, game in enumerate(self.games)]))
            print("\n".join("{}: {}".format(v, solver.Value(v)) for v in self.num_games_vs.values()))
            print("Solution Strength:", solver.ObjectiveValue())
            return assignment
        else:
            raise RuntimeError("No solution found!")

