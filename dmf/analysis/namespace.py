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

from collections import defaultdict

from dmf.analysis.value import Value
from dmf.analysis.variables import SpecialVar, Var, LocalVar, NonlocalVar, GlobalVar


class Namespace(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)

    def __missing__(self, key):
        self[key] = value = Value(top=True)
        return value

    # we use defaultdict, the default value of an unknown variable is TOP
    # So we have to collect all variables
    def __le__(self, other):
        variables = filter(
            lambda elt: not isinstance(elt, SpecialVar),
            self.keys() | other.keys(),
        )
        for var in variables:
            if not self[var] <= other[var]:
                return False
        return True

    def __iadd__(self, other):
        variables = filter(
            lambda elt: not isinstance(elt, SpecialVar),
            self.keys() | other.keys(),
        )
        for var in variables:
            self[var] += other[var]
        return self

    def __contains__(self, name: str):
        # __xxx__ and Var
        for var in self:
            if name == var.name:
                return True
        return False

    def read_var_type(self, name: str) -> Var:
        for var, _ in self.items():
            if name == var.name:
                return var

    def read_value(self, name: str) -> Value:
        for var, val in self.items():
            if name == var.name:
                return val

    def write_local_value(self, name: str, value: Value):
        self[LocalVar(name)] = value

    def write_nonlocal_value(self, name: str, ns: Namespace):
        self[NonlocalVar(name)] = ns

    def write_global_value(self, name: str, ns: Namespace):
        self[GlobalVar(name)] = ns

    def write_special_value(self, name: str, value):
        self[SpecialVar(name)] = value

    def del_local_var(self, name: str):
        del self[LocalVar(name)]
