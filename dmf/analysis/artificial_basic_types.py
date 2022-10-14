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
from dmf.analysis.special_types import Any
from dmf.analysis.value import type_2_value, Value
from dmf.log.logger import logger


class Artificial:
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]


# mimic man-made functions such as len()
class ArtificialFunction(Artificial):
    def __init__(self, tp_function: FunctionType, tp_qualname: str):
        # use memory address to denote uniqueness
        self.tp_uuid: str = f"artificial.function.{tp_qualname}"
        # human-readable function name
        self.tp_qualname: str = tp_qualname
        # function itself
        self.tp_code: FunctionType = tp_function
        # an empty tp_dict
        self.tp_dict: Namespace = Namespace()

    def __call__(self, *args, **kwargs):
        value = Value()
        try:
            result = self.tp_code(*args, **kwargs)
        except TypeError:
            logger.critical(f"Function call failed")
        else:
            value.inject(result)
        finally:
            return value

    def __repr__(self):
        return self.tp_uuid


# mimic methods such as list.append
class ArtificialMethod(Artificial):
    def __init__(self, tp_function: ArtificialFunction, tp_instance):
        self.tp_uuid: str = (
            f"artificial.method.{tp_function.tp_uuid}.{tp_instance.tp_uuid}"
        )
        self.tp_qualname = f"{tp_function.tp_uuid}.{tp_instance.tp_uuid}"
        self.tp_function: ArtificialFunction = tp_function
        self.tp_instance = tp_instance

    def __call__(self, *args, **kwargs):
        value = Value()
        try:
            result = self.tp_function(type_2_value(self.tp_instance), *args, **kwargs)
        except TypeError:
            logger.critical(f"Method call failed")
        else:
            value.inject(result)
        finally:
            return value

    def __repr__(self):
        return self.tp_uuid


# mimic such as builtins.list
class ArtificialClass(Artificial):
    def __init__(self, tp_qualname: str):
        # fully qualified name
        self.tp_uuid: str = f"artificial.class.{tp_qualname}"
        # fully qualified name
        self.tp_qualname: str = tp_qualname
        # instance dict
        self.tp_dict: Namespace = Namespace()

    def __repr__(self):
        return self.tp_uuid

    def __call__(self, *args, **kwargs):
        raise NotImplementedError


# mimic builtins.type
# if called with 1 arg, return its type
# if called with 3 args, it's creating a class. just return Any
class TypeArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs) -> Value:
        if len(args) == 1:
            objs: Value = args[0]
            value = Value()
            for obj in objs:
                value.inject(obj.tp_class)
            return value
        else:
            return Value.make_any()


# Type_Type mimics builtins.type
# call it will yield results
Type_Type = TypeArtificialClass("builtins.type")
Type_Type.tp_class = Type_Type

# mimic builtins.object
class ObjectArtificialClass(ArtificialClass):
    def __call__(self, *args, **kwargs):
        raise NotImplementedError


# Object_Type mimics builtins.object
Object_Type = ObjectArtificialClass("builtins.object")
Object_Type.tp_bases = []
Object_Type.tp_class = Type_Type
Type_Type.tp_bases = [[Object_Type]]


class IncompleteMRO(Exception):
    pass


def c3(cls_obj):
    try:
        mros = static_c3(cls_obj)
    except IncompleteMRO:
        return [[Any]]
    else:
        return mros


def static_c3(cls_obj) -> List[List]:
    if cls_obj is Object_Type:
        return [[cls_obj]]
    elif cls_obj is Any:
        raise IncompleteMRO
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


Type_Type.tp_mro = c3(Type_Type)
Object_Type.tp_mro = c3(Object_Type)


# redefine __init__ to create other ArtificialClasses
def __init__(self, tp_qualname: str):
    self.tp_uuid: str = f"artificial.class.{tp_qualname}"
    self.tp_qualname: str = tp_qualname
    self.tp_dict: Namespace = Namespace()
    self.tp_class = Type_Type
    self.tp_bases = [[Object_Type]]
    self.tp_mro = [[self, Object_Type]]


ArtificialClass.__init__ = __init__
