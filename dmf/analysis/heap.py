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

from collections import defaultdict
from typing import Dict

from dmf.analysis.value import Value


class Heap:
    def __init__(self):
        self.heap: Dict[int, Dict[str, Value]] = defaultdict(dict)

    def __repr__(self):
        return self.heap.__repr__()

    def write_to_field(self, heap_context: int, field_name: str, value: Value):
        self.heap[heap_context][field_name] = value

    def read_from_field(self, heap_context: int, field_name: str):
        return self.heap[heap_context][field_name]

    def contains(self, heap_context: int, field_name: str):
        return field_name in self.heap[heap_context]

    def issubset(self, other: Heap):
        for heap_context in self.heap:
            if heap_context not in other.heap:
                return False
            fields = self.heap[heap_context]
            other_fields = other.heap[heap_context]
            for field in fields:
                if field not in other_fields:
                    return False
                if not fields[field].issubset(other_fields[field]):
                    return False

        return True

    def update(self, other: Heap):
        for heap_context in other.heap:
            if heap_context not in self.heap:
                self.heap[heap_context] = other.heap[heap_context]
            else:
                other_fields = other.heap[heap_context]
                fields = self.heap[heap_context]
                for field in other_fields:
                    if field not in fields:
                        fields[field] = other_fields[field]
                    else:
                        fields[field].update(other_fields[field])

        return self

    def hybrid_copy(self):
        copied = Heap()
        copied.heap.update(self.heap)
        return copied
