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

import builtins
from typing import List, Any, Dict

from dmf.analysis.abstract_value import Value

BUILTIN_NAMES = set(dir(builtins))


class Frame:
    def __init__(self, scope_property):
        self.frame = {}
        self.scope_property = scope_property

    def __setitem__(self, key, value):
        self.frame[key] = value

    def __getitem__(self, key):
        return self.frame[key]

    def __contains__(self, key):
        return key in self.frame

    def keys(self):
        return self.frame

    def symbol_table(self):
        return self.frame

    def items(self):
        return self.frame.items()

    def issubset(self, other: Frame):
        for key in self.keys():
            if key not in other.keys():
                return False
            if not self.frame[key].issubset(other[key]):
                return False

        return True

    def union(self, other: Frame):
        intersection = set(self.keys()).intersection(other.keys())
        for var in intersection:
            self[var].update(other[var])

        diff = set(other.keys()).difference(self.keys())
        for var in diff:
            self[var] = other[var]

    def __repr__(self):
        return self.frame.__repr__()

    def copy(self):
        copied_frame = Frame(self.scope_property)
        for key, value in self.items():
            copied_frame[key] = value
        return copied_frame


class Stack:
    def __init__(self):
        self.stack: List[Frame] = []

    def __repr__(self):
        return self.stack.__repr__()

    def push(self, frame: Frame):
        self.stack.append(frame)

    def enter_new_scope(self, scope_property):
        self.push(Frame(scope_property))

    def pop(self):
        self.stack = self.stack[:-1]

    def top(self):
        return self.stack[-1]

    def write_var(self, name, value):
        self.top()[name] = value

    def LEGB(self, name):
        for frame in reversed(self.stack):
            if frame.scope_property == "global":
                return frame[name]
            else:
                if name not in frame:
                    continue
                else:
                    return frame[name]

    def issubset(self, other: Stack):
        return self.top().issubset(other.top())

    def union(self, other: Stack):
        self.top().union(other.top())

    def copy(self):
        copied_stack = Stack()
        for frame in self.stack:
            copied_frame = frame.copy()
            copied_stack.push(copied_frame)
        return copied_stack


class Heap:
    def __init__(self):
        self.heap = {}


class State:
    def __init__(self):
        self.stack = Stack()
        # self.heap = Heap()

    def __repr__(self):
        return self.stack.__repr__()

    def write_to_stack(self, name, value: Value):
        self.stack.write_var(name, value)

    def read_from_stack(self, name) -> Value:
        return self.stack.LEGB(name)

    def stack_enter_new_scope(self, scope_property):
        self.stack.enter_new_scope(scope_property)

    def issubset(self, other: State):
        return self.stack.issubset(other.stack)

    def union(self, other: State):
        self.stack.union(other.stack)

    def copy(self):
        copied_state = State()
        copied_stack = self.stack.copy()
        copied_state.stack = copied_stack
        return copied_state


class Lattice:
    def __init__(self):
        self.lattice = {}

    def __setitem__(self, key, value):
        self.lattice[key] = value

    def __getitem__(self, context):
        return self.lattice[context]

    def __delitem__(self, key):
        del self.lattice[key]

    def __contains__(self, context):
        return context in self.lattice

    def items(self):
        return self.lattice.items()

    def update(self, original: Lattice):
        if original is None:
            return

        for context, state in original.items():
            if context not in self.lattice:
                self.__setitem__(context, state)
            else:
                self.lattice[context].update(state)

    def issubset(self, original: Lattice):
        # if original is None, it's unreachable for now.
        if original is None:
            return False

        # check relationship of contexts
        transferred_contexts = set(self.lattice)
        original_contexts = set(original.lattice)
        if transferred_contexts.issubset(original_contexts):
            # check relationship of state
            for context in transferred_contexts:
                new_state = self.lattice[context]
                original_state = original.lattice[context]
                if not new_state.issubset(original_state):
                    return False
        return False

    def __repr__(self):
        res = ""
        for context, state in self.lattice.items():
            res += "context {}, state {}\n".format(context, state)

        return res

    def copy(self):
        copied_context_states = Lattice()
        for key, states in self.lattice.items():
            copied_context_states[key] = states.copy()
        return copied_context_states
