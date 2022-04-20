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

import logging
from collections import defaultdict
from typing import Dict, Tuple, List, Union, Set, NewType, DefaultDict, Any

from .types import BUILTIN_CLASSES, BUILTIN_CLASS_NAMES

Context = NewType("Context", tuple)
HContext = NewType("HContext", tuple)
FieldName = NewType("FieldName", str)
VarAddress = NewType("VarAddress", Tuple[str, Context])
FieldNameAddress = NewType("FieldNameAddress", Tuple[FieldName, HContext])
Address = NewType("Address", Union[VarAddress, FieldNameAddress])
DataStackFrame = NewType("DataStackFrame", Dict[str, Address])
Obj = NewType("Obj", Tuple[HContext, Dict[FieldName, Address]])


class DataStack:
    def __init__(self):
        self.data_stack: List[DataStackFrame] = []
        self.new_and_push_frame()

    def st(self, var: str, context: Context = None) -> Address:
        if var in BUILTIN_CLASS_NAMES:
            return BUILTIN_CLASS_NAMES[var]

        logging.debug("Test st: {} {}".format(var, context))
        top_frame: DataStackFrame = self.top()
        if var not in top_frame:
            logging.info("{} is not in data stack, make one".format(var))
            top_frame[var] = (var, context)
        return top_frame[var]

    def top(self) -> DataStackFrame:
        return self.data_stack[-1]

    def pop(self) -> None:
        self.data_stack = self.data_stack[:-1]

    def insert_var(self, var: str, address: Address) -> None:
        top_frame: DataStackFrame = self.top()
        top_frame[var] = address

    def new_and_push_frame(self) -> None:
        frame: DataStackFrame = DataStackFrame({})
        self.data_stack.append(frame)

    def __repr__(self) -> str:
        result = ""
        for key, value in self.top().items():
            line = "{}, {}\n".format(key, value)
            result += line

        return result


class Store:
    def __init__(self, default_initialize: bool = True):
        self.store: DefaultDict[Address, Set[Obj]] = defaultdict(set)
        if default_initialize:
            self._initialize()

    def _initialize(self):
        for cls in BUILTIN_CLASSES:
            self.insert_one(cls.address, cls.obj)

    def insert_one(self, address: Address, obj: Obj):
        self.store[address].add(obj)

    def insert_many(self, address: Address, objs: Set[Obj]):
        # sometimes an object only points to one object, but sometimes points to lots of
        # if one, clear and add new
        # self.store[address].clear()
        self.store[address].update(objs)

    def get(self, address: Address) -> Set[Obj]:
        return self.store[address]

    def get_store(self) -> Dict:
        return self.store.items()

    def __repr__(self) -> str:
        result = ""
        for key, value in self.store.items():
            line = "{}, {}\n".format(key, value)
            result += line

        return result


CallStackFrame = NewType("CallStackFrame", Tuple[int, Context, Address])


class CallStack:
    def __init__(self):
        self.call_stack: List[CallStackFrame] = []

    def top(self) -> CallStackFrame:
        assert self.call_stack
        return self.call_stack[-1]

    def pop(self) -> None:
        assert self.call_stack
        self.call_stack = self.call_stack[:-1]

    def push(self, frame: CallStackFrame):
        self.call_stack.append(frame)

    def emplace(self, label: int, context: Context, address: Address) -> None:
        self.push(CallStackFrame((label, context, address)))


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
