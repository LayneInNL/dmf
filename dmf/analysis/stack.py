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

from typing import Any, Dict, List

from dmf.analysis.value import Value

# BUILTIN_DICT = {"True": "True", "False": "False", "None": "None"}


class Frame:
    def __init__(self):
        self.f_locals: Dict[str, Value] | None = {}
        self.f_back: Frame | None = None
        self.f_globals: Dict[str, Value] | None = None
        self.f_builtins: Dict[str, Value] | None = None

    def __repr__(self):
        return self.f_locals.__repr__()

    def read_var(self, name):
        # Implement LEGB rule
        if name in self.f_locals:
            return self.f_locals[name]

        parent_frame: Frame = self.f_back
        while parent_frame is not None and parent_frame.f_globals is self.f_globals:
            if name in parent_frame.f_locals:
                return parent_frame.f_locals[name]
            else:
                parent_frame = parent_frame.f_back

        if name in self.f_globals:
            return self.f_globals[name]

        if name in self.f_builtins:
            return self.f_builtins[name]

        assert False

    def contains(self, name):
        return name in self.f_locals

    def write_var(self, name, value):
        self.f_locals[name] = value

    def issubset(self, other: Frame):
        for var in self.f_locals:
            if var not in other.f_locals:
                return False
            if not self.f_locals[var].issubset(other.f_locals[var]):
                return False
        return True

    def update(self, other: Frame):
        for var in other.f_locals:
            if var not in self.f_locals:
                self.f_locals[var] = other.f_locals[var]
            else:
                self.f_locals[var].update(other.f_locals[var])

        return self

    def hybrid_copy(self):
        copied = Frame()
        copied.f_locals.update(self.f_locals)
        copied.f_globals = self.f_globals
        copied.f_back = self.f_back

        return copied


def create_first_frame():
    frame = Frame()
    frame.f_globals = frame.f_locals = {}
    frame.f_back = None
    return frame


class Stack:
    def __init__(self):
        self.stack: List[Frame] = []

    def __repr__(self):
        return self.stack.__repr__()

    def push_frame(self, frame: Frame):
        self.stack.append(frame)

    def pop_frame(self):
        self.stack = self.stack[:-1]

    def top_frame(self) -> Frame:
        return self.stack[-1]

    def read_var(self, name):
        return self.top_frame().read_var(name)

    def write_var(self, name, value):
        return self.top_frame().write_var(name, value)

    def issubset(self, other: Stack):
        return self.top_frame().issubset(other.top_frame())

    def update(self, other: Stack):
        self.top_frame().update(other.top_frame())

    def hybrid_copy(self):
        copied = Stack()
        for frame in self.stack[:-1]:
            copied.push_frame(frame)
        copied.push_frame(self.stack[-1].hybrid_copy())

        return copied

    def go_into_new_frame(self):
        curr_frame = self.top_frame()
        new_frame = Frame()
        new_frame.f_back = curr_frame
        new_frame.f_globals = curr_frame.f_globals
        self.push_frame(new_frame)