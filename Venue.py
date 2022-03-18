import functools
import typing


@functools.total_ordering
class Venue(object):
    def __init__(self, identifier: typing.Any):
        # if type(identifier).__str__ is not object.__str__:
        #     raise ValueError("ID type: {} has no __str__ method".format(type(identifier)))
        self.identifier: typing.Any = identifier

    def __str__(self) -> str:
        return str(self.identifier)

    def __repr__(self) -> str:
        return "Venue " + str(self)

    def __eq__(self, other: "Venue") -> bool:
        return issubclass(type(other), Venue) and \
               isinstance(other.identifier, type(self.identifier)) and \
               self.identifier == other.identifier

    def __lt__(self, other: "Venue") -> bool:
        if not issubclass(type(other), Venue):
            return True
        elif not isinstance(other.identifier, type(self.identifier)):
            return str(type(self.identifier)) < str(type(other.identifier))
        else:
            return self.identifier < other.identifier

    def __hash__(self):
        return hash((type(self), type(self.identifier), self.identifier))


@functools.total_ordering
class Sheet(Venue):
    use_letters: typing.ClassVar[bool] = False

    def __init__(self, val: typing.Union[int, str]):
        if isinstance(val, int):
            super(Sheet, self).__init__(val)
        elif isinstance(val, str):
            val = val.lower()
            if val.isnumeric():
                if self.use_letters:
                    super(Sheet, self).__init__(ord('a') + int(val))
                else:
                    super(Sheet, self).__init__(int(val))
            elif len(val) == 1:
                super(Sheet, self).__init__(ord(val[0]) - ord('a') + 1)
            else:
                raise ValueError("{} is not a valid Sheet ID".format(val))
        else:
            raise TypeError("type(val)={} which is neither int nor str".format(type(val)))

    def __str__(self) -> str:
        if Sheet.use_letters:
            return chr(self.identifier).upper()
        else:
            return str(self.identifier)

    def __repr__(self) -> str:
        return "Sheet " + str(self)


venue_type_registry = [Venue, Sheet]
assert(all(issubclass(c, Venue) for c in venue_type_registry))


def venue_type_from_str(type_string: str) -> typing.Type:
    for t in venue_type_registry:
        if t.__name__ == type_string:
            return t
    return Venue
