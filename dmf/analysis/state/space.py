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
import typing
from typing import Dict, Tuple, List, Union

from .types import BUILTIN_CLASSES, BUILTIN_CLASS_NAMES

Context = typing.NewType("Context", tuple)
HContext = typing.NewType("HContext", tuple)
Var = typing.NewType("Var", str)
FieldName = typing.NewType("FieldName", str)
VarAddress = typing.NewType("VarAddress", Tuple[Var, Context])
FieldNameAddress = typing.NewType("FieldNameAddress", Tuple[FieldName, HContext])
Address = typing.NewType("Address", Union[VarAddress, FieldNameAddress])
DataStackFrame = typing.NewType("DataStackFrame", Dict[Var, Address])
Obj = typing.NewType("Obj", Tuple[HContext, Dict[FieldName, Address]])


def new_frame() -> DataStackFrame:
    frame: DataStackFrame = DataStackFrame({})
    return frame


class DataStack:
    def __init__(self):
        self.data_stack: List[DataStackFrame] = []
        initial_frame: DataStackFrame = new_frame()
        self.push_frame(initial_frame)

    def st(self, var: Var, context: Context = None) -> Address:
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

    def push_var(self, var: Var, address: Address) -> None:
        top_frame: DataStackFrame = self.top()
        top_frame[var] = address

    def push_frame(self, frame: DataStackFrame) -> None:
        self.data_stack.append(frame)

    def __repr__(self) -> str:
        result = ""
        for key, value in self.top().items():
            line = "{}, {}\n".format(key, value)
            result += line

        return result


class Store:
    def __init__(self, default_initialize: bool = True):
        self.store: Dict[Address, Obj] = {}
        if default_initialize:
            self._initialize()

    def _initialize(self):
        for cls in BUILTIN_CLASSES:
            self.insert_one(cls.address, cls.obj)

    def insert_one(self, address: Address, obj: Obj):
        self.store[address] = obj

    def get(self, address: Address) -> Obj:
        return self.store[address]

    def __repr__(self) -> str:
        result = ""
        for key, value in self.store.items():
            line = "{}, {}\n".format(key, value)
            result += line

        return result


class CallStack:
    def __init__(self):
        # call_stack contains Tuple[StmtID, Context, ContSensAddr]
        self.call_stack = []
