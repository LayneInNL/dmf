from typing import Set, Tuple


class Value:
    BOT = 1
    FALSE = 2
    TRUE = 4
    TOP = 8


class BoolLattice:
    def __init__(self):
        self.value = Value.BOT

    # 2 BOT
    # 3, 4 FALSE
    # 5, 8 TRUE
    # 6, 9, 10, 12, 16 TOP
    def union(self, other):
        value = self.value + other
        if value in [2]:
            self.value = Value.BOT
        elif value in [3, 4]:
            self.value = Value.FALSE
        elif value in [5, 8]:
            self.value = Value.TRUE
        else:
            self.value = Value.TOP

    def is_subset(self, other):
        if other is None:
            return False
        return self.value < other

    def merge(self, other):
        self.union(other)

    def transform(self, objects: Set[Tuple]):
        for hcontext, fields in objects:
            if hcontext == -7:
                other = Value.FALSE
                self.union(hcontext)
            elif hcontext == -6:
                other = Value.TRUE
                self.union(hcontext)

    def __eq__(self, other):
        return self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if (self.value == Value.TRUE and other.value == Value.FALSE) or \
                (self.value == Value.FALSE and other.value == Value.TRUE):
            return False

        return self.value < other.value


class Lattice:
    def __init__(self):
        self.bool_lattice = BoolLattice()
