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
from typing import Union

from dmf.analysis.special_types import Any


class Value:
    threshold = 2

    @classmethod
    def make_any(cls) -> Value:
        return cls(any=True)

    def __init__(self, *, any=False):
        self.types: Union[Any, dict]
        if any:
            self.types = Any
        else:
            self.types = {}

    def __len__(self):
        if self.is_Any():
            return self.threshold + 1
        else:
            return len(self.types)

    def __le__(self, other: Value) -> bool:
        if other.is_Any():
            return True
        if self.is_Any():
            return False
        for k in self.types:
            if k not in other.types:
                return False
            elif not self.types[k] <= other.types[k]:
                return False
        return True

    def __iadd__(self, other: Value) -> Value:
        if self.is_Any() or other.is_Any():
            self.transform_to_Any()
            return self

        for k in other.types:
            if k not in self.types:
                self.types[k] = other.types[k]
            else:
                self.types[k] += other.types[k]

        if len(self.types) > self.threshold:
            self.transform_to_Any()
        return self

    def __repr__(self):
        print(self.types)
        return self.types.__repr__()

    def __iter__(self):
        return iter(self.types.values())

    def inject(self, other):
        if isinstance(other, Value):
            self.inject_value(other)
        else:
            self.inject_type(other)

    def inject_type(self, type):
        # insert Any
        if type is Any:
            self.transform_to_Any()
        elif self.is_Any():
            return
        elif len(self.types) > self.threshold:
            self.transform_to_Any()
        else:
            self.types[type.tp_qualname] = type

    def inject_value(self, value: Value):
        if self.is_Any() or value.is_Any():
            self.transform_to_Any()
            return

        for label, type in value.types.items():
            if label not in self.types:
                self.types[label] = type
            else:
                self.types[label] += type

        if len(self.types) > self.threshold:
            self.transform_to_Any()

    def values(self):
        return self.types.values()

    def is_Any(self) -> bool:
        return self.types is Any

    def transform_to_Any(self):
        self.types = Any


sys.Value = Value


def type_2_value(type) -> Value:
    if not isinstance(type, Value):
        value = Value()
        assert hasattr(type, "tp_uuid"), type
        value.inject(type)
        return value
    else:
        return type


def create_value_with_type(typ) -> Value:
    value = Value()
    value.inject_type(typ)
    return value
