#  Copyright 2022 Layne Liu
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from __future__ import annotations

import logging
from typing import Set

from .state.space import Obj
from .state.types import PrimitiveTypes


class BoolLattice:
    BOT = 1
    FALSE = 2
    TRUE = 4
    TOP = 8

    mapping = {PrimitiveTypes.BOOL_TRUE: TRUE, PrimitiveTypes.BOOL_FALSE: FALSE}
    format_mapping = {
        BOT: "Top",
        FALSE: "False",
        TRUE: "True",
        TOP: "Top",
    }

    def __init__(self):
        self.value = self.BOT

    # 2 BOT
    # 3, 4 FALSE
    # 5, 8 TRUE
    # 6, 9, 10, 12, 16 TOP
    def join(self, other: int):
        value = self.value + other
        logging.debug("value is {}".format(value))
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
        return "{}".format(self.format_mapping[self.value])


class NoneLattice:
    BOT = 1
    NONE = 2
    mapping = {PrimitiveTypes.NONE: NONE}
    format_mapping = {NONE: "None", BOT: "Bot"}

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
        return "{}".format(self.format_mapping[self.value])


class NumLattice:
    NEG = {1}
    ZERO = {2}
    NEG_ZERO = {1, 2}
    POS = {4}
    POS_ZERO = {2, 4}
    NEG_ZERO_POS = {1, 2, 4}
    symbol_mapping = {1: "-", 2: "0", 4: "+"}
    mapping = {
        PrimitiveTypes.NUM_NEGATIVE: NEG,
        PrimitiveTypes.NUM_ZERO: ZERO,
        PrimitiveTypes.NUM_POSITIVE: POS,
    }

    def __init__(self):
        self.value: Set[int] = set()

    def join(self, other: Set):
        self.value |= other

    def merge(self, other: NumLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: NumLattice):
        return self.value.issubset(other.value)

    def __repr__(self):
        rep = "(Symbol: "
        for elt in self.value:
            rep += "{} ".format(self.symbol_mapping[elt])
        rep += ")"
        return rep


class StrLattice:
    BOT = 1
    EMPTY = 2
    NON_EMPTY = 4
    TOP = 8
    mapping = {PrimitiveTypes.STR_EMPTY: EMPTY, PrimitiveTypes.STR_NON_EMPTY: NON_EMPTY}
    format_mapping = {
        BOT: "Bot",
        EMPTY: "Empty",
        NON_EMPTY: "NonEmpty",
        TOP: "Top",
    }

    def __init__(self):
        self.value: int = self.BOT

    #            BOT EMPTY NONEMPTY TOP
    # BOT          2    3    5        9
    # EMPTY        3    4    6        10
    # NONEMPTY     5    6    8        12
    # TOP          9    10   12       16
    def join(self, other: int):
        value = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.EMPTY
        elif value in [5, 8]:
            self.value = self.NON_EMPTY
        else:
            self.value = self.TOP

    def merge(self, other: StrLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: StrLattice):
        if self.value == self.NON_EMPTY and other.value == self.EMPTY:
            return False

        return self.value <= other.value

    def __repr__(self):
        return self.format_mapping[self.value]


class UndefLattice:
    BOT = 1
    UNDEF = 2
    mapping = {PrimitiveTypes.UNDEF: UNDEF}
    format_mapping = {UNDEF: "Undef", BOT: "Bot"}

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
            self.value = self.UNDEF

    def merge(self, other: UndefLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: UndefLattice):
        return self.value <= other.value

    def __repr__(self):
        return "{}".format(self.format_mapping[self.value])


class VarLattice:
    def __init__(self):
        self.bool_lattice: BoolLattice = BoolLattice()
        self.none_lattice: NoneLattice = NoneLattice()
        self.num_lattice: NumLattice = NumLattice()
        self.str_lattice: StrLattice = StrLattice()

    def transform(self, obj: Obj):
        heap_context, fields = obj
        if heap_context in [PrimitiveTypes.BOOL_TRUE, PrimitiveTypes.BOOL_FALSE]:
            self.bool_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [PrimitiveTypes.NONE]:
            self.none_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [
            PrimitiveTypes.NUM_NEGATIVE,
            PrimitiveTypes.NUM_ZERO,
            PrimitiveTypes.NUM_POSITIVE,
        ]:
            self.num_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [PrimitiveTypes.STR_EMPTY, PrimitiveTypes.STR_NON_EMPTY]:
            self.str_lattice.from_heap_context_to_lattice(heap_context)

    def is_subset(self, other: VarLattice):
        return (
            self.bool_lattice.is_subset(other.bool_lattice)
            and self.none_lattice.is_subset(other.none_lattice)
            and self.num_lattice.is_subset(other.num_lattice)
            and self.str_lattice.is_subset(other.str_lattice)
        )

    def merge(self, other: VarLattice):
        self.bool_lattice.merge(other.bool_lattice)
        self.none_lattice.merge(other.none_lattice)
        self.num_lattice.merge(other.num_lattice)
        self.str_lattice.merge(other.str_lattice)

    def __repr__(self):
        bool_lattice_str = self.bool_lattice.__repr__()
        none_lattice_str = self.none_lattice.__repr__()
        num_lattice_str = self.num_lattice.__repr__()
        str_lattice_str = self.str_lattice.__repr__()
        return "Lattice: Bool x None x Num x Str: {} x {} x {} x {}".format(
            bool_lattice_str, none_lattice_str, num_lattice_str, str_lattice_str
        )
