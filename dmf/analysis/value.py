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

import logging
from typing import Set, Dict, List

NONE_TYPE = "NONE"
BOOL_TYPE = "BOOL"
NUM_TYPE = "NUM"
BYTE_TYPE = "BYTE"
STR_TYPE = "STR"

BASIC_TYPES = (NONE_TYPE, BOOL_TYPE, NUM_TYPE, BYTE_TYPE, STR_TYPE)


def static_c3(class_object):
    if class_object is builtin_object:
        return [class_object]
    return [class_object] + static_merge(
        [static_c3(base) for base in class_object.bases]
    )


def static_merge(mro_list):
    if not any(mro_list):
        return []
    for candidate, *_ in mro_list:
        if all(candidate not in tail for _, *tail in mro_list):
            return [candidate] + static_merge(
                [
                    tail if head is candidate else [head, *tail]
                    for head, *tail in mro_list
                ]
            )
    else:
        raise TypeError("No legal mro")


class ClassObject:
    def __init__(self, class_name: str, bases: List[ClassObject], attributes: Dict):
        self.name: str = class_name
        self.bases: List[ClassObject] = bases
        self.attributes = attributes
        if not bases:
            self.mro = None
        else:
            self.compute_mro()

    def __repr__(self):
        return "name: {} x dict: {}".format(self.name, self.attributes.__repr__())

    def compute_mro(self):
        self.mro = static_c3(self)
        logging.debug("mro is {}".format(self.mro))

    def issubset(self, other: ClassObject):
        for attribute in self.attributes:
            if attribute not in other.attributes:
                return False
            elif self.attributes[attribute].issubset(other.attributes[attribute]):
                return False

        return True

    def update(self, other: ClassObject):
        for attribute in other.attributes:
            if attribute not in self.attributes:
                self.attributes[attribute] = other.attributes[attribute]
            else:
                self.attributes[attribute].update(other.attributes[attribute])

        return self

    def hybrid_copy(self):
        return self


builtin_object = ClassObject("object", [], {})


class Value:
    def __init__(self):
        self.heap_types: Set[int] = set()
        self.prim_types: Set[str] = set()
        self.func_types: Set[int] = set()
        self.class_types: ClassObject | None = None

    def __repr__(self):
        return "{} x {} x {} x {}".format(
            self.heap_types, self.prim_types, self.func_types, self.class_types
        )

    def inject_heap_type(self, heap: int):
        self.heap_types.add(heap)

    def extract_heap_type(self):
        return self.heap_types

    def inject_prim_type(self, type_to_be_injected: str):
        self.prim_types.add(type_to_be_injected)

    def inject_func_type(self, label: int):
        self.func_types.add(label)

    def extract_func_type(self):
        return self.func_types

    def inject_class_type(self, name, bases, frame: Dict[str, Value]):
        class_object: ClassObject = ClassObject(name, bases, frame)
        if self.class_types is None:
            self.class_types = class_object
        else:
            self.class_types.update(class_object)

    def extract_class_object(self) -> ClassObject:
        return self.class_types

    def issubset(self, other: Value):

        res1 = self.heap_types.issubset(other.heap_types)
        res2 = self.prim_types.issubset(other.prim_types)
        res3 = self.func_types.issubset(other.func_types)
        if self.class_types is None and other.class_types is None:
            res4 = True
        elif self.class_types is None and other.class_types is not None:
            res4 = False
        elif self.class_types is not None and other.class_types is None:
            res4 = False
        else:
            res4 = self.class_types.issubset(other.class_types)
        return all((res1, res2, res3, res4))

    def update(self, other: Value):
        self.heap_types.update(other.heap_types)
        self.prim_types.update(other.prim_types)
        self.func_types.update(other.func_types)
        if isinstance(self.class_types, ClassObject) and isinstance(
            other.class_types, ClassObject
        ):
            self.class_types.update(other.class_types)
        elif self.class_types is None and other.class_types is None:
            pass
        elif self.class_types is not None and other.class_types is None:
            pass
        elif self.class_types is None and other.class_types is not None:
            pass
        return self
