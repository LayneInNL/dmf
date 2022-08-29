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
from types import FunctionType
from typing import List

from dmf.analysis.namespace import Namespace
from dmf.analysis.special_types import Bases_Any, MRO_Any
from dmf.analysis.typeshed_types import TypeshedClass
from dmf.analysis.value import type_2_value
from dmf.log.logger import logger


class Singleton:
    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]


class Immutable:
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class ArtificialFunction(Singleton, Immutable):
    def __init__(self, tp_function: FunctionType, tp_qualname: str):
        # use memory address to denote uniqueness
        self.tp_uuid: str = str(id(tp_function))
        # human-readable function name
        self.tp_qualname = tp_qualname
        # function itself
        self.tp_code: FunctionType = tp_function
        # an empty tp_dict
        self.tp_dict: Namespace = Namespace()

    def __call__(self, *args, **kwargs):
        return self.tp_code(*args, **kwargs)

    def __repr__(self):
        return self.tp_qualname


class ArtificialMethod:
    def __init__(self, tp_function, tp_instance):
        self.tp_uuid = f"{tp_function.tp_uuid}-{tp_instance.tp_uuid}"
        self.tp_function = tp_function
        self.tp_instance = tp_instance

    def __call__(self, *args, **kwargs):
        return self.tp_function(self.tp_instance, *args, **kwargs)

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.tp_uuid


# ArtificialClass = builtins.type
class ArtificialClass(Singleton, Immutable):
    def __init__(self, tp_qualname: str):
        self.tp_uuid: str = tp_qualname
        self.tp_qualname: str = tp_qualname
        self.tp_dict: Namespace = Namespace()

    def __repr__(self):
        return self.tp_qualname


# create a type
Type_Type = ArtificialClass("builtins.type")
Type_Type_Value = type_2_value(Type_Type)
Type_Type.tp_class = Type_Type

Object_Type = ArtificialClass("builtins.object")
Object_Type_Value = type_2_value(Object_Type)
Object_Type.tp_bases = []
Object_Type.tp_class = Type_Type
Type_Type.tp_bases = [[Object_Type]]


# if MROAnyError, it means mro can not be fully constructed.
# we only know current class and the rest of mro is Any
def c3(cls_obj):
    mros = static_c3(cls_obj)
    logger.critical(mros)
    return mros


def static_c3(cls_obj) -> List[List]:
    if cls_obj is Object_Type:
        return [[cls_obj]]
    elif cls_obj is Bases_Any:
        return [[MRO_Any]]
    else:
        mros = []
        # cls_obj is like [[1,2,3]]
        for base_list in cls_obj.tp_bases:
            base_list: List
            merge_list: List = []
            for base in base_list:
                many_c3: List[List] = static_c3(base)
                for one_c3 in many_c3:
                    merge_list.append(one_c3)
                    one_mro: List = static_merge(merge_list)
                    mros.append([cls_obj] + one_mro)
        return mros
        # return [cls_obj] + static_merge([static_c3(base) for base in cls_obj.tp_bases])


def static_merge(mro_list) -> List:
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


Type_Type.tp_bases = [[Object_Type]]
# Type_Type.tp_bases = [[Bases_Any]]
Type_Type.tp_mro = c3(Type_Type)
Object_Type.tp_mro = c3(Object_Type)

# Type and Object are initialized. Here we initialize Typeshed related objects
TypeshedClass.tp_class = Type_Type
TypeshedClass.tp_bases = [[Bases_Any]]
TypeshedClass.c3 = c3

# redefine __init__ to create other ArtificialClasses
def __init__(self, tp_qualname: str):
    self.tp_uuid: str = tp_qualname
    self.tp_qualname: str = tp_qualname
    self.tp_dict: Namespace = Namespace()
    self.tp_class = Type_Type
    self.tp_bases = [Type_Type_Value.value_2_list()]
    self.tp_mro = c3(self)


ArtificialClass.__init__ = __init__
Range_Type = ArtificialClass("builtins.range")
Method_Type = ArtificialClass("builtins.method")

None_Type = ArtificialClass("builtins.NoneType")
