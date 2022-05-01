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
from typing import Set, Any, Dict

NONE_TYPE = "NONE"
BOOL_TYPE = "BOOL"
NUM_TYPE = "NUM"
BYTE_TYPE = "BYTE"
STR_TYPE = "STR"

BASIC_TYPES = (NONE_TYPE, BOOL_TYPE, NUM_TYPE, BYTE_TYPE, STR_TYPE)


class Value:
    def __init__(self):
        self.heap_types: Set[int] = set()
        self.prim_types: Set[str] = set()
        self.func_types: Set[int] = set()
        self.class_types: Dict[int, Dict[str, Value]] = {}

    def __repr__(self):
        return "Value is: {} x {} x {} x {}".format(
            self.heap_types, self.prim_types, self.func_types, self.class_types
        )

    def inject_prim_type(self, type_to_be_injected: str):
        self.prim_types.add(type_to_be_injected)

    def inject_func_type(self, label: int):
        self.func_types.add(label)

    def inject_class_type(self, label: int, frame):
        self.class_types[label] = frame

    def class_types_issubset(self, other: Dict[int, Dict[str, Value]]):
        mine = self.class_types
        for label in mine:
            if label not in other:
                return False
            mine_values = mine[label]
            other_values = other[label]
            for key in mine_values:
                if key not in other_values:
                    return False
                if not mine_values[key].issubset(other_values[key]):
                    return False

        return True

    def class_types_update(self, other: Dict[int, Dict[str, Value]]):
        mine = self.class_types
        for label in other:
            if label not in mine:
                mine[label] = other[label]
                continue
            mine_values = mine[label]
            other_values = other[label]
            for key in other_values:
                if key not in mine_values:
                    mine_values[key] = other_values[key]
                else:
                    mine_values[key].update(other_values[key])

        return self

    def issubset(self, other: Value):
        return (
            self.heap_types.issubset(other.heap_types)
            and self.prim_types.issubset(other.prim_types)
            and self.func_types.issubset(other.func_types)
            and self.class_types_issubset(other.class_types)
        )

    def update(self, other: Value):
        self.heap_types.update(other.heap_types)
        self.prim_types.update(other.prim_types)
        self.func_types.update(other.func_types)
        self.class_types_update(other.class_types)
        return self
