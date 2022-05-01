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

from dmf.analysis.State import State


class Lattice:
    def __init__(self):
        self.lattice: Dict[Tuple, State] = {}

    def __setitem__(self, context, state):
        self.lattice[context] = state

    def __getitem__(self, context):
        return self.lattice[context]

    def __delitem__(self, context):
        del self.lattice[context]

    def __contains__(self, context):
        return context in self.lattice

    def __le__(self, other: Lattice):
        for context in self.lattice:
            if context not in other.lattice:
                return False
            if not self.lattice[context].issubset(other.lattice[context]):
                return False
        return True

    def __repr__(self):
        return self.lattice.__repr__()

    def items(self):
        return self.lattice.items()

    def keys(self):
        return self.lattice.keys()

    def values(self):
        return self.lattice.values()

    def issubset(self, other: Lattice | None):
        return self.__le__(other)

    def update(self, other: Lattice | None):
        if other is None:
            return self
        for context in other.lattice:
            if context not in self.lattice:
                self.lattice[context] = other.lattice[context]
            else:
                self.lattice[context].update(other.lattice[context])

        return self

    def hybrid_copy(self):
        copied: Lattice = Lattice()
        for context, state in self.lattice.items():
            copied[context] = state.hybrid_copy()
        return copied


def issubset(lattice1: Lattice, lattice2: Lattice):
    if lattice1 is None:
        return True
    if lattice2 is None:
        return False
    return lattice1.issubset(lattice2)
