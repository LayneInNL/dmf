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

from typing import Dict, Tuple

from dmf.analysis.utils import issubset_twodict, update_twodict, issubset, update
from dmf.analysis.value import Value, ClsObj


class Singleton:
    def __init__(self, cls_obj):
        self.cls_obj = cls_obj
        self.internal: Dict[str, Value] = {}

    def __le__(self, other: Singleton):
        return issubset(self.internal, other.internal)

    def __iadd__(self, other: Singleton):
        update(self.internal, other.internal)
        return self

    def __contains__(self, field):
        return field in self.internal

    def __setitem__(self, field, value):
        self.internal[field] = value

    def __getitem__(self, field):
        return self.internal[field]


class Summary:
    def __init__(self):
        self.internal: Dict[ClsObj, Dict[str, Value]] = {}

    def __le__(self, other: Summary):
        return issubset_twodict(self.internal, other.internal)

    def __iadd__(self, other: Summary):
        update_twodict(self.internal, other.internal)
        return self


class Heap:
    def __init__(self, heap: Heap = None):
        self.singleton: Dict[int, Singleton] = {}
        self.summary: Dict[int, Summary] = {}
        if heap is not None:
            self.singleton.update(heap.singleton)
            self.summary.update(heap.summary)

    def __contains__(self, item: Tuple[int, str]):
        heap_ctx, field = item
        return field in self.singleton[heap_ctx]

    def __le__(self, other: Heap):
        return issubset(self.singleton, other.singleton) and issubset(
            self.summary, other.summary
        )

    def __iadd__(self, other: Heap):
        self.singleton.update(other.singleton)
        self.summary.update(other.summary)
        return self

    def __repr__(self):
        return "Singleton: {}, Summary {}".format(self.singleton, self.summary)

    def write_to_field(self, heap_ctx: int, field: str, value: Value):
        self.singleton[heap_ctx][field] = value

    def read_from_field(self, heap_ctx: int, field: str):
        return self.singleton[heap_ctx][field]

    def copy(self):
        copied = Heap(self)
        return copied
