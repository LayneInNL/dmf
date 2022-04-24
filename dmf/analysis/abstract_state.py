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


class StackFrame:
    def __init__(self):
        self.frame = {}


class Stack:
    def __init__(self):
        self.stack = []
        self.init()

    def init(self):
        global_frame = StackFrame()
        self.push(global_frame)

    def push(self, frame):
        self.stack.append(frame)

    def pop(self):
        self.stack = self.stack[:-1]

    def top(self):
        return self.stack[-1]


class Heap:
    def __init__(self):
        self.heap = {}


class State:
    def __init__(self):
        self.stack = Stack()
        self.heap = Heap()
