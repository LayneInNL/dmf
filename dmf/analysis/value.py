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
from typing import Set, Dict, List, Any, Type

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
VALUE_TOP = "TOP"


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


class FuncType:
    def __init__(self, lab, module, entry_lab, exit_lab):
        self._lab_ = lab
        self._module_ = module
        self._code_ = (entry_lab, exit_lab)
        self._dict_ = AbstractValueDict()

    def __le__(self, other: FuncType):
        return self._dict_ <= other._dict_

    def __iadd__(self, other: FuncType):
        self._dict_ += other._dict_
        return self

    def __repr__(self):
        return self._dict_.__repr__()


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
    def __init__(self, state):
        self.state = state

    def read_var_from_module(self, var):
        return self.state.read_var_from_stack(var)

    # def __repr__(self):
    #     return self.state.__repr__()

    def __le__(self, other):
        return self.state <= other.state

    def __iadd__(self, other):
        self.state += other.state
        return self


class ListType:
    def __init__(self):
        self.types: AbstractValue = AbstractValue()

    def __le__(self, other: ListType):
        return self.types <= other.types

    def __iadd__(self, other: ListType):
        self.types += other.types
        return self

    def __repr__(self):
        return self.types.__repr__()

    def append(self, other: AbstractValue):
        self.types += other

    def clear(self):
        pass

    def copy(self):
        pass

    def count(self):
        pass

    def extend(self):
        pass

    def index(self):
        pass

    def insert(self):
        pass

    def pop(self):
        pass

    def remove(self):
        pass

    def reverse(self):
        pass

    def sort(self):
        pass


class Value:
    def __init__(self):
        self.types: Dict[int, Any] = {}

    def __le__(self, other: Value):
        for v_idx in self.types:
            if v_idx not in other.types:
                return False
            if not self.types[v_idx] <= other.types[v_idx]:
                return False
        return True

    def __iadd__(self, other: Value):
        for v_idx in other.types:
            if v_idx not in self.types:
                self.types[v_idx] = other.types[v_idx]
            else:
                self.types[v_idx] += other.types[v_idx]
        return self

    def __repr__(self):
        return self.types.__repr__()

    def inject_func_type(self, lab, func_type):
        self.types[lab] = func_type


class AbstractValue:
    def __init__(self, top=False):
        if top:
            self.abstract_value: Value | VALUE_TOP = VALUE_TOP
        else:
            self.abstract_value: Value | VALUE_TOP = Value()

    def __le__(self, other: AbstractValue):
        if other.abstract_value == VALUE_TOP:
            return True
        if self.abstract_value == VALUE_TOP:
            return False
        return self.abstract_value <= other.abstract_value

    def __iadd__(self, other: AbstractValue):
        if self.abstract_value == VALUE_TOP or other.abstract_value == VALUE_TOP:
            return VALUE_TOP
        else:
            self.abstract_value += other.abstract_value
            return self.abstract_value

    def __repr__(self):
        return self.abstract_value.__repr__()

    def inject_func_type(self, lab, func_type):
        self.abstract_value.inject_func_type(lab, func_type)


# Dict[str, AbstractValue|VALUE_TOP]
class AbstractValueDict(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)

    def __missing__(self, key):
        self[key] = value = AbstractValue(top=True)
        return value

    def __le__(self, other: AbstractValueDict):
        for key in self:
            if key.startswith("__") and key.endswith("__"):
                continue
            if key not in other:
                return False
            if not self[key] <= other[key]:
                return False
        return True

    def __iadd__(self, other: AbstractValueDict):
        for key in other:
            if key.startswith("__") and key.endswith("__"):
                continue
            self[key] += other[key]
        return self

    def hybrid_copy(self):
        return AbstractValueDict().copy()


SELF_FLAG = "self"
INIT_FLAG = "19970303"
INIT_FLAG_VALUE = Value()
RETURN_FLAG = "19951107"
