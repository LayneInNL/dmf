from __future__ import annotations
import logging
from typing import Set, Tuple, Any
from .state.types import PrimitiveTypes


class BoolLattice:
    BOT = 1
    FALSE = 2
    TRUE = 4
    TOP = 8

    mapping = {PrimitiveTypes.BOOL_TRUE: TRUE, PrimitiveTypes.BOOL_FALSE: FALSE}

    def __init__(self):
        self.value = self.BOT

    # 2 BOT
    # 3, 4 FALSE
    # 5, 8 TRUE
    # 6, 9, 10, 12, 16 TOP
    def join(self, other: int):
        value = self.value + other
        logging.debug('value is {}'.format(value))
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.FALSE
        elif value in [5, 8]:
            self.value = self.TRUE
        else:
            self.value = self.TOP

    def merge(self, other: BoolLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: BoolLattice):
        if self.value == self.FALSE and other.value == self.TRUE:
            return False

        return self.value <= other.value

    def __repr__(self):
        rep = None
        if self.value == self.TOP:
            rep = 'TOP'
        elif self.value == self.TRUE:
            rep = 'TRUE'
        elif self.value == self.FALSE:
            rep = 'FALSE'
        elif self.value == self.BOT:
            rep = 'BOT'
        return '{}'.format(rep)


class NoneLattice:
    BOT = 1
    NONE = 2
    mapping = {PrimitiveTypes.NONE: NONE}

    def __init__(self):
        self.value = self.BOT

    # V  1   2
    # 1  2   3
    # 2  3   4
    def join(self, other: int):
        value = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.NONE

    def merge(self, other: NoneLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: NoneLattice):
        return self.value <= other.value

    def __repr__(self):
        rep = None
        if self.value == self.NONE:
            rep = 'None'
        elif self.value == self.BOT:
            rep = 'BOT'
        return '{}'.format(rep)


class VarLattice:
    def __init__(self):
        self.bool_lattice: BoolLattice = BoolLattice()
        self.none_lattice: NoneLattice = NoneLattice()

    def transform(self, objs: Set[Tuple[int, Any]]):
        for heap_context, fields in objs:
            if heap_context in [PrimitiveTypes.BOOL_TRUE, PrimitiveTypes.BOOL_FALSE]:
                self.bool_lattice.from_heap_context_to_lattice(heap_context)
            elif heap_context in [PrimitiveTypes.NONE]:
                self.none_lattice.from_heap_context_to_lattice(heap_context)

    def is_subset(self, other: VarLattice):
        return self.bool_lattice.is_subset(other.bool_lattice) and \
               self.none_lattice.is_subset(other.none_lattice)

    def merge(self, other: VarLattice):
        self.bool_lattice.merge(other.bool_lattice)
        self.none_lattice.merge(other.none_lattice)

    def __repr__(self):
        bool_lattice_str = self.bool_lattice.__repr__()
        none_lattice_str = self.none_lattice.__repr__()
        return 'Lattice: Bool x None: {} x {}'.format(bool_lattice_str, none_lattice_str)
