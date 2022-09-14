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
from dmf.analysis.namespace import LocalVar
from dmf.analysis.special_types import Any
from dmf.analysis.value import Value


class HeapNamespace(dict):
    def __missing__(self, key):
        self[key] = value = Value()
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

    def __contains__(self, name: str):
        for var in self:
            if name == var.name:
                return True
        return False

    def read_value(self, name: str) -> Value:
        for var, val in self.items():
            if name == var.name:
                return val
        raise AttributeError(name)

    def write_local_value(self, name: str, value: Value):
        assert isinstance(value, Value), value
        self[LocalVar(name)] = value

    def del_local_var(self, name: str):
        del self[LocalVar(name)]


class SizedHeapNamespace:
    threshold = 5

    def threshold_check(self):
        if self.types is Any:
            return
        elif len(self.types) > self.threshold:
            self.types = Any
        else:
            pass

    def __init__(self):
        self.types: HeapNamespace | Any = HeapNamespace()

    def __repr__(self):
        return repr(self.types)

    def __le__(self, other: SizedHeapNamespace):
        if self.types is Any:
            return True
        elif other.types is Any:
            return False
        else:
            for var in self.types:
                if not self.types[var] <= other.types[var]:
                    return False
        return True

    def __iadd__(self, other: SizedHeapNamespace):
        if self.types is Any:
            return self
        elif other.types is Any:
            self.types = Any
        else:
            for var in other.types:
                self.types[var] += other.types[var]
        self.threshold_check()
        return self

    def __contains__(self, name: str):
        if self.types is Any:
            return True
        else:
            for var in self.types:
                if name == var.name:
                    return True
        return False

    def read_value(self, name: str) -> Value:
        if self.types is Any:
            return Value.make_any()

        for var, val in self.types.items():
            if name == var.name:
                return val
        raise AttributeError(name)

    def write_local_value(self, name: str, value: Value):
        assert isinstance(value, Value), value
        if self.types is Any:
            return None
        else:
            self.types[LocalVar(name)] = value
        self.threshold_check()

    def del_local_var(self, name: str):
        if self.types is Any:
            return None
        else:
            del self.types[LocalVar(name)]
