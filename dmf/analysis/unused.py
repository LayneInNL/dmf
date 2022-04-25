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
class FuncTableFrame:
    def __init__(self, scope_property):
        self.frame = {}
        self.scope_property = scope_property


class FuncTable:
    def __init__(self, extremal=False):
        self.func_table = []
        if extremal:
            self.push(FuncTableFrame("global"))

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

    def enter_new_scope(self, scope_property):
        self.push(FuncTableFrame(scope_property))


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
