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

from typing import Dict, List

from dmf.analysis.value import AbstractValueDict, AbstractValue


def new_local_ns(old_ns: AbstractValueDict = None):
    new_ns = AbstractValueDict()
    if old_ns is not None:
        new_ns.update(old_ns)

    return new_ns


class Frame:
    def __init__(self, f_locals, f_back, f_globals, f_builtins):
        self.f_locals: AbstractValueDict[str, AbstractValue] = f_locals
        self.f_back: Frame | None = f_back
        self.f_globals: AbstractValueDict[str, AbstractValue] = f_globals
        self.f_builtins: AbstractValueDict[str, AbstractValue] = f_builtins

    def __contains__(self, var):
        return var in self.f_locals

    def __le__(self, other: Frame):
        return self.f_locals <= other.f_locals

    def __iadd__(self, other: Frame):
        self.f_locals += other.f_locals
        return self

    def __repr__(self):
        return self.f_locals.__repr__()

    def read_var(self, var):
        # Implement LEGB rule
        if var in self.f_locals:
            return self.f_locals[var]

        parent_frame: Frame = self.f_back
        while parent_frame is not None and parent_frame.f_globals is self.f_globals:
            if var in parent_frame.f_locals:
                return parent_frame.f_locals[var]
            else:
                parent_frame = parent_frame.f_back

        if var in self.f_globals:
            return self.f_globals[var]

        if var in self.f_builtins:
            return self.f_builtins[var]

        raise AttributeError

    def write_var(self, var, value):
        self.f_locals[var] = value

    def copy(self):
        copied = Frame(
            new_local_ns(self.f_locals), self.f_back, self.f_globals, self.f_builtins
        )

        return copied


class Stack:
    def __init__(self, stack: Stack = None):
        self.stack: List[Frame] = []
        if stack is not None:
            for frame in stack.stack[:-1]:
                self.push_frame(frame)
            self.push_frame(stack.stack[-1].copy())

    def __le__(self, other: Stack):
        return self.top_frame() <= other.top_frame()

    def __iadd__(self, other: Stack):
        top_frame = self.top_frame()
        top_frame += other.top_frame()
        return self

    def __repr__(self):
        return self.stack.__repr__()

    def push_frame(self, frame: Frame):
        self.stack.append(frame)

    def pop_frame(self):
        self.stack = self.stack[:-1]

    def top_frame(self) -> Frame:
        return self.stack[-1]

    def read_var(self, var):
        return self.top_frame().read_var(var)

    def write_var(self, var, value):
        return self.top_frame().write_var(var, value)

    def copy(self):
        copied = Stack(self)
        return copied

    def next_ns(self):
        curr_frame = self.top_frame()
        new_frame = Frame(
            new_local_ns(), curr_frame, curr_frame.f_globals, curr_frame.f_builtins
        )
        self.push_frame(new_frame)
