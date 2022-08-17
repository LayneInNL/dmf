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

from typing import Union

from dmf.analysis.special_types import Any


class Value:
    def __init__(self, *, any=False):
        self.types: Union[Any, dict]
        if any:
            self.types = Any
        else:
            self.types = {}

    def __le__(self, other: Value) -> bool:
        if other.types == Any:
            return True
        if self.types == Any:
            return False

        for k in self.types:
            if k not in other.types:
                return False
            elif not self.types[k] <= other.types[k]:
                return False
        return True

    def __iadd__(self, other: Value) -> Value:
        if self.types == Any or other.types == Any:
            self.types = Any
            return self

        for k in other.types:
            if k not in self.types:
                self.types[k] = other.types[k]
            else:
                self.types[k] += other.types[k]
        return self

    def __repr__(self):
        return self.types.__repr__()

    def __iter__(self):
        return iter(self.types.values())

    def inject_type(self, type):
        if self.types is Any or type is Any:
            self.types = Any
        else:
            self.types[type.tp_uuid] = type

    def inject_value(self, value: Value):
        if self.is_Any() or value.is_Any():
            self.types = Any
            return

        for label, type in value.types.items():
            if label not in self.types:
                self.types[label] = type
            else:
                self.types[label] += type

    def values(self):
        return self.types.values()

    def is_Any(self) -> bool:
        return self.types is Any


def create_value_with_type(typ) -> Value:
    value = Value()
    value.inject_type(typ)
    return value
