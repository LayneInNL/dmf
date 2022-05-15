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
from collections import defaultdict
from typing import Set, Dict, List

from dmf.analysis.prim import (
    PrimType,
    PRIM_STR,
    PRIM_BYTE,
    PRIM_NUM,
    PRIM_BOOL,
    PRIM_NONE,
)
from dmf.analysis.value_util import issubset, update

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
        return hash(self.label)

    def __repr__(self):
        return "({}, {}, {}, {}".format(
            self.label, self.entry_label, self.exit_label, self.arguments
        )


class ClsObj:
    def __init__(self, label: int, bases: List[ClsObj], attributes: Dict[str, Value]):
        self.label = label
        self.bases: List[ClsObj] = bases
        self.attributes: Dict[str, Value] = attributes
        if bases:
            self.mro: List[ClsObj] = static_c3(self)

    def __repr__(self):
        return "label: {} x dict: {}".format(self.label, self.attributes.__repr__())

    def __le__(self, other: ClsObj):
        return issubset(self.attributes, other.attributes)

    def __iadd__(self, other: ClsObj):
        update(self.attributes, other.attributes)
        return self

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

    def get_init(self):
        return self["__init__"]


builtin_object = ClsObj(0, [], {})


# in order to denote TOP, we need a special value. Since python doesn't support algebraic data types,
# we have to use functions outside class to do operations.


class Module:
    def __init__(self, module):
        self.namespace: ValueDict[str, Value | VALUE_TOP] = ValueDict(lambda: VALUE_TOP)
        self.namespace.update(module.__dict__)
        self.state = None

    def value_namespace(self):
        return self.namespace

    def set_state(self, state):
        self.state = state

    def __getitem__(self, item):
        return self.namespace[item]

    def __setitem__(self, key, value):
        self.namespace[key] = value

    def read_var_from_module(self, var):
        return self.state.read_var_from_stack(var)

    # def __repr__(self):
    #     return self.state.__repr__()

    def __le__(self, other):
        return self.state <= other.state

    def __iadd__(self, other):
        self.state += other.state
        return self


class Value:
    def __init__(self, heap_type=None):
        self.heap_types: Set[int] = set()
        if heap_type:
            self.heap_types.add(heap_type)
        self.prim_types: Set[PrimType] = set()
        self.func_types: Set[FuncObj] = set()
        self.class_types: Dict[int, ClsObj] = {}
        self.module_types: Dict[str, Module] = {}

    def __le__(self, other: Value):

        res1 = self.heap_types <= other.heap_types
        if not res1:
            return False
        res2 = self.prim_types <= other.prim_types
        if not res2:
            return False
        res3 = self.func_types <= other.func_types
        if not res3:
            return False
        for label in self.class_types:
            if label not in other.class_types:
                return False
            if not self.class_types[label] <= other.class_types[label]:
                return False
        for label in self.module_types:
            if label not in other.module_types:
                return False
            if not self.module_types[label] <= other.module_types[label]:
                return False
        return True

    def __iadd__(self, other: Value):
        self.heap_types |= other.heap_types
        self.prim_types |= other.prim_types
        self.func_types |= other.func_types
        for label in other.class_types:
            if label not in self.class_types:
                self.class_types[label] = other.class_types[label]
            else:
                self.class_types[label] += other.class_types[label]
        for label in other.module_types:
            if label not in self.module_types:
                self.module_types[label] = other.module_types[label]
            else:
                self.module_types[label] += other.module_types[label]
        return self

    def __repr__(self):
        return "{} x {} x {} x {} x {}".format(
            self.heap_types,
            self.prim_types,
            self.func_types,
            self.class_types,
            self.module_types,
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

    def inject_class_type(self, label, bases, frame: Dict[str, Value]):
        class_object: ClsObj = ClsObj(label, bases, frame)
        self.class_types[label] = class_object

    def inject_module_type(self, qualname, module):
        self.module_types[qualname] = module

    def extract_heap_types(self):
        return self.heap_types

    def extract_prim_types(self):
        return self.prim_types

    def extract_func_types(self):
        return self.func_types

    def extract_class_types(self) -> Dict[int, ClsObj]:
        return self.class_types

    def extract_module_types(self):
        return self.module_types


class ValueDict(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)

    def __le__(self, other: ValueDict):
        for key in self:
            if key.startswith("__") and key.endswith("__"):
                continue
            if key not in other:
                return False
            if not issubset_value(self[key], other[key]):
                return False
        return True

    def __iadd__(self, other: ValueDict):
        for key in other:
            if key.startswith("__") and key.endswith("__"):
                continue
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


SELF_FLAG = "self"
INIT_FLAG = "19970303"
INIT_FLAG_VALUE = Value()
RETURN_FLAG = "19951107"
