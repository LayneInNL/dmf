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

import ast
import sys
from copy import deepcopy
from types import FunctionType
from typing import Tuple

import astor

from dmf.analysis.artificial_basic_types import (
    ArtificialClass,
    ArtificialFunction,
    Type_Type,
    Object_Type,
    c3,
)
from dmf.analysis.context_sensitivity import record
from dmf.analysis.exceptions import IteratingError
from dmf.analysis.implicit_names import (
    MODULE_PACKAGE_FLAG,
    MODULE_NAME_FLAG,
)
from dmf.analysis.namespace import Namespace
from dmf.analysis.special_types import Any
from dmf.analysis.typeshed_types import (
    TypeshedModule,
    TypeshedFunction,
    TypeshedClass,
    TypeshedAssign,
    parse_typeshed_module,
    extract_1value,
    Typeshed,
    TypeshedDescriptorGetter,
    TypeshedImportedModule,
    TypeshedImportedName,
    TypeshedInstance,
)
from dmf.analysis.typing_names import all_typing_names, all_builtin_names
from dmf.analysis.union_namespace import UnionNamespace
from dmf.analysis.value import Value, type_2_value
from dmf.log.logger import logger

# this is used as a namespace for artificial classes and functions
artificial_namespace = Namespace()
artificial_namespace.write_local_value("type", type_2_value(Type_Type))
artificial_namespace.write_local_value("object", type_2_value(Object_Type))

# since we use static analysis, builtin_module is a set of modules
# but in fact there will only be one module
builtin_modules: Value = parse_typeshed_module("builtins")
builtin_module: TypeshedModule = extract_1value(builtin_modules)
builtin_module_dict: Namespace = builtin_module.tp_dict

types_modules: Value = parse_typeshed_module("types")
types_module: TypeshedModule = extract_1value(types_modules)
types_module_dict: Namespace = types_module.tp_dict

Module_Types: Value = types_module_dict.read_value("ModuleType")
Module_Type: TypeshedClass = extract_1value(Module_Types)
TypeshedModule.tp_class = Module_Type

Function_Types: Value = types_module_dict.read_value("FunctionType")
Function_Type: TypeshedClass = extract_1value(Function_Types)

Int_Types: Value = builtin_module_dict.read_value("int")
Int_Type = extract_1value(Int_Types)
Int_Instance = Int_Type()

Float_Types: Value = builtin_module_dict.read_value("float")
Float_Type = extract_1value(Float_Types)
Float_Instance = Float_Type()

Complex_Types: Value = builtin_module_dict.read_value("complex")
Complex_Type = extract_1value(Complex_Types)
Complex_Instance = Complex_Type()

Str_Types: Value = builtin_module_dict.read_value("str")
Str_Type = extract_1value(Str_Types)
Str_Instance = Str_Type()

Bytes_Types: Value = builtin_module_dict.read_value("bytes")
Bytes_Type = extract_1value(Bytes_Types)
Bytes_Instance = Bytes_Type()

ByteArray_Types: Value = builtin_module_dict.read_value("bytearray")
ByteArray_Type = extract_1value(ByteArray_Types)
ByteArray_Instance = ByteArray_Type()

Bool_Types: Value = builtin_module_dict.read_value("bool")
Bool_Type = extract_1value(Bool_Types)
Bool_Instance = Bool_Type()

NotImplemented_Types = builtin_module_dict.read_value("_NotImplementedType")
NotImplemented_Type = extract_1value(NotImplemented_Types)
NotImplemented_Instance = NotImplemented_Type()
builtin_module_dict.write_local_value(
    "NotImplemented", type_2_value(NotImplemented_Instance)
)

Ellipsis_Types = builtin_module_dict.read_value("ellipsis")
Ellipsis_Type = extract_1value(Ellipsis_Types)
Ellipsis_Instance = Ellipsis_Type()
builtin_module_dict.write_local_value("Ellipsis", type_2_value(Ellipsis_Instance))

None_Types = builtin_module_dict.read_value("NoneType")
None_Type = extract_1value(None_Types)
None_Instance = None_Type()
builtin_module_dict.write_local_value("None", type_2_value(None_Instance))

Typeshed_Type_Type: Value = builtin_module_dict.read_value("type")
Type_Type.tp_fallback = Typeshed_Type_Type
# builtin_module_dict.write_local_value("type", type_2_value(Type_Type))

Typeshed_Object_Type: Value = builtin_module_dict.read_value("object")
Object_Type.tp_fallback = Typeshed_Object_Type
# builtin_module_dict.write_local_value("object", type_2_value(Object_Type))


# special attribute __name__
artificial_namespace.write_local_value("__name__", type_2_value(Str_Type()))

# mimic object.__new__
class Constructor:
    def __init__(self):
        self.tp_uuid = "artificial.function.builtins.object.__new__"
        self.tp_class = Function_Type

    def __call__(self, tp_address, tp_class):
        analysis_instance = AnalysisInstance(tp_address=tp_address, tp_class=tp_class)
        return analysis_instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]

    def __repr__(self):
        return "object.__new__"

    def extract_type(self):
        return "builtins.object.__new__"


def _setup_Object_Type():
    def __init__(self):
        return self

    init = ArtificialFunction(
        tp_function=__init__, tp_qualname="builtins.object.__init__"
    )
    Object_Type.tp_dict.write_local_value("__init__", type_2_value(init))

    constructor = Constructor()
    Object_Type.tp_dict.write_local_value("__new__", type_2_value(constructor))


_setup_Object_Type()


# mimic builtins.super
class SuperArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        # super(type1, type2)
        type1_value, type2_value, *_ = args
        assert len(type1_value) == 1, type1_value
        assert len(type2_value) == 1, type2_value
        type1 = extract_1value(type1_value)
        type2 = extract_1value(type2_value)

        if isinstance(type2, AnalysisInstance):
            type2_class = type2.tp_class
        else:
            raise NotImplementedError(type2)

        type2_class_mros = type2_class.tp_mro
        super_mros = []
        for type2_class_mro in type2_class_mros:
            # each is a list [xxx, yyy, zzz]
            for idx, curr_type in enumerate(type2_class_mro):
                if type2_class.tp_uuid == type1.tp_uuid:
                    one_mro = type2_class_mro[idx + 1 :]
                    super_mros.append(one_mro)
                    break
            else:
                super_mros.append([Any])

        return SuperAnalysisInstance(tp_address, tp_class, type2, super_mros)


Super_Type = SuperArtificialClass("builtins.super")
Typeshed_Super_Type: Value = builtin_module_dict.read_value("super")
Super_Type.tp_fallback = Typeshed_Super_Type
# builtin_module_dict.write_local_value("super", type_2_value(Super_Type))
artificial_namespace.write_local_value("super", type_2_value(Super_Type))


# mimic builtins.property
class PropertyArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        assert len(args) == 4, args
        fget, fset, fdel, *_ = args
        return PropertyAnalysisInstance(tp_address, tp_class, fget, fset, fdel)


Property_Type = PropertyArtificialClass("builtins.property")
Typeshed_Property_Type: Value = builtin_module_dict.read_value("property")
Property_Type.tp_fallback = Typeshed_Property_Type
# builtin_module_dict.write_local_value("property", type_2_value(Property_Type))
artificial_namespace.write_local_value("property", type_2_value(Property_Type))

# mimic builtins.classmethod
class ClassmethodArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        assert len(args) == 1, args
        function, *_ = args
        return ClassmethodAnalysisInstance(tp_address, tp_class, function)


Classmethod_Type = ClassmethodArtificialClass("builtins.classmethod")
Typeshed_Classmethod_Type: Value = builtin_module_dict.read_value("classmethod")
Classmethod_Type.tp_fallback = Typeshed_Classmethod_Type
# builtin_module_dict.write_local_value("classmethod", type_2_value(Classmethod_Type))
artificial_namespace.write_local_value("classmethod", type_2_value(Classmethod_Type))

# mimic builtins.staticmethod
class StaticmethodArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args):
        assert len(args) == 1, args
        function, *_ = args
        return StaticmethodAnalysisInstance(tp_address, tp_class, function)


Staticmethod_Type = StaticmethodArtificialClass("builtins.staticmethod")
Typeshed_Staticmethod_Type: Value = builtin_module_dict.read_value("staticmethod")
Staticmethod_Type.tp_fallback = Typeshed_Staticmethod_Type
# builtin_module_dict.write_local_value("staticmethod", type_2_value(Staticmethod_Type))
artificial_namespace.write_local_value("staticmethod", type_2_value(Staticmethod_Type))

# mimic generator
class GeneratorArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        # the first argument of args contains all yielded types
        assert len(args) == 1, args
        init_container_value, *_ = args
        return GeneratorAnalysisInstance(tp_address, tp_class, init_container_value)


Generator_Type = GeneratorArtificialClass("types.GeneratorType")
Typeshed_Generator_Type: Value = types_module_dict.read_value("GeneratorType")
Generator_Type.tp_fallback = Typeshed_Generator_Type
# types_module_dict.write_local_value("GeneratorType", type_2_value(Generator_Type))
artificial_namespace.write_local_value("GeneratorType", type_2_value(Generator_Type))


def _setup_Generator_Type():
    def __iter__(self):
        return self

    def __next__(self):
        value = Value()
        for type in self:
            one_value = type.tp_dict.read_value(type.tp_container)
            value.inject(one_value)
        return value

    methods = filter(lambda symbol: isinstance(symbol, FunctionType), locals().values())
    for method in methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"types.GeneratorType.{method.__name__}"
        )
        Generator_Type.tp_dict.write_local_value(
            method.__name__, type_2_value(arti_method)
        )


_setup_Generator_Type()


class RangeArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        return RangeAnalysisInstance(tp_address, tp_class)


Range_Type = RangeArtificialClass("builtins.range")

Typeshed_Range_Type: Value = builtin_module_dict.read_value("range")
Range_Type.tp_fallback = Typeshed_Range_Type
# builtin_module_dict.write_local_value("range", type_2_value(Range_Type))
artificial_namespace.write_local_value("range", type_2_value(Range_Type))


def _setup_Range_Type():
    def __iter__(self):
        value = Value()
        for one_self in self:
            iterator_tp_address = f"{one_self.tp_address}-range-iterator"
            list_value = one_self.tp_dict.read_value(one_self.tp_container)
            one_type = Iterator_Type(iterator_tp_address, Iterator_Type, list_value)
            value.inject(one_type)
        return value

    methods = filter(lambda symbol: isinstance(symbol, FunctionType), locals().values())
    for method in methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"builtins.range.{method.__name__}"
        )
        Range_Type.tp_dict.write_local_value(method.__name__, type_2_value(arti_method))


_setup_Range_Type()


class ListArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        # tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return ListAnalysisInstance(tp_address, tp_class)


List_Type = ListArtificialClass("builtins.list")
Typeshed_List_Type: Value = builtin_module_dict.read_value("list")
List_Type.tp_fallback = Typeshed_List_Type
artificial_namespace.write_local_value("list", type_2_value(List_Type))
# builtin_module_dict.write_local_value("list", type_2_value(List_Type))


def _setup_List_Type():
    def append(self: Value, x):
        value = Value()
        value.inject(x)

        for one_self in self:
            prev_value = one_self.tp_dict.read_value(one_self.tp_container)
            value.inject(prev_value)
            one_self.tp_dict.write_local_value(one_self.tp_container, value)
        return type_2_value(None_Instance)

    def extend(self, iterable):
        for one_self in self:
            one_self.tp_dict.write_local_value(one_self.tp_container, Value.make_any())
        return type_2_value(None_Instance)

    def insert(self, i, x):
        value = Value()
        value.inject(x)

        for one_self in self:
            prev_value = one_self.tp_value.read_value(one_self.tp_contaier)
            value.inject(prev_value)
            one_self.tp_dict.write_local_value(one_self.tp_contaier, value)
        return type_2_value(None_Instance)

    def remove(self, x):
        return type_2_value(None_Instance)

    def pop(self, i=None):
        value = Value()
        for one_self in self:
            prev_value = one_self.tp_dict.read_value(one_self.tp_container)
            value.inject(prev_value)
        return value

    def clear(self):
        for one_self in self:
            one_self.tp_dict.write_local_value(one_self.tp_container, Value())
        return type_2_value(None_Instance)

    def index(self, x, start=None, end=None):
        return type_2_value(Int_Instance)

    def count(self, x):
        return type_2_value(Int_Instance)

    def sort(self, *args, **kwargs):
        return type_2_value(None_Instance)

    def reverse(self):
        return type_2_value(None_Instance)

    def copy(self):
        return type_2_value(self)

    def __setitem__(self, key, value):
        for one_self in self:
            merged_value = Value()
            merged_value.inject(value)
            prev_value = one_self.tp_dict.read_value(one_self.tp_container)
            merged_value.inject(prev_value)
            one_self.tp_dict.write_local_value(one_self.tp_container, merged_value)
        return type_2_value(None_Instance)

    def __getitem__(self, key):
        value = Value()
        for one_self in self:
            prev_value = one_self.tp_dict.read_value(one_self.tp_container)
            value.inject(prev_value)
        return value

    def __iter__(self):
        value = Value()
        for one_self in self:
            program_point = sys.program_point
            heap_address = record(program_point[0], program_point[1])
            iterator_tp_address = f"{one_self.tp_address}-{heap_address}"
            list_value = one_self.tp_dict.read_value(one_self.tp_container)
            one_type = Iterator_Type(iterator_tp_address, Iterator_Type, list_value)
            value.inject(one_type)
        return value

    methods = filter(lambda symbol: isinstance(symbol, FunctionType), locals().values())
    for method in methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"builtins.list.{method.__name__}"
        )
        List_Type.tp_dict.write_local_value(method.__name__, type_2_value(arti_method))


_setup_List_Type()


class TupleArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        return TupleAnalysisInstance(tp_address, tp_class)


Tuple_Type = TupleArtificialClass("builtins.tuple")
Typeshed_Tuple_Type: Value = builtin_module_dict.read_value("tuple")
Tuple_Type.tp_fallback = Typeshed_Tuple_Type
# builtin_module_dict.write_local_value("tuple", type_2_value(Tuple_Type))
artificial_namespace.write_local_value("tuple", type_2_value(Tuple_Type))


def _setup_Tuple_Type():
    def fake_append(self: Value, x):
        value = Value()
        value.inject(x)

        for one_self in self:
            prev_value = one_self.tp_dict.read_value(one_self.tp_container)
            value.inject(prev_value)
            one_self.tp_dict.write_local_value(one_self.tp_container, value)
        return type_2_value(None_Instance)

    def index(self, x, start=None, end=None):
        return type_2_value(Int_Instance)

    def count(self, x):
        return type_2_value(Int_Instance)

    def __iter__(self):
        value = Value()
        for one_self in self:
            if isinstance(one_self, TupleAnalysisInstance):
                program_point = sys.program_point
                heap_address = record(program_point[0], program_point[1])
                iterator_tp_address = f"{one_self.tp_address}-{heap_address}"
                list_value = one_self.tp_dict.read_value(one_self.tp_container)
                one_type = Iterator_Type(iterator_tp_address, Iterator_Type, list_value)
                value.inject(one_type)
            else:
                raise NotImplementedError(one_self.tp_class)
        return value

    list_methods = filter(
        lambda symbol: isinstance(symbol, FunctionType), locals().values()
    )
    for method in list_methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"builtins.tuple.{method.__name__}"
        )
        Tuple_Type.tp_dict.write_local_value(method.__name__, type_2_value(arti_method))


_setup_Tuple_Type()


class SetArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        return SetAnalysisInstance(tp_address, tp_class)


Set_Type = SetArtificialClass("builtins.set")
Typeshed_Set_Type: Value = builtin_module_dict.read_value("set")
Set_Type.tp_fallback = Typeshed_Set_Type
# builtin_module_dict.write_local_value("set", type_2_value(Set_Type))
artificial_namespace.write_local_value("set", type_2_value(Set_Type))


class FrozensetArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        return FrozenSetAnalysisInstance(tp_address, tp_class)


Frozenset_Type = FrozensetArtificialClass("builtins.frozenset")
Typeshed_Frozenset_Type: Value = builtin_module_dict.read_value("frozenset")
Frozenset_Type.tp_fallback = Typeshed_Frozenset_Type
# builtin_module_dict.write_local_value("frozenset", type_2_value(Frozenset_Type))
artificial_namespace.write_local_value("frozenset", type_2_value(Frozenset_Type))


def _setup_Set_Type():
    def copy(self):
        return self

    def difference(self, *args, **kwargs):
        return Value.make_any()

    def intersection(self, *args, **kwargs):
        return Value.make_any()

    def isdisjoint(self, *args, **kwargs):
        return type_2_value(Bool_Instance)

    def issubset(self, *args, **kwargs):
        return type_2_value(Bool_Instance)

    def issuperset(self, *args, **kwargs):
        return type_2_value(Bool_Instance)

    def symmetric_difference(self, *args, **kwargs):
        return Value.make_any()

    def union(self, *args, **kwargs):
        return Value.make_any()

    def add(self, x):
        for one_self in self:
            value = Value()
            value.inject(x)
            prev_value = one_self.tp_dict.read_value(one_self.tp_container)
            value.inject(prev_value)
            one_self.tp_dict.write_local_value(one_self.tp_container, value)
        return type_2_value(None_Instance)

    def clear(self):
        for one_self in self:
            one_self.tp_dict.write_local_value(one_self.tp_container, Value())
        return type_2_value(None_Instance)

    def discard(self):
        return type_2_value(None_Instance)

    def difference_update(self, *args, **kwargs):
        return Value.make_any()

    def intersection_update(self, *args, **kwargs):
        return Value.make_any()

    def pop(self, *args, **kwargs):
        value = Value()
        for one_self in self:
            one_value = one_self.tp_dict.read_value(one_self.tp_container)
            value.inject(one_value)
        return value

    def remove(self, *args, **kwargs):
        return type_2_value(None_Instance)

    def symmetric_difference(self, *args, **kwargs):
        return Value.make_any()

    def symmetric_difference_update(self, *args, **kwargs):
        return Value.make_any()

    def __iter__(self):
        value = Value()
        for one_self in self:
            if isinstance(one_self, SetAnalysisInstance):
                program_point = sys.program_point
                heap_address = record(program_point[0], program_point[1])
                iterator_tp_address = f"{one_self.tp_address}-{heap_address}"
                list_value = one_self.tp_dict.read_value(one_self.tp_container)
                one_type = Iterator_Type(iterator_tp_address, Iterator_Type, list_value)
                value.inject(one_type)
            else:
                raise NotImplementedError(one_self.tp_class)
        return value

    methods = filter(lambda symbol: isinstance(symbol, FunctionType), locals().values())
    for method in methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"builtins.set.{method.__name__}"
        )
        Set_Type.tp_dict.write_local_value(method.__name__, type_2_value(arti_method))


_setup_Set_Type()


def _setup_FrozenSet_Type():
    def fake_add(self, x):
        for one_self in self:
            value = Value()
            value.inject(x)
            prev_value = one_self.tp_dict.read_value(one_self.tp_container)
            value.inject(prev_value)
            one_self.tp_dict.write_local_value(one_self.tp_container, value)
        return type_2_value(None_Instance)

    def copy(self):
        return self

    def difference(self, *args, **kwargs):
        return Value.make_any()

    def intersection(self, *args, **kwargs):
        return Value.make_any()

    def isdisjoint(self, *args, **kwargs):
        return type_2_value(Bool_Instance)

    def issubset(self, *args, **kwargs):
        return type_2_value(Bool_Instance)

    def issuperset(self, *args, **kwargs):
        return type_2_value(Bool_Instance)

    def symmetric_difference(self, *args, **kwargs):
        return Value.make_any()

    def union(self, *args, **kwargs):
        return Value.make_any()

    def __iter__(self):
        value = Value()
        for one_self in self:
            if isinstance(one_self, FrozenSetAnalysisInstance):
                program_point = sys.program_point
                heap_address = record(program_point[0], program_point[1])
                iterator_tp_address = f"{one_self.tp_address}-{heap_address}"
                list_value = one_self.tp_dict.read_value(one_self.tp_container)
                one_type = Iterator_Type(iterator_tp_address, Iterator_Type, list_value)
                value.inject(one_type)
            else:
                raise NotImplementedError(one_self.tp_class)
        return value

    methods = filter(lambda symbol: isinstance(symbol, FunctionType), locals().values())
    for method in methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"builtins.frozenset.{method.__name__}"
        )
        Frozenset_Type.tp_dict.write_local_value(
            method.__name__, type_2_value(arti_method)
        )


_setup_FrozenSet_Type()


class DictArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        return DictAnalysisInstance(tp_address, tp_class)


Dict_Type = DictArtificialClass("builtins.dict")
Typeshed_Dict_Type: Value = builtin_module_dict.read_value("dict")
Dict_Type.tp_fallback = Typeshed_Dict_Type
# builtin_module_dict.write_local_value("dict", type_2_value(Dict_Type))
artificial_namespace.write_local_value("dict", type_2_value(Dict_Type))


def _setup_Dict_Type():
    def get(self, key, default=None):
        value = Value()
        for one_self in self:
            prev_value = one_self.tp_dict.read_value(one_self.tp_container[1])
            value.inject(prev_value)

        if default is not None:
            value.inject(default)
        return value

    def setdefault(self, key, default=None):
        value = Value()
        for one_self in self:
            prev_value = one_self.tp_dict.read_value(one_self.tp_container[1])
            value.inject(prev_value)

        if default is not None:
            value.inject(default)

        return value

    def pop(self, key, default=None):
        value = Value()
        for one_self in self:
            prev_value = one_self.tp_dict.read_value(one_self.tp_container[1])
            value.inject(prev_value)

        if default is not None:
            value.inject(default)

        return value

    def popitem(self):
        value = Value()
        for one_self in self:
            key_value = one_self.tp_dict.read_value(one_self.tp_container[0])
            value.inject(key_value)
            value_value = one_self.tp_dict.read_value(one_self.tp_container[1])
            value.inject(value_value)
        program_point = sys.program_point
        tp_address = record(program_point[0], program_point[1])
        one_tuple = Tuple_Type(f"{tp_address}", Tuple_Type, value)
        return type_2_value(one_tuple)

    def keys(self):
        value = Value()
        for one_self in self:
            key_value = one_self.tp_dict.read_value(one_self.tp_container[0])
            program_point = sys.program_point
            heap_address = record(program_point[0], program_point[1])
            tp_address = f"{one_self.tp_address}-{heap_address}"
            one_iterator = Iterator_Type(tp_address, Iterator_Type, key_value)
            value.inject(one_iterator)
        return value

    def __iter__(self):
        return keys(self)

    def items(self):
        return Value.make_any()
        # value = Value()
        # for one_self in self:
        #     program_point = sys.program_point
        #     heap_address = record(program_point[0], program_point[1])
        #     tp_address = f"{one_self.tp_address}-{heap_address}"
        #     one_iterator = Iterator_Type(tp_address, Iterator_Type, Value.make_any())
        #     value.inject(one_iterator)
        # return value

    def values(self):
        value = Value()
        for one_self in self:
            value_value = one_self.tp_dict.read_value(one_self.tp_container[1])
            program_point = sys.program_point
            heap_address = record(program_point[0], program_point[1])
            tp_address = f"{one_self.tp_address}-{heap_address}"
            one_iterator = Iterator_Type(tp_address, Iterator_Type, value_value)
            value.inject(one_iterator)
        return value

    def update(self, other):
        # other could be AnalysisInstance
        for one_self in self:
            one_self.tp_dict.write_local_value(
                one_self.tp_container[0], Value.make_any()
            )
            one_self.tp_dict.write_local_value(
                one_self.tp_container[1], Value.make_any()
            )
        return type_2_value(None_Instance)

    def fromkeys(self, iterable, value=None):
        program_point = sys.program_point
        heap_address = record(program_point[0], program_point[1])
        tp_address = f"{heap_address}"

        if value is None:
            value = type_2_value(None_Instance)

        one_dict = Dict_Type(tp_address, Dict_Type, iterable, value)
        return type_2_value(one_dict)

    def clear(self):
        for one_self in self:
            one_self.tp_dict.write_local_value(one_self.tp_container[0], Value())
            one_self.tp_dict.write_local_value(one_self.tp_container[1], Value())
        return type_2_value(None_Instance)

    def copy(self):
        return self

    methods = filter(lambda symbol: isinstance(symbol, FunctionType), locals().values())
    for method in methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"builtins.dict.{method.__name__}"
        )
        Dict_Type.tp_dict.write_local_value(method.__name__, type_2_value(arti_method))


_setup_Dict_Type()


class IteratorArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args, **kwargs):
        value, *_ = args
        return IteratorAnalysisInstance(tp_address, tp_class, value)


Iterator_Type = IteratorArtificialClass("builtins.iterator")


def _setup_Iterator_Type():
    def __next__(self) -> Value:
        for one_self in self:
            value = Value()
            try:
                if one_self.location >= one_self.end_location:
                    raise IteratingError
                else:
                    elt = one_self.iterators[one_self.location]
                    one_self.location += 1
            except IteratingError:
                return value
            else:
                value.inject(elt)
                return value

    def __le__(self, other):
        # means no elements in iterator
        # raise NotImplementedError
        logger.critical(
            f"self.internal: {self.internal}, other.internal: {other.internal}"
        )
        return self.location == self.end_location

    def __iadd__(self, other):
        # raise NotImplementedError
        logger.critical(
            f"self.internal: {self.internal}, other.internal: {other.internal}"
        )
        return self

    methods = filter(lambda symbol: isinstance(symbol, FunctionType), locals().values())
    for method in methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"builtins.iterator.{method.__name__}"
        )
        Iterator_Type.tp_dict.write_local_value(
            method.__name__, type_2_value(arti_method)
        )


_setup_Iterator_Type()


class Analysis:
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def extract_type(self):
        raise NotImplementedError


class AnalysisInstance(Analysis):
    def __init__(self, tp_address: Tuple, tp_class: AnalysisClass):
        self.tp_uuid: Tuple = tp_address
        self.tp_address: Tuple = tp_address
        self.tp_class: AnalysisClass = tp_class

    @property
    def tp_dict(self):
        return sys.heap[self.tp_address]

    def __repr__(self):
        return f"{self.tp_address} object"

    def extract_type(self):
        return self.tp_class.extract_type()


class AnalysisClass(Analysis):
    def __init__(
        self, tp_uuid, tp_bases, tp_module, tp_dict, tp_code, tp_address, tp_name
    ):
        # tp_uuid is flow label
        self.tp_uuid: str = str(tp_uuid)

        self.tp_class = Type_Type
        self.tp_bases = tp_bases
        self.tp_mro = c3(self)

        self.tp_module = tp_module
        self.tp_dict = tp_dict
        self.tp_code = tp_code

        self.tp_address = tp_address
        # class name
        self.tp_name = tp_name

    def __le__(self, other: AnalysisClass):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisClass):
        self.tp_dict += other.tp_dict
        return self

    def __repr__(self):
        return f"analysis-class {self.tp_uuid}"

    def extract_type(self):
        return f"class builtins.type"


def _typeshedmodule_custom_getattr(self, name):
    if name not in self.tp_dict:
        return Value.make_any()
    else:
        value = Value()
        one_value = self.tp_dict.read_value(name)
        value.inject(one_value)
        value = refine_value(value)
        return value


TypeshedModule.custom_getattr = _typeshedmodule_custom_getattr


class AnalysisModule(Analysis):
    def __init__(self, tp_name: str, tp_package: str, tp_code: Tuple):
        # tp_uuid is module name
        self.tp_uuid: str = tp_name
        # same as tp_name
        self.tp_name: str = tp_name
        self.tp_class = Module_Type
        self.tp_package: str = tp_package
        self.tp_dict: UnionNamespace = UnionNamespace()
        setattr(self.tp_dict, MODULE_PACKAGE_FLAG, self.tp_package)
        setattr(self.tp_dict, MODULE_NAME_FLAG, self.tp_name)
        # entry and exit label of a module
        self.tp_code: Tuple = tp_code
        self.tp_address = (self.tp_code[0],)

    def __deepcopy__(self, memo):
        new_tp_dict = deepcopy(self.tp_dict, memo)
        self.tp_dict = new_tp_dict
        return self

    def __le__(self, other: AnalysisModule):
        return True
        # return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisModule):
        return self
        # self.tp_dict += other.tp_dict
        # return self

    def extract_type(self):
        return f"module {self.tp_name}"

    def custom_getattr(self, name):
        if name not in self.tp_dict:
            raise AttributeError(name)
        value = Value()
        one_value = self.tp_dict.read_value(name)
        value.inject(one_value)
        value = refine_value(value)
        return value

    def __repr__(self):
        return f"analysis-module {self.tp_uuid}"


sys.AnalysisModule = AnalysisModule


class AnalysisFunction(Analysis):
    def __init__(
        self,
        tp_uuid: int,
        tp_code: Tuple[int, int],
        tp_module: str,
        tp_defaults,
        tp_kwdefaults,
        tp_address,
        tp_generator: bool = False,
        tp_name: str = None,
    ):
        # tp_uuid is flow label
        self.tp_uuid: str = str(tp_uuid)
        self.tp_class = Function_Type
        self.tp_code: Tuple[int, int] = tp_code
        self.tp_module: str = tp_module
        self.tp_dict: UnionNamespace = UnionNamespace()
        self.tp_defaults = tp_defaults
        self.tp_kwdefaults = tp_kwdefaults
        self.tp_address = tp_address
        self.tp_generator: bool = tp_generator
        self.tp_name: str = tp_name

    def __le__(self, other: AnalysisFunction):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisFunction):
        self.tp_dict += other.tp_dict
        return self

    def __repr__(self):
        return f"analysis-function {self.tp_uuid}"

    def extract_type(self):
        return f"function {self.tp_name}"


class AnalysisMethod(Analysis):
    def __init__(self, tp_function, tp_instance):
        self.tp_uuid = f"{tp_function.tp_uuid}-{tp_instance.tp_uuid}"
        # a function
        self.tp_function = tp_function
        # an instance
        self.tp_instance = tp_instance
        self.tp_module = tp_function.tp_module

    def __le__(self, other):
        return self.tp_function <= other.tp_function

    def __iadd__(self, other):
        self.tp_function += other.tp_function
        return self

    def __repr__(self):
        return f"analysis-method {self.tp_uuid}"

    def extract_type(self):
        return f"method {self.tp_function.tp_name}"


class AnalysisDescriptor(Analysis):
    def __init__(self, tp_function, *args):
        self.tp_uuid = f"{tp_function.tp_uuid}-descriptor"
        # tp_function is the descriptor function
        self.tp_function = tp_function
        self.tp_args = args

    def __repr__(self):
        return self.tp_uuid

    def extract_type(self):
        return f"function {self.tp_function.tp_name}"


class ClassmethodAnalysisInstance(AnalysisInstance):
    # args should be a single value containing analysis functions
    def __init__(self, tp_address, tp_class, functions):
        super().__init__(tp_address, tp_class)
        self.tp_container = "classmethod"
        self.tp_dict.write_local_value(self.tp_container, functions)


class StaticmethodAnalysisInstance(AnalysisInstance):
    # args should be a single value containing analysis functions
    def __init__(self, tp_address, tp_class, functions):
        super().__init__(tp_address, tp_class)
        self.tp_container = "staticmethod"
        self.tp_dict.write_local_value(self.tp_container, functions)


class PropertyAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, fget, fset, fdel, doc=None):
        super().__init__(tp_address, tp_class)
        self.tp_container = ("fget", "fset", "fdel", "doc")
        self.tp_dict.write_local_value(self.tp_container[0], fget)
        self.tp_dict.write_local_value(self.tp_container[1], fset)
        self.tp_dict.write_local_value(self.tp_container[2], fdel)
        doc_value = Value()
        doc_value.inject(None_Instance)
        doc_value.inject(Str_Instance)
        self.tp_dict.write_local_value(self.tp_container[3], doc_value)


class IteratorAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, iter_value):
        super().__init__(tp_address, tp_class)
        self.tp_container = "iterators"
        self.iterators = tuple(iter_value)
        logger.critical(self.iterators)
        self.location = 0
        self.end_location = len(self.iterators)


class GeneratorAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, init_value, *args, **kwargs):
        super().__init__(tp_address, tp_class)
        self.tp_container = "generator-internal"
        self.tp_dict.write_local_value(self.tp_container, init_value)


class RangeAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class):
        super().__init__(tp_address, tp_class)
        self.tp_container = "range-internal"
        init_container_value = type_2_value(Int_Instance)
        self.tp_dict.write_local_value(self.tp_container, init_container_value)


class ListAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class):
        super().__init__(tp_address, tp_class)
        self.tp_container = "list-internal"
        self.tp_dict.write_local_value(self.tp_container, Value())


class TupleAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class):
        super().__init__(tp_address, tp_class)
        self.tp_container = "tuple-internal"
        self.tp_dict.write_local_value(self.tp_container, Value())


class SetAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class):
        super().__init__(tp_address, tp_class)
        self.tp_container = "set-internal"
        self.tp_dict.write_local_value(self.tp_container, Value())


class FrozenSetAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class):
        super().__init__(tp_address, tp_class)
        self.tp_container = "frozenset-internal"
        self.tp_dict.write_local_value(self.tp_container, Value())


class DictAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class):
        super().__init__(tp_address, tp_class)
        self.tp_container = ("key-internal", "value-internal")
        self.tp_dict.write_local_value(self.tp_container[0], Value())
        self.tp_dict.write_local_value(self.tp_container[1], Value())


class SuperAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, tp_self, tp_mro, *args, **kwargs):
        super().__init__(tp_address, tp_class)
        self.tp_self = tp_self
        self.tp_mro = tp_mro


# translate original typeshed types to concrete typeshed types
# given a typeshed, return types
class TypeExprVisitor(ast.NodeVisitor):
    def __init__(self, typeshed):
        # module to identify names
        self.typeshed = typeshed

    def refine(self) -> Value:
        """
        refine coarse typeshed types to refined types, such as importedname to functions or classes

        :return:
        """
        value = Value()
        if not isinstance(self.typeshed, Typeshed):
            value.inject(self.typeshed)
            return value

        if isinstance(self.typeshed, TypeshedImportedModule):
            module_value = parse_typeshed_module(self.typeshed.tp_imported_module)
            value.inject(module_value)
        elif isinstance(self.typeshed, TypeshedImportedName):
            module_value = parse_typeshed_module(self.typeshed.tp_imported_module)
            assert len(module_value) == 1
            for module in module_value:
                if self.typeshed.tp_imported_name in module:
                    one_value = module.tp_dict.read_value(
                        self.typeshed.tp_imported_name
                    )
                    for sub_value in one_value:
                        sub_visitor = TypeExprVisitor(sub_value)
                        refined_sub_value = sub_visitor.refine()
                        value.inject(refined_sub_value)
                    value.inject(one_value)
                else:
                    value.inject(Value.make_any())
        elif isinstance(
            self.typeshed,
            (
                TypeshedClass,
                TypeshedFunction,
                TypeshedModule,
            ),
        ):
            value.inject(self.typeshed)
        elif isinstance(self.typeshed, TypeshedDescriptorGetter):
            for getter in self.typeshed.functions:
                curr_value = self.visit(getter.returns)
                for one_curr in curr_value:
                    if isinstance(one_curr, TypeshedClass):
                        one_curr_instance = one_curr()
                        value.inject(one_curr_instance)
                    else:
                        value.inject(one_curr)
        elif isinstance(self.typeshed, TypeshedAssign):
            try:
                curr_value = self.visit(self.typeshed.tp_code)
            except RecursionError:
                return Value.make_any()
            else:
                if self.typeshed.is_annassign:
                    for one_curr in curr_value:
                        if isinstance(one_curr, TypeshedClass):
                            one_curr_instance = one_curr()
                            value.inject(one_curr_instance)
                        else:
                            value.inject(one_curr)
                else:
                    value.inject(curr_value)
        elif isinstance(self.typeshed, TypeshedInstance):
            value.inject(self.typeshed)
        else:
            raise NotImplementedError(self.typeshed)
        return value

    def generic_visit(self, node: ast.AST):
        # return Value.make_any()
        raise NotImplementedError(astor.to_source(node))

    # X | Y
    def visit_BinOp(self, node: ast.BinOp):
        if not isinstance(node.op, ast.BitOr):
            raise NotImplementedError(node)
        value = Value()
        lhs_value = self.visit(node.left)
        value.inject(lhs_value)
        rhs_value = self.visit(node.right)
        value.inject(rhs_value)
        return value

    # we maintain singleton in typeshed, so return Any
    def visit_Call(self, node: ast.Call):
        return Value.make_any()

    def visit_Num(self, node: ast.Num):
        value = Value()
        if isinstance(node.n, int):
            value.inject(Int_Type())
        elif isinstance(node.n, float):
            value.inject(Float_Type())
        else:
            value.inject(Complex_Type())
        return value

    def visit_Str(self, node: ast.Str):
        value = Value()
        value.inject(Str_Type())
        return value

    def visit_Bytes(self, node: ast.Bytes):
        value = Value()
        value.inject(Bytes_Type())
        return value

    def visit_NameConstant(self, node: ast.NameConstant):
        value = Value()
        if node.value is not None:
            value.inject(Bool_Type())
        else:
            value.inject(None_Instance)
        return value

    # types.ModuleType
    def visit_Attribute(self, node: ast.Attribute):
        value = Value()

        # compute receiver value
        receiver_value = self.visit(node.value)
        for one_receiver in receiver_value:
            if node.attr in one_receiver.tp_dict:
                attr_value = one_receiver.tp_dict.read_value(node.attr)
                value.inject(attr_value)
            else:
                raise AttributeError(node)
        refined_value = refine_value(value)
        return refined_value

    def visit_Subscript(self, node: ast.Subscript):
        if not isinstance(node.value, ast.Name):
            raise NotImplementedError(node)
        return self.visit(node.value)

    def visit_Name(self, node: ast.Name):
        id = node.id
        # if id is an identifier in
        if id in all_typing_names:
            return Value.make_any()

        value = Value()
        if id in all_builtin_names:
            builtin_visitor = TypeExprVisitor(
                TypeshedAssign(
                    tp_name=id,
                    tp_module="builtins",
                    tp_qualname=f"builtins.{id}",
                    tp_code=ast.Name(id=id),
                )
            )
            res = builtin_visitor.refine()
            value.inject(res)
            return value

        # check if it's in module
        # get typeshed module
        modules: Value = parse_typeshed_module(self.typeshed.tp_module)
        for module in modules:
            if id in module.tp_dict:
                name_value = module.tp_dict.read_value(id)
                value.inject(name_value)
            else:
                raise AttributeError(self.typeshed.tp_module, id)
        refined_value = refine_value(value)
        return refined_value

    def visit_Index(self, node: ast.Index):
        return self.visit(node.value)

    def visit_Tuple(self, node: ast.Tuple):
        value = Value()
        for elt in node.elts:
            one_value = self.visit(elt)
            value.inject(one_value)
        return value


# further parse types
# for instance, test: int to Int_Type
# but insert other types as normal
def refine_value(value_to_to_refined: Value):

    result_value = Value()
    for one_type in value_to_to_refined:
        if isinstance(one_type, Typeshed):
            visitor = TypeExprVisitor(one_type)
            one_value = visitor.refine()
            result_value.inject(one_value)
        else:
            result_value.inject(one_type)
    return result_value


# resolve type returns to types
def _function_refine_self_to_value(self: TypeshedFunction, *args, **kwargs):
    visitor = TypeExprVisitor(self)
    value = Value()
    for function in self.functions:
        _val = visitor.visit(function.returns)
        for one_val in _val:
            if isinstance(one_val, TypeshedClass):
                instance_val = one_val()
                value.inject(instance_val)
            else:
                value.inject(one_val)
    return value


TypeshedFunction.refine_self_to_value = _function_refine_self_to_value
TypeshedDescriptorGetter.refine_self_to_value = _function_refine_self_to_value


def _assign_refine_self_to_value(self: TypeshedAssign, *args, **kwargs):
    visitor = TypeExprVisitor(self)
    value = Value()
    expr: ast.expr = self.tp_code
    _val = visitor.visit(expr)
    value.inject(_val)
    return value


TypeshedAssign.refine_self_to_value = _assign_refine_self_to_value


def _object_call(self, tp_address, tp_class, *args, **kwargs):
    return AnalysisInstance(tp_address=tp_address, tp_class=tp_class)


Object_Type.__call__ = _object_call
