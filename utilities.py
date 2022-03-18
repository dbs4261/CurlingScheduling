import datetime


def timedelta_from_str(s: str) -> datetime.timedelta:
    s = s.strip().split(":")
    if len(s) == 0 or len(s) > 3:
        raise TypeError("Could not parse H[:M[:S]] from string {}".format(s))
    return datetime.timedelta(hours=int(s[0]),
                              minutes=int(s[1]) if len(s) >= 2 else 0,
                              seconds=int(s[2]) if len(s) == 3 else 0)


def timedelta_to_str(td: datetime.timedelta) -> str:
    hours = td.seconds // (60 * 60)
    minutes = td.seconds % (60 * 60) // 60
    seconds = td.seconds % 60
    return "{}:{}:{}".format(hours, minutes, seconds)