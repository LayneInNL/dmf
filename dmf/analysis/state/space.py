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
import logging
from typing import Dict, Tuple, List, NewType, Any


class ValueBool:
    BOT = 1
    BOOL = 2

    def __init__(self):
        self.value = ValueBool.BOT

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

    def __init__(self):
        self.value = ValueNum.BOT

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

    def __init__(self):
        self.value = ValueNone.BOT

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

    def __init__(self):
        self.value = ValueStr.BOT

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


class AbstractValue:
    def __init__(self):
        self.heap_contexts = set()
        self.value_bool = ValueBool()
        self.value_num = ValueNum()
        self.value_none = ValueNone()
        self.value_str = ValueStr()

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

    def union(self, other: AbstractValue):
        self.heap_contexts.update(other.heap_contexts)
        self.value_bool.union(other.value_bool)
        self.value_num.union(other.value_num)
        self.value_none.union(other.value_none)
        self.value_str.union(other.value_str)

    def issubset(self, other: AbstractValue):
        return (
            self.heap_contexts.issubset(other.heap_contexts)
            and self.value_bool.issubset(other.value_bool)
            and self.value_num.issubset(other.value_num)
            and self.value_none.issubset(other.value_none)
            and self.value_str.issubset(other.value_str)
        )

    def __repr__(self):
        return "heaps {} x bool {} x num {} x none {} x str {}".format(
            self.heap_contexts,
            self.value_bool,
            self.value_num,
            self.value_none,
            self.value_str,
        )


class Stack:
    def __init__(self):
        self.stack: List = [{}]

    def lookup(self, var: str):
        top_frame = self.top()
        return top_frame[var]

    def top(self):
        return self.stack[-1]

    def pop(self) -> None:
        self.stack = self.stack[:-1]

    def insert_var(self, var: str, abstract_value: AbstractValue) -> None:
        top_frame = self.top()
        top_frame[var] = abstract_value

    def __repr__(self):
        result = ""
        for key, value in self.top().items():
            line = "{}, {}\n".format(key, value)
            result += line

        return result


class Store:
    def __init__(self):
        self.store = {}


FuncInfo = NewType("FuncInfo", Tuple[int, int])


class FuncTable:
    def __init__(self):
        self.func_table: List[Dict[str, FuncInfo]] = []
        self.new_and_push_frame()

    def new_and_push_frame(self):
        self.func_table.append({})

    def insert_func(self, name: str, start_label: int, final_label: int):
        top: Dict[str, FuncInfo] = self.top()
        func_info = (start_label, final_label)
        top[name] = FuncInfo(func_info)

    def top(self) -> Dict[str, FuncInfo]:
        return self.func_table[-1]

    def pop(self) -> None:
        self.func_table = self.func_table[:-1]

    def st(self, name: str) -> FuncInfo:
        return self.top()[name]


ClassInfo = NewType("ClassInfo", Tuple[int, int])


class ClassTable:
    def __init__(self):
        # each class contains global fields, function tables
        self.class_table: List[Dict[str, ClassInfo]] = []
        self.new_and_push_frame()

    def new_and_push_frame(self):
        self.class_table.append({})

    def insert_class(self, name: str, start_label: int, final_label: int):
        top: Dict[str, ClassInfo] = self.top()
        class_info = (start_label, final_label)
        top[name] = ClassInfo(class_info)

    def top(self) -> Dict[str, Any]:
        return self.class_table[-1]

    def pop(self) -> None:
        self.class_table = self.class_table[:-1]

    def st(self, name: str) -> ClassInfo:
        return self.top()[name]
