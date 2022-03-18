import argparse
import datetime
import numpy as np
import pathlib
import sys
import typing

from Game import Game
from Team import Team, read_team_csv
from Weekday import Weekday
from Venue import Venue, Sheet
from Schedule import Schedule

import utilities


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="A script for generating draw schedules for curling")
    parser.add_argument("--start-date", dest="start_date", type=datetime.date.fromisoformat, required=True)
    parser.add_argument("--end-date", dest="end_date", type=datetime.date.fromisoformat, required=True)
    parser.add_argument("--draw-time", dest="draw_times", default=[], action='extend', nargs='+',
                                           type=lambda t: datetime.datetime.strptime(t, "%H:%M").time())
    parser.add_argument("--draw-duration", dest="draw_duration", required=True, type=utilities.timedelta_from_str)
    parser.add_argument("--weekday", dest="weekdays", type=Weekday.from_str, default=[], action='extend', nargs='*')
    parser.add_argument("--sheets", dest="sheets", type=int, required=True)
    parser.add_argument("--required-num-games", dest="num_games", type=int, default=None)
    parser.add_argument("--blackout-times", dest="blackout_times", type=pathlib.Path, default=None)
    parser.add_argument("--draw-schedule", dest="draw_schedule", type=pathlib.Path)
    parser.add_argument("--output-schedule", dest="output_schedule", type=pathlib.Path, default=None)
    parser.add_argument("--team-csv", dest="team_csv", type=pathlib.Path, required=True)
    args = parser.parse_args()

    teams: typing.Optional[typing.List[Team]] = None
    if args.team_csv is not None:
        teams = read_team_csv(args.team_csv)

    schedule: Schedule
    if args.draw_schedule is not None:
        schedule = Schedule.from_csv(args.draw_schedule, teams)
    else:
        schedule = Schedule.naive_schedule(start_date=args.start_date, end_date=args.end_date,
                game_times=args.draw_times, weekdays=args.weekdays,
                game_length=args.draw_duration, venues=[Sheet(s) for s in range(args.sheets)])
    if not schedule.teams_assigned() or True:
        if teams is None or len(teams) == 0:
            raise RuntimeError("No teams to schedule!")
        schedule.assign(teams, args.num_games)

    games_against = schedule.games_against_matrix()
    teams = sorted(list(schedule.teams()))
    for i, team in enumerate(teams):
        print(team.name, np.sum(games_against[:, i]), "|", games_against[:, i])
    if args.output_schedule is not None:
        schedule.to_csv(args.output_schedule)
