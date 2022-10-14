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


class Value:
    threshold = 5

    def threshold_check(self):
        if self.types is Any:
            return
        elif len(self.types) > self.threshold:
            self.types = Any

    @classmethod
    def make_any(cls) -> Value:
        return cls(any=True)

    def is_any(self):
        return self.types is Any

    def __init__(self, *, any=False):
        self.types: Any | dict
        if any:
            self.types = Any
        else:
            self.types = {}

    def __len__(self):
        if self.types is Any:
            return self.threshold + 1
        else:
            return len(self.types)

    def __le__(self, other: Value) -> bool:
        if other.types is Any:
            return True
        if self.types is Any:
            return False
        for k in self.types:
            if k not in other.types:
                return False
            elif not self.types[k] <= other.types[k]:
                return False
        return True

    def __iadd__(self, other: Value) -> Value:
        if self.types is Any:
            return self
        elif other.types is Any:
            self.types = Any
            return self
        else:
            for k in other.types:
                if k not in self.types:
                    self.types[k] = other.types[k]
                else:
                    self.types[k] += other.types[k]
            self.threshold_check()
            return self

    def __repr__(self):
        # return self.types.__repr__()
        if self.types is Any:
            return repr(Any)
        else:
            formatted = list(self.types.values())
            return repr(formatted)

    def __iter__(self):
        return iter(self.types.values())

    def inject(self, other):
        if isinstance(other, Value):
            self.inject_value(other)
        else:
            self.inject_type(other)

    def inject_type(self, type):
        # itself is Any, do nothing
        if self.types is Any:
            return

        # want to insert Any
        if type is Any:
            self.types = Any
            return

        if type.tp_uuid in self.types:
            self.types[type.tp_uuid] += type
        else:
            self.types[type.tp_uuid] = type

        self.threshold_check()

    def inject_value(self, value: Value):
        if self.types is Any:
            return

        if value.types is Any:
            self.types = Any
            return

        for label, type in value.types.items():
            if label not in self.types:
                self.types[label] = type
            else:
                self.types[label] += type

        self.threshold_check()

    def value_2_list(self):
        return list(self.types.values())

    def extract_1_elt(self):
        assert len(self) == 1
        return self.value_2_list()[0]


def type_2_value(type) -> Value:
    value = Value()
    value.inject(type)
    return value
