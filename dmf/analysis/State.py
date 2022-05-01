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
from dmf.analysis.Heap import Heap
from dmf.analysis.Stack import Stack, Frame
from dmf.analysis.Value import Value


class State:
    def __init__(self):
        self.stack: Stack = Stack()
        # self.heap: Heap = Heap()

    def __repr__(self):
        return self.stack.__repr__()

    def push_frame_to_stack(self, frame: Frame):
        self.stack.push_frame(frame)

    def pop_frame_from_stack(self):
        self.stack.pop_frame()

    def top_frame_on_stack(self):
        return self.stack.top_frame()

    def read_var_from_stack(self, var: str) -> Value:
        return self.stack.read_var(var)

    def write_var_to_stack(self, var: str, value: Value):
        self.stack.write_var(var, value)

    def stack_go_into_new_frame(self):
        self.stack.go_into_new_frame()

    def issubset(self, other: State):
        return self.stack.issubset(other.stack)

    def update(self, other: State):
        self.stack.update(other.stack)
        return self

    def hybrid_copy(self):
        copied = State()
        copied.stack = self.stack.hybrid_copy()
        # copied.heap = self.heap.hybrid_copy()

        return copied
