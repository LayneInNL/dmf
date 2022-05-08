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

from typing import Tuple, Dict

from dmf.analysis.state import State
from dmf.analysis.utils import issubset

LATTICE_BOT = None


class Lattice:
    def __init__(self, lattice: Lattice = None):
        self.internal: Dict[Tuple, State] = {}
        if lattice is not None:
            for ctx, state in lattice.items():
                self.internal[ctx] = state.copy()

    def __setitem__(self, ctx, state):
        self.internal[ctx] = state

    def __getitem__(self, context):
        return self.internal[context]

    def __delitem__(self, context):
        del self.internal[context]

    def __contains__(self, context):
        return context in self.internal

    def __le__(self, other: Lattice):

        return issubset(self.internal, other.internal)

    def __add__(self, other: Lattice):
        for context in other.internal:
            if context not in self.internal:
                self.internal[context] = other.internal[context]
            else:
                self.internal[context] += other.internal[context]

        return self

    def __repr__(self):
        return self.internal.__repr__()

    def items(self):
        return self.internal.items()

    def keys(self):
        return self.internal.keys()

    def values(self):
        return self.internal.values()

    def copy(self):
        copied: Lattice = Lattice(self)
        return copied


def issubset_lattice(lattice1: Lattice | LATTICE_BOT, lattice2: Lattice | LATTICE_BOT):
    if lattice1 == LATTICE_BOT:
        return True

    if lattice2 == LATTICE_BOT:
        return False

    return lattice1 <= lattice2


def update_lattice(lattice1: Lattice, lattice2: Lattice | LATTICE_BOT):
    if lattice2 == LATTICE_BOT:
        return lattice1

    lattice1 += lattice2
    return lattice1
