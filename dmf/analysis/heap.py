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
from typing import Dict, Tuple, DefaultDict

from dmf.analysis.value import InsType, Value, Namespace, Var
from dmf.analysis.value_util import issubset_twodict, update_twodict, issubset, update


# class Singleton:
#     def __init__(self, cls_obj):
#         self.internal: Dict = {}
#         self.cls_obj = cls_obj
#
#     def __repr__(self):
#         return "dict {} cls {}".format(self.internal, self.cls_obj)
#
#     def __le__(self, other: Singleton):
#         return issubset(self.internal, other.internal)
#
#     def __iadd__(self, other: Singleton):
#         update(self.internal, other.internal)
#         return self
#
#     def __contains__(self, field):
#         return field in self.internal
#
#     def __setitem__(self, field, value):
#         self.internal[field] = value
#
#     def __getitem__(self, field):
#         # At first retrieve dict of instance itself.
#         if field in self.internal:
#             return self.internal[field]
#         else:
#             return self.cls_obj.getattr(field)


# class Summary:
#     def __init__(self):
#         self.internal: Dict = {}
#
#     def __le__(self, other: Summary):
#         return issubset_twodict(self.internal, other.internal)
#
#     def __iadd__(self, other: Summary):
#         update_twodict(self.internal, other.internal)
#         return self


class Heap:
    def __init__(self, heap: Heap = None):
        self.singletons: DefaultDict[InsType, Namespace[Var, Value]] = defaultdict(
            Namespace
        )
        if heap is not None:
            self.singletons.copy()

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
        return "singleton: {}".format(self.singletons)

    def write_ins_to_heap(self, ins: InsType):
        self.singletons[ins] = Namespace()

    def write_field_to_heap(self, ins: InsType, field: str, value: Value):
        self.singletons[ins][Var(field, "local")] = value

    def copy(self):
        copied = Heap(self)
        return copied


analysis_heap = Heap()
