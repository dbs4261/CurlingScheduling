import datetime
import enum
import typing


class Weekday(enum.IntEnum):
    Sunday = 1
    Monday = 2
    Tuesday = 3
    Wednesday = 4
    Thursday = 5
    Friday = 6
    Saturday = 7
    Sun = Sunday
    Mon = Monday
    Tu = Tuesday
    Tue = Tuesday
    Tues = Tuesday
    Wed = Wednesday
    Th = Thursday
    Thu = Thursday
    Thur = Thursday
    Thurs = Thursday
    Fri = Friday
    Sat = Saturday

    @staticmethod
    def as_list(start_on_sunday: bool = True) -> typing.List["Weekday"]:
        if start_on_sunday:
            return [Weekday.Sun, Weekday.Mon, Weekday.Tue, Weekday.Wed, Weekday.Thu, Weekday.Fri, Weekday.Sat]
        else:
            return [Weekday.Mon, Weekday.Tue, Weekday.Wed, Weekday.Thu, Weekday.Fri, Weekday.Sat, Weekday.Sun]

    @staticmethod
    def from_str(label: str) -> "Weekday":
        label = label.strip()
        if label[-1] == '.':
            label = label[:-1]
        label = label.lower()
        label[0] = label[0].upper()
        return Weekday[label]

    @staticmethod
    def from_date(date: typing.Union[datetime.datetime, datetime.date]) -> "Weekday":
        return Weekday.as_list(start_on_sunday=True)[date.isoweekday()]

    def to_index(self, iso_format: bool = True) -> int:
        return self.value - 1 if iso_format else self.value % 7

    def __str__(self, abbreviation: bool = False) -> str:
        if abbreviation:
            if self == Weekday.Tuesday:
                return self.name[:4] + '.'
            elif self == Weekday.Thursday:
                return self.name[:4] + '.'
            else:
                return self.name[:3] + '.'
        return self.name

    @staticmethod
    def Next(date: datetime.date, weekday: "Weekday") -> datetime.date:
        days_ahead = weekday.to_index() - date.isoweekday()
        if days_ahead < 0:
            days_ahead += 7
        return date + datetime.timedelta(days=days_ahead)