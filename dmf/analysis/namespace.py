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

import sys

from dmf.analysis.symbol_table import Var, NonlocalVar, GlobalVar, LocalVar, SymbolTable
from dmf.analysis.value import Value


class Namespace(SymbolTable):
    def __contains__(self, item):
        if isinstance(item, str):
            raise NotImplementedError
        return super().__contains__(item)

    def contains(self, name: str):
        if (
            LocalVar(name) in self
            or NonlocalVar(name) in self
            or GlobalVar(name) in self
        ):
            return True
        return False

    def __repr__(self):
        filtered_dict = {
            key: value for key, value in self.items() if not key.name.startswith("_var")
        }
        return repr(filtered_dict)

    def __missing__(self, key):
        self[key] = value = Value.make_any()
        return value

    def __le__(self, other):
        for var in self:
            if not self[var] <= other[var]:
                return False
        return True

    def __iadd__(self, other):
        for var in other:
            self[var] += other[var]
        return self

    def read_var_type(self, name: str) -> Var:
        if LocalVar(name) in self:
            return LocalVar(name)
        if NonlocalVar(name) in self:
            return NonlocalVar(name)
        if GlobalVar(name) in self:
            return GlobalVar(name)

        raise AttributeError(name)

    def read_value(self, name: str) -> Value:
        if LocalVar(name) in self:
            return self[LocalVar(name)]
        if NonlocalVar(name) in self:
            return self[NonlocalVar(name)]
        if GlobalVar(name) in self:
            return self[GlobalVar(name)]
        raise AttributeError(name)

    def write_local_value(self, name: str, value: Value):
        assert isinstance(value, Value), value
        self[LocalVar(name)] = value

    def write_nonlocal_value(self, name: str, ns: Namespace):
        self[NonlocalVar(name)] = ns

    def write_global_value(self, name: str, ns: Namespace):
        self[GlobalVar(name)] = ns

    def del_local_var(self, name: str):
        del self[LocalVar(name)]


sys.analysis_typeshed_modules = Namespace()
