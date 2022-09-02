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

from dmf.analysis.namespace import Namespace, Var
from dmf.analysis.value import Value


class Heap:
    def __init__(self):
        self.singletons: Dict[str, Namespace] = {}

    def __contains__(self, item):
        return item in self.singletons

    def __le__(self, other: Heap):
        for heap_address in self.singletons:
            if heap_address not in other.singletons:
                return False
            else:
                self_dict: Namespace = self.singletons[heap_address]
                other_dict: Namespace = other.singletons[heap_address]
                for field in self_dict:
                    field: Var
                    if field.name not in other_dict:
                        return False
                    elif not self_dict[field] <= other_dict[field]:
                        return False
        return True

    def __iadd__(self, other: Heap):
        for heap_address in other.singletons:
            if heap_address not in self.singletons:
                self.singletons[heap_address] = other.singletons[heap_address]
            else:
                self_namespace = self.singletons[heap_address]
                other_namespace = other.singletons[heap_address]
                for field in other_namespace:
                    field: Var
                    if field.name not in self_namespace:
                        self_namespace[field] = other_namespace[field]
                    else:
                        self_namespace[field] += other_namespace[field]
        return self

    def __repr__(self):
        return "heaps: {}".format(self.singletons)

    def write_instance_to_heap(self, heap_uuid: str):
        if heap_uuid not in self.singletons:
            self.singletons[heap_uuid] = Namespace()
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

    def write_instance_dict(self, heap_address: str):
        self.singletons[heap_address] = Namespace()

    def delete_instance_from_heap(self, heap_address: str):
        del self.singletons[heap_address]
