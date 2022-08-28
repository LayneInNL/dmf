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

from dmf.analysis.analysis_types import (
    AnalysisInstance,
)
from dmf.analysis.namespace import Namespace
from dmf.analysis.value import Value


class Heap:
    def __init__(self):
        self.singletons: Dict = {}

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

    def write_instance_to_heap(self, heap_uuid: str):
        if heap_uuid not in self.singletons:
            self.singletons[heap_uuid] = Namespace()
        return self.singletons[heap_uuid]

    def write_field_to_instance(
        self, instance: AnalysisInstance, field: str, value: Value
    ):
        assert instance.tp_uuid in self.singletons
        tp_dict = self.singletons[instance.tp_uuid]
        tp_dict.write_local_value(field, "local", value)

    def read_field_from_instance(self, instance: AnalysisInstance, field: str):
        assert instance.tp_uuid in self.singletons
        tp_dict = self.singletons[instance.tp_uuid]
        return tp_dict.read_value(field)

    def read_instance_dict(self, instance: AnalysisInstance):
        return self.singletons[instance.tp_uuid]

    def write_instance_dict(self, instance: AnalysisInstance):
        self.singletons[instance.tp_uuid] = Namespace()

    def delete_instance_from_heap(self, instance: AnalysisInstance):
        del self.singletons[instance.tp_uuid]
