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
from dmf.analysis.special_types import Any
from dmf.analysis.value import Value


class HeapNamespace(dict):
    ...


class SizedHeapNamespace:
    threshold = 10

    def threshold_check(self):
        if self.types is Any:
            return
        elif len(self.types) > self.threshold:
            self.types = Any

    def __init__(self):
        self.types: HeapNamespace | Any = HeapNamespace()

    def __repr__(self):
        return repr(self.types)

    def __contains__(self, name: str):
        if self.types is Any:
            return True
        if name in self.types:
            return True
        return False

    def read_value(self, name: str) -> Value:
        if self.types is Any:
            return Value.make_any()

        if name not in self.types:
            raise AttributeError(name)

        value = Value()
        value.inject(self.types[name])
        return value

    def write_local_value(self, name: str, value: Value):
        assert isinstance(value, Value), value
        if self.types is Any:
            return

        new_value = Value()
        new_value.inject(value)
        if name in self.types:
            old_value = self.types[name]
            new_value.inject(old_value)
        self.types[name] = new_value
        self.threshold_check()

    def overwirte_local_value(self, name: str, value: Value):
        assert isinstance(value, Value), value
        if self.types is Any:
            return

        new_value = Value()
        new_value.inject(value)
        self.types[name] = new_value
        self.threshold_check()
