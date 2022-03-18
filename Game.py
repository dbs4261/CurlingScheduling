import datetime
import functools
import typing

import utilities
from Venue import Venue


@functools.total_ordering
class Game:
    def __init__(self, date: datetime.date, start_time: datetime.time,
                 game_length: typing.Optional[datetime.timedelta] = None,
                 venue: typing.Optional[Venue] = None):
        assert(isinstance(date, datetime.date))
        assert(isinstance(start_time, datetime.time))
        assert(game_length is None or isinstance(game_length, datetime.timedelta))
        assert(venue is None or isinstance(venue, Venue))
        self.date: datetime.date = date
        self.start_time: datetime.time = start_time
        self.game_length: typing.Optional[datetime.timedelta] = game_length
        self.venue: typing.Optional[Venue] = venue

    @staticmethod
    def header():
        return ["Start Date", "Start Time", "Game Length", "{Venue_Type}"]

    @staticmethod
    def header_venue_idx():
        return 3

    @staticmethod
    def from_csv(elements: typing.Union[str, typing.List[str]], DerivedType: typing.Type = Venue):
        if not issubclass(DerivedType, Venue):
            raise TypeError("DerivedType must be derived from Venue")
        if isinstance(elements, str):
            split_elements = [el.strip() for el in elements.strip().split(",")]
            return Game.from_string(split_elements, DerivedType=DerivedType)
        if len(elements) < len(Game.header()):
            raise ValueError("Cannot create game from string")
        date = datetime.date.fromisoformat(elements[0])
        start_time = datetime.time.fromisoformat(elements[1])
        game_length = utilities.timedelta_from_str(elements[2]) if len(elements) > 2 else None
        venue = DerivedType(elements[3]) if len(elements) > 3 else None
        return Game(date, start_time, game_length, venue)

    def to_csv(self):
        return ", ".join([self.date.isoformat(), self.start_time.isoformat(),
                          utilities.timedelta_to_str(self.game_length) if self.game_length is not None else "",
                          str(self.venue) if self.venue is not None else ""])

    @functools.cached_property
    def game_start(self) -> datetime.datetime:
        return datetime.datetime.combine(self.date, self.start_time)

    @functools.cached_property
    def game_end(self) -> typing.Optional[datetime.datetime]:
        if self.game_length is None:
            return None
        else:
            return self.game_start + self.game_length

    def same_day(self, other: "Game") -> bool:
        return self.date == other.date or \
               self.date == other.game_end.date() or \
               self.game_end.date() == other.date or \
               self.game_end.date() == other.game_end.date()

    def overlaps(self, other: "Game") -> bool:
        if self.game_start == other.game_start or self.game_end == other.game_end:
            return True
        if self.game_start < other.game_start:
            return other.game_start < self.game_end
        else:
            return self.game_start < other.game_end

    def __str__(self) -> str:
        return "{} to {} at {}".format(self.game_start, self.game_end, self.venue)

    def __eq__(self, other: "Game") -> bool:
        return isinstance(other, Game) and \
               self.date == other.date and \
               self.start_time == other.start_time and \
               self.game_length == other.game_length and \
               self.venue == other.venue

    def __lt__(self, other: "Game") -> bool:
        if self.date == other.date:
            if self.start_time == other.start_time:
                if other.game_length is None:
                    return True
                elif self.game_length is None or self.game_length == other.game_length:
                    return self.venue < other.venue
                else:
                    return self.game_length < other.game_length
            else:
                return self.start_time < other.start_time
        else:
            return self.date < other.date
