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

from dmf.analysis.abstract_value import Value


class StackFrame:
    def __init__(self):
        self.frame = {}

    def __setitem__(self, key, value):
        self.frame[key] = value

    def __getitem__(self, item):
        return self.frame[item]

    def keys(self):
        return self.frame

    def get_internal_dict(self):
        return self.frame

    def items(self):
        return self.frame.items()

    def issubset(self, other: StackFrame):
        for key in self.keys():
            if key not in other.keys():
                return False
            if isinstance(self.frame[key], Value):
                if not self.frame[key].issubset(other[key]):
                    return False
            else:
                logging.debug("{} has type {}".format(key, self.frame[key]))

        return True

    def union(self, other: StackFrame):
        intersection = set(self.keys()).intersection(other.keys())
        for var in intersection:
            self[var].union(other[var])

        diff = set(other.keys()).difference(self.keys())
        for var in diff:
            self[var] = other[var]

    def __repr__(self):
        return self.frame.__repr__()

    def copy(self):
        copied = StackFrame()
        for key, value in self.items():
            copied[key] = value
        return copied


class Stack:
    def __init__(self):
        self.stack = []

    def push(self, frame):
        self.stack.append(frame)

    def enter_new_scope(self):
        self.stack.append(StackFrame())

    def pop(self):
        self.stack = self.stack[:-1]

    def top(self):
        return self.stack[-1]

    def write_var(self, name, value):
        self.top()[name] = value

    def read_var(self, name):
        return self.top()[name]

    def issubset(self, other: Stack):
        return self.top().issubset(other.top())

    def union(self, other: Stack):
        self.top().union(other.top())

    def __repr__(self):
        return self.stack.__repr__()

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

    def write_to_stack(self, name, value):
        self.stack.write_var(name, value)

    def read_from_stack(self, name):
        return self.stack.read_var(name)

    def stack_enter_new_scope(self):
        self.stack.enter_new_scope()

    def issubset(self, other: State):
        return self.stack.issubset(other.stack)

    def union(self, other: State):
        self.stack.union(other.stack)

    def __repr__(self):
        return self.stack.__repr__()

    def copy(self):
        copied_state = State()
        copied_stack = self.stack.copy()
        copied_state.stack = copied_stack
        return copied_state


class ContextStates:
    def __init__(self, extremal=False):
        if extremal:
            state = State()
            state.stack_enter_new_scope()
            self.states = {(): state}
        else:
            self.states = {}

    def __setitem__(self, key, value):
        self.states[key] = value

    def __getitem__(self, context):
        return self.states[context]

    def items(self):
        return self.states.items()

    def union(self, original: ContextStates):
        if original is None:
            return

        for context, state in original.items():
            if context not in self.states:
                self.__setitem__(context, state)
            else:
                self.states[context].union(state)

    def issubset(self, original: ContextStates):
        # if original is None, it's unreachable for now.
        if original is None:
            return False

        # check relationship of contexts
        transferred_contexts = set(self.states)
        original_contexts = set(original.states)
        if transferred_contexts.issubset(original_contexts):
            # check relationship of state
            for context in transferred_contexts:
                new_state = self.states[context]
                original_state = original.states[context]
                if not new_state.issubset(original_state):
                    return False
        return False

    def __repr__(self):
        res = ""
        for context, state in self.states.items():
            res += "context {}, state {}\n".format(context, state)

        return res

    def copy(self):
        copied_context_states = ContextStates()
        for key, states in self.states.items():
            copied_context_states[key] = states.copy()
        return copied_context_states


class FuncTable:
    def __init__(self):
        self.func_table = [{}]

    def push(self, frame):
        self.func_table.append(frame)

    def pop(self):
        self.func_table = self.func_table[:-1]

    def top(self):
        return self.func_table[-1]

    def insert(self, name, location, entry_label, exit_label):
        top = self.top()
        top[name] = (location, (entry_label, exit_label))

    def lookup(self, name):
        top = self.top()
        return top[name]


class ClassTable:
    def __init__(self):
        self.class_table = [{}]

    def push(self, frame):
        self.class_table.append(frame)

    def pop(self):
        self.class_table = self.class_table[:-1]

    def top(self):
        return self.class_table[-1]

    def insert(self, name, entry_label, exit_label):
        top = self.top()
        top[name] = (entry_label, exit_label)

    def lookup(self, name):
        top = self.top()
        return top[name]
