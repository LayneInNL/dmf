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

from dmf.analysis.namespace import Namespace
from dmf.analysis.types import Instance
from dmf.analysis.value import Value
from dmf.analysis.namespace import LocalVar


class Heap:
    def __init__(self):
        self.singletons: Dict = {}

    # def __deepcopy__(self, memo):
    #     new_singletons = deepcopy(self.singletons, memo)
    #     new_heap = object.__new__(Heap)
    #     new_heap.singletons = new_singletons
    #     memo[id(self)] = new_heap
    #     return new_heap

    def __contains__(self, item):
        return item in self.singletons

    def __le__(self, other: Heap):
        for ins in self.singletons:
            if ins not in other.singletons:
                return False
            else:
                self_dict = self.singletons[ins]
                other_dict = other.singletons[ins]
                for field in self_dict:
                    if field not in other_dict:
                        return False
                    elif not self_dict[field] <= other_dict[field]:
                        return False
        return True

    def __iadd__(self, other: Heap):
        for ins in other.singletons:
            if ins not in self.singletons:
                self.singletons[ins] = other.singletons[ins]
            else:
                self_dict = self.singletons[ins]
                other_dict = other.singletons[ins]
                for field in other_dict:
                    if field not in self.singletons:
                        self_dict[field] = other_dict[field]
                    else:
                        self_dict[field] += other_dict[field]
        return self

    def __repr__(self):
        return "heaps: {}".format(self.singletons)

    def write_ins_to_heap(self, instance: Instance) -> Namespace:
        if instance not in self.singletons:
            self.singletons[instance] = Namespace()
        print(id(self.singletons[instance]))
        return self.singletons[instance]

    def write_field_to_heap(self, instance: Instance, field: str, value: Value):
        self.singletons[instance][LocalVar(field)] = value

    def read_field_from_heap(self, instance: Instance, field: str):
        return self.singletons[instance][LocalVar(field)]

    def read_instance_dict(self, instance: Instance):
        return self.singletons[instance]

    def write_instance_dict(self, instance: Instance):
        self.singletons[instance] = Namespace()
