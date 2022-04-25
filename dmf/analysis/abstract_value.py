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

from collections import defaultdict


class ValueBool:
    BOT = 1
    BOOL = 2

    def __init__(self, present=False):
        self.value = ValueBool.BOOL if present else ValueBool.BOT

    def present(self):
        self.value = ValueBool.BOOL

    def issubset(self, other: ValueBool):
        return self.value <= other.value

    def union(self, other: ValueBool):
        if self.value + other.value == 2:
            self.value = ValueBool.BOT
        else:
            self.value = ValueBool.BOOL

    def __repr__(self):
        if self.value == ValueBool.BOT:
            return "BOT"
        else:
            return "BOOL"


class ValueNum:
    BOT = 1
    NUM = 2

    def __init__(self, present=False):
        self.value = ValueNum.NUM if present else ValueNum.BOT

    def present(self):
        self.value = ValueNum.NUM

    def issubset(self, other: ValueNum):
        return self.value <= other.value

    def union(self, other: ValueNum):
        if self.value + other.value == 2:
            self.value = ValueNum.BOT
        else:
            self.value = ValueNum.NUM

    def __repr__(self):
        if self.value == ValueNum.BOT:
            return "BOT"
        else:
            return "NUM"


class ValueNone:
    BOT = 1
    NONE = 2

    def __init__(self, present=False):
        self.value = ValueNone.NONE if present else ValueNone.BOT

    def present(self):
        self.value = ValueNone.NONE

    def issubset(self, other: ValueNone):
        return self.value <= other.value

    def union(self, other: ValueNone):
        if self.value + other.value == 2:
            self.value = ValueNone.BOT
        else:
            self.value = ValueNone.NONE

    def __repr__(self):
        if self.value == ValueNone.BOT:
            return "BOT"
        else:
            return "NONE"


class ValueStr:
    BOT = 1
    STR = 2

    def __init__(self, present=False):
        self.value = ValueStr.STR if present else ValueStr.BOT

    def present(self):
        self.value = ValueStr.STR

    def issubset(self, other: ValueStr):
        return self.value <= other.value

    def union(self, other: ValueStr):
        if self.value + other.value == 2:
            self.value = ValueStr.BOT
        else:
            self.value = ValueStr.STR

    def __repr__(self):
        if self.value == ValueNone.BOT:
            return "BOT"
        else:
            return "STR"


class PrettyDefaultDict(defaultdict):
    __repr__ = dict.__repr__


class ValueFunction:
    def __init__(self):
        self.value = PrettyDefaultDict(set)

    def __getitem__(self, item):
        return self.value[item]

    def inject_function(self, name, location):
        self.value[name].add(location)

    def extract_function(self, name):
        return self.value[name]

    def issubset(self, other: ValueFunction):
        for var in self.value:
            if var not in other.value:
                return False
            if not self.value[var].issubset(other.value[var]):
                return False
        return True

    def union(self, other: ValueFunction):
        other_value = other.value
        self_value = self.value
        for var in other_value:
            if var not in self_value:
                self_value[var] = other_value[var]
            else:
                self_value[var].update(other_value[var])

    def __repr__(self):
        return self.value.__repr__()


class ValueClass:
    def __init__(self):
        self.value = {}

    def inject_class(self, name, label, frame):
        self.value[(name, label)] = frame

    def issubset(self, other: ValueClass):
        for key, values in self.value.items():
            if key not in other.value:
                return False
            other_values = other.value[key]
            for var in values:
                if var not in other_values:
                    return False
                if not values[var].issubset(other_values[var]):
                    return False
        return True

    def union(self, other: ValueClass):
        for other_key, other_values in other.value.items():
            if other_key not in self.value:
                self.value[other_key] = other_values
                continue
            values = self.value[other_key]
            for other_var in other_values:
                if other_var not in values:
                    values[other_var] = other_values[other_var]
                else:
                    values[other_var].union(other_values[other_var])

    def __repr__(self):
        return self.value.__repr__()


class Value:
    def __init__(
        self, value_bool=False, value_num=False, value_none=False, value_str=False
    ):
        self.heap_contexts = set()
        self.value_bool = ValueBool(value_bool)
        self.value_num = ValueNum(value_num)
        self.value_none = ValueNone(value_none)
        self.value_str = ValueStr(value_str)
        self.value_func = ValueFunction()
        self.value_class = ValueClass()

    def inject_heap_context(self, heap):
        self.heap_contexts.add(heap)

    def inject_bool(self):
        self.value_bool.present()

    def inject_num(self):
        self.value_num.present()

    def inject_none(self):
        self.value_none.present()

    def inject_str(self):
        self.value_str.present()

    def inject_function(self, name, location):
        self.value_func.inject_function(name, location)

    def extract_function(self, name):
        self.value_func.extract_function(name)

    def inject_class(self, name, label, frame):
        self.value_class.inject_class(name, label, frame)

    def union(self, other: Value):
        self.heap_contexts.update(other.heap_contexts)
        self.value_bool.union(other.value_bool)
        self.value_num.union(other.value_num)
        self.value_none.union(other.value_none)
        self.value_str.union(other.value_str)
        self.value_func.union(other.value_func)
        self.value_class.union(other.value_class)

    def issubset(self, other: Value):
        return (
            self.heap_contexts.issubset(other.heap_contexts)
            and self.value_bool.issubset(other.value_bool)
            and self.value_num.issubset(other.value_num)
            and self.value_none.issubset(other.value_none)
            and self.value_str.issubset(other.value_str)
            and self.value_func.issubset(other.value_func)
            and self.value_class.issubset(other.value_class)
        )

    def __repr__(self):
        return "heaps {} x bool {} x num {} x none {} x str {} x func {} x class {}".format(
            self.heap_contexts,
            self.value_bool,
            self.value_num,
            self.value_none,
            self.value_str,
            self.value_func,
            self.value_class,
        )
