from __future__ import annotations
import logging
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
    def union(self, other: int):
        value = self.value + other
        logging.debug('value is {}'.format(value))
        if value in [2]:
            self.value = Value.BOT
        elif value in [3, 4]:
            self.value = Value.FALSE
        elif value in [5, 8]:
            self.value = Value.TRUE
        else:
            self.value = Value.TOP

    def merge(self, other: BoolLattice):
        self.union(other.value)

    def transform(self, objects: Set[Tuple[int, Tuple]]):
        for hcontext, _ in objects:
            logging.debug('hcontext {}'.format(hcontext))
            if hcontext == -7:
                other = Value.FALSE
                self.union(other)
            elif hcontext == -6:
                other = Value.TRUE
                self.union(other)

    def __eq__(self, other: BoolLattice):
        return self.value == other.value

    def __ne__(self, other: BoolLattice):
        return not self.__eq__(other)

    def is_subset(self, other: BoolLattice):
        if self.value == Value.FALSE and other.value == Value.TRUE:
            return False

        return self.value <= other.value

    def __repr__(self):
        if self.value == 8:
            repr = 'TOP'
        elif self.value == 4:
            repr = 'TRUE'
        elif self.value == 2:
            repr = 'FALSE'
        elif self.value == 1:
            repr = 'BOT'
        return 'Bool Lattice Value: {}'.format(repr)


class Lattice:
    def __init__(self):
        self.bool_lattice = BoolLattice()
