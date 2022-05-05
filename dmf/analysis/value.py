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
from typing import Set, Dict, List, Tuple

from dmf.analysis.utils import issubset, update

NONE_TYPE = "NONE"
BOOL_TYPE = "BOOL"
NUM_TYPE = "NUM"
BYTE_TYPE = "BYTE"
STR_TYPE = "STR"


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
    def __init__(
        self, name: str, bases: List[ClassObject], attributes: Dict[str, Value]
    ):
        self.name: str = name
        self.bases: List[ClassObject] = bases
        self.attributes = attributes
        if bases:
            self.mro = static_c3(self)

    def __repr__(self):
        return "name: {} x dict: {}".format(self.name, self.attributes.__repr__())

    def __le__(self, other: ClassObject):
        return issubset(self.attributes, other.attributes)

    def __iadd__(self, other: ClassObject):
        return update(self.attributes, other.attributes)

    def __getitem__(self, item: str):
        if item in self.attributes:
            return self.attributes[item]

        for base in self.mro:
            if item in base.attributes:
                return base.attributes[item]

        raise AttributeError


builtin_object = ClassObject("object", [], {})


class Value:
    def __init__(self):
        self.heap_types: Set[Tuple[int, ClassObject]] = set()
        self.prim_types: Set[str] = set()
        self.func_type: int | None = None
        self.class_type: ClassObject | None = None

    def __le__(self, other: Value):

        res1 = self.heap_types.issubset(other.heap_types)
        res2 = self.prim_types.issubset(other.prim_types)
        if self.func_type is None:
            if other.func_type is None:
                res3 = True
            elif other.func_type is not None:
                res3 = False
        elif self.func_type is not None:
            if other.func_type is None:
                res3 = False
            else:
                if self.func_type == other.func_type:
                    res3 = True
                else:
                    logging.debug(
                        "new {}, old {}".format(self.func_type, other.func_type)
                    )
                    assert False
        if self.class_type is None:
            if other.class_type is None:
                res4 = True
            elif other.class_type is not None:
                res4 = False
        elif self.class_type is not None:
            if other.class_type is None:
                res4 = False
            else:
                res4 = self.class_type <= other.class_type
        return all((res1, res2, res3, res4))

    def __iadd__(self, other: Value):
        self.heap_types.update(other.heap_types)
        self.prim_types.update(other.prim_types)
        if self.func_type is None:
            if other.func_type is None:
                pass
            elif other.func_type is not None:
                self.func_type = other.func_type
        elif self.func_type is not None:
            if other.func_type is None:
                pass
            elif other.func_type is not None:
                if self.func_type == other.func_type:
                    pass
                else:
                    logging.debug(
                        "new {}, old {}".format(self.func_type, other.func_type)
                    )
                    assert False

        if isinstance(self.class_type, ClassObject) and isinstance(
            other.class_type, ClassObject
        ):
            self.class_type += other.class_type
        elif self.class_type is None and other.class_type is None:
            pass
        elif self.class_type is not None and other.class_type is None:
            pass
        elif self.class_type is None and other.class_type is not None:
            pass
        return self

    def __repr__(self):
        return "{} x {} x {} x {}".format(
            self.heap_types, self.prim_types, self.func_type, self.class_type
        )

    def inject_heap_type(self, heap: int, class_object: ClassObject):
        self.heap_types.add((heap, class_object))

    def inject_none(self):
        self.prim_types.add(NONE_TYPE)

    def inject_bool(self):
        self.prim_types.add(BOOL_TYPE)

    def inject_num(self):
        self.prim_types.add(NUM_TYPE)

    def inject_byte(self):
        self.prim_types.add(BYTE_TYPE)

    def inject_str(self):
        self.prim_types.add(STR_TYPE)

    def inject_func_type(self, label: int):
        if self.func_type is None:
            self.func_type = label
        else:
            logging.debug("new {}, old {}".format(label, self.func_type))
            assert False

    def inject_class_type(self, name, bases, frame: Dict[str, Value]):
        class_object: ClassObject = ClassObject(name, bases, frame)
        if self.class_type is None:
            self.class_type = class_object
        else:
            self.class_type += class_object

    def extract_heap_type(self) -> Set[Tuple[int, ClassObject]]:
        return self.heap_types

    def extract_prim_type(self):
        return self.prim_types

    def extract_func_label(self):
        return self.func_type

    def extract_class_object(self) -> ClassObject:
        return self.class_type
