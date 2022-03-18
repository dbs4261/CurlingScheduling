import datetime
import typing

from Team import Team
from Venue import Venue
from Game import Game
from Weekday import Weekday
from Schedule import Schedule


class League(object):
    def __init__(self, teams: typing.Optional[typing.List[Team]] = None,
                 venues: typing.Optional[typing.List[Venue]] = None,
                 games_per_team: typing.Optional[int] = None,
                 schedule: Schedule = None):
        self.teams: typing.List[Team] = teams if teams is not None else []
        self.venues: typing.List[Venue] = venues if venues is not None else []
        self.games_per_team: typing.Optional[int] = games_per_team
        self.schedule = schedule
        if self.schedule is not None:
            self.teams = list(self.schedule.teams().union(self.teams))
            self.venues = list(self.schedule.venues().union(self.venues))
            if len(self.schedule.venues()) == 0 and not self.schedule.teams_assigned():
                self.schedule.populate_venues(self.venues)

    def sports_engine_export(self):
        raise NotImplementedError("sports_engine_export not implemented")
