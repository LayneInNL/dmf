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

import ast
import logging
from collections import defaultdict
from typing import Set, Dict, List, Tuple

from dmf.analysis.prim import (
    PrimType,
    PRIM_STR,
    PRIM_BYTE,
    PRIM_NUM,
    PRIM_BOOL,
    PRIM_NONE,
)
from dmf.analysis.utils import issubset, update

# None to denote TOP type. it can save memory consumption.
VALUE_TOP = None


def static_c3(class_object):
    if class_object is builtin_object:
        return [class_object]
    return [class_object] + static_merge(
        [static_c3(base) for base in class_object.bases]
    )


def static_merge(mro_list):
    if not any(mro_list):
        return []
    for candidate, *_ in mro_list:
        if all(candidate not in tail for _, *tail in mro_list):
            return [candidate] + static_merge(
                [
                    tail if head is candidate else [head, *tail]
                    for head, *tail in mro_list
                ]
            )
    else:
        raise TypeError("No legal mro")


class FuncObj:
    def __init__(
        self, label: int, entry_label: int, exit_label: int, arguments: ast.arguments
    ):
        self.label = label
        self.entry_label = entry_label
        self.exit_label = exit_label
        self.arguments = arguments

    def __eq__(self, other: FuncObj):
        return self.label == other.label

    def __hash__(self):
        return self.label

    def __repr__(self):
        return "({}, {}, {}, {}".format(
            self.label, self.entry_label, self.exit_label, self.arguments
        )


class ClsObj:
    def __init__(
        self, label: int, name: str, bases: List[ClsObj], attributes: Dict[str, Value]
    ):
        self.label = label
        self.name: str = name
        self.bases: List[ClsObj] = bases
        self.attributes = attributes
        if bases:
            self.mro = static_c3(self)

    def __repr__(self):
        return "name: {} x dict: {}".format(self.name, self.attributes.__repr__())

    def __le__(self, other: ClsObj):
        return issubset(self.attributes, other.attributes)

    def __iadd__(self, other: ClsObj):
        return update(self.attributes, other.attributes)

    def __getitem__(self, attribute: str):
        if attribute in self.attributes:
            return self.attributes[attribute]

        for base in self.mro:
            if attribute in base.attributes:
                return base.attributes[attribute]

        raise AttributeError

    def __eq__(self, other: ClsObj):
        return self.label == other.label

    def __hash__(self):
        return self.label


builtin_object = ClsObj(0, "object", [], {})


# in order to denote TOP, we need a special value. Since python doesn't support algebraic data types,
# we have to use functions outside class to do operations.


class Value:
    def __init__(self):
        self.heap_types: Set[int] = set()
        self.prim_types: Set[PrimType] = set()
        self.func_types: Set[FuncObj] = set()
        self.class_types: Set[ClsObj] = set()

    def __le__(self, other: Value):

        res1 = self.heap_types <= other.heap_types
        res2 = self.prim_types <= other.prim_types
        res3 = self.func_types <= other.func_types
        res4 = self.class_types <= other.class_types
        return all((res1, res2, res3, res4))

    def __iadd__(self, other: Value):
        self.heap_types |= other.heap_types
        self.prim_types |= other.prim_types
        self.func_types |= other.func_types
        self.class_types |= other.class_types
        return self

    def __repr__(self):
        return "{} x {} x {} x {}".format(
            self.heap_types, self.prim_types, self.func_types, self.class_types
        )

    def inject_heap_type(self, heap_ctx: int):
        self.heap_types.add(heap_ctx)

    def inject_none(self):
        self.prim_types.add(PRIM_NONE)

    def inject_bool(self):
        self.prim_types.add(PRIM_BOOL)

    def inject_num(self):
        self.prim_types.add(PRIM_NUM)

    def inject_byte(self):
        self.prim_types.add(PRIM_BYTE)

    def inject_str(self):
        self.prim_types.add(PRIM_STR)

    def inject_func_type(self, label: int, entry_label, exit_label, arguments):
        func_obj = FuncObj(label, entry_label, exit_label, arguments)
        self.func_types.add(func_obj)

    def inject_class_type(self, label, name, bases, frame: Dict[str, Value]):
        class_object: ClsObj = ClsObj(label, name, bases, frame)
        self.class_types.add(class_object)

    def extract_heap_types(self):
        return self.heap_types

    def extract_prim_types(self):
        return self.prim_types

    def extract_func_types(self):
        return self.func_types

    def extract_class_types(self):
        return self.class_types


class ValueDict(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)

    def __le__(self, other: ValueDict):
        for key in self:
            if key not in other:
                return False
            if not issubset_value(self[key], other[key]):
                return False
        return True

    def __iadd__(self, other: ValueDict):
        for key in other:
            self[key] = update_value(self[key], other[key])
        return self

    def hybrid_copy(self):
        copied = ValueDict(lambda: VALUE_TOP)
        copied.update(self)
        return copied


def issubset_value(value1: Value | VALUE_TOP, value2: Value | VALUE_TOP):
    if value2 == VALUE_TOP:
        return True
    if value1 == VALUE_TOP:
        return False
    return value1 <= value2


def update_value(value1: Value | VALUE_TOP, value2: Value | VALUE_TOP):
    if value1 == VALUE_TOP or value2 == VALUE_TOP:
        return VALUE_TOP
    else:
        value1 += value2
        return value1
