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

from dmf.analysis.utils import issubset_twodict, update_twodict
from dmf.analysis.value import Value


class Heap:
    def __init__(self):
        self.heap: Dict[int, Dict[str, Value]] = defaultdict(dict)

    def __contains__(self, item):
        hcontext, field = item
        return field in self.heap[hcontext]

    def __le__(self, other: Heap):
        return issubset_twodict(self.heap, other.heap)

    def __iadd__(self, other: Heap):
        update_twodict(self.heap, other.heap)
        return self

    def __repr__(self):
        return self.heap.__repr__()

    def write_to_field(self, heap_context: int, field_name: str, value: Value):
        self.heap[heap_context][field_name] = value

    def read_from_field(self, heap_context: int, field_name: str):
        return self.heap[heap_context][field_name]

    def hybrid_copy(self):
        copied = Heap()
        copied += self
        return copied
