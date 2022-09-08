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

from typing import Dict

from dmf.analysis.heap_namespace import HeapNamespace
from dmf.analysis.value import Value


class Heap:
    def __init__(self):
        self.singletons: Dict[str, HeapNamespace] = {}

    def __contains__(self, item):
        return item in self.singletons

    def __le__(self, other: Heap):
        for heap_address in self.singletons:
            if heap_address not in other.singletons:
                return False
            else:
                self_namespace: HeapNamespace = self.singletons[heap_address]
                other_namespace: HeapNamespace = other.singletons[heap_address]
                if not self_namespace <= other_namespace:
                    return False
        return True

    def __iadd__(self, other: Heap):
        for heap_address in other.singletons:
            if heap_address not in self.singletons:
                self.singletons[heap_address] = other.singletons[heap_address]
            else:
                self_namespace = self.singletons[heap_address]
                other_namespace = other.singletons[heap_address]
                self_namespace += other_namespace
        return self

    def __repr__(self):
        return "heaps: {}".format(self.singletons)

    def has_heap_address(self, heap_address):
        if heap_address in self.singletons:
            return True
        return False

    def write_instance_to_heap(self, heap_uuid: str):
        if heap_uuid not in self.singletons:
            self.singletons[heap_uuid] = HeapNamespace()
        return self.singletons[heap_uuid]

    def write_field_to_address(self, heap_address: str, field: str, value: Value):
        assert heap_address in self.singletons
        tp_dict = self.singletons[heap_address]
        tp_dict.write_local_value(field, value)

    def read_field_from_address(self, heap_address: str, field: str):
        assert heap_address in self.singletons
        tp_dict = self.singletons[heap_address]
        return tp_dict.read_value(field)

    def read_instance_dict(self, heap_address: str):
        return self.singletons[heap_address]
