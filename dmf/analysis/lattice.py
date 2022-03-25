from enum import Enum


class BoolLattice(Enum):
    BOT = 1
    FALSE = 2
    TRUE = 4
    TOP = 8

    def __init__(self):
        self.value = self.BOT

    # 2 BOT
    # 3 4 FALSE
    # 5 8 TRUE
    # 6, 9, 10, 12, 16 TOP
    def union(self, other):
        value = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.FALSE
        elif value in [5, 8]:
            self.value = self.TRUE
        else:
            self.value = self.TOP

    def is_subset(self, other):
        return self.value < other
