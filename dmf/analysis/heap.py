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

from dmf.analysis.value_util import issubset_twodict, update_twodict, issubset, update
from dmf.analysis.value import Value, ClsType


class Singleton:
    def __init__(self, cls_obj):
        self.internal: Dict[str, Value] = {}
        self.cls_obj: ClsType = cls_obj

    def __repr__(self):
        return "dict {} cls {}".format(self.internal, self.cls_obj)

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
        # At first retrieve dict of instance itself.
        if field in self.internal:
            return self.internal[field]
        else:
            return self.cls_obj.getattr(field)


class Summary:
    def __init__(self):
        self.internal: Dict[ClsType, Dict[str, Value]] = {}

    def __le__(self, other: Summary):
        return issubset_twodict(self.internal, other.internal)

    def __iadd__(self, other: Summary):
        update_twodict(self.internal, other.internal)
        return self


class Heap:
    def __init__(self, heap: Heap = None):
        self.singletons: Dict[int, Singleton] = {}
        self.summaries: Dict[int, Summary] = {}
        if heap is not None:
            self.singletons.update(heap.singletons)
            self.summaries.update(heap.summaries)

    def __contains__(self, item: Tuple[int, str]):
        heap_ctx, field = item
        return field in self.singletons[heap_ctx]

    def __le__(self, other: Heap):
        return issubset(self.singletons, other.singletons) and issubset(
            self.summaries, other.summaries
        )

    def __iadd__(self, other: Heap):
        self.singletons.update(other.singletons)
        self.summaries.update(other.summaries)
        return self

    def __repr__(self):
        return "Singleton: {}, Summary {}".format(self.singletons, self.summaries)

    def add_heap_and_cls(self, heap_ctx, cls_obj):
        singleton = Singleton(cls_obj)
        self.singletons[heap_ctx] = singleton

    def write_to_field(self, heap_ctx: int, field: str, value: Value):
        self.singletons[heap_ctx][field] = value

    def read_from_field(self, heap_ctx: int, field: str):
        return self.singletons[heap_ctx][field]

    def copy(self):
        copied = Heap(self)
        return copied
