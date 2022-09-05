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
import builtins
import sys
from types import FunctionType
from typing import Tuple

from dmf.analysis.artificial_basic_types import (
    ArtificialClass,
    ArtificialFunction,
    Type_Type,
    Object_Type,
    c3,
    None_Type,
    NotImplemented_Type,
    Ellipsis_Type,
)
from dmf.analysis.context_sensitivity import record
from dmf.analysis.implicit_names import PACKAGE_FLAG, NAME_FLAG
from dmf.analysis.namespace import Namespace
from dmf.analysis.special_types import MRO_Any
from dmf.analysis.typeshed_types import (
    TypeshedModule,
    TypeshedFunction,
    TypeshedClass,
    TypeshedAssign,
    TypeshedAnnAssign,
    parse_typeshed_module,
    TypeshedInstance,
    extract_1value,
    Typeshed,
    resolve_typeshed_value,
    TypeshedDescriptorGetter,
    resolve_typeshed_type,
)
from dmf.analysis.value import Value, type_2_value
from dmf.log.logger import logger

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
Int_Instance = TypeshedInstance("int", "builtins", "builtins.int", Int_Type)

Float_Types: Value = builtin_module_dict.read_value("float")
Float_Type = extract_1value(Float_Types)
Float_Instance = TypeshedInstance("float", "builtins", "builtins.float", Float_Type)

Str_Types: Value = builtin_module_dict.read_value("str")
Str_Type = extract_1value(Str_Types)
Str_Instance = TypeshedInstance("str", "builtins", "builtins.str", Str_Type)

Bytes_Types: Value = builtin_module_dict.read_value("bytes")
Bytes_Type = extract_1value(Bytes_Types)
Bytes_Instance = TypeshedInstance("bytes", "builtins", "builtins.bytes", Bytes_Type)

ByteArray_Types: Value = builtin_module_dict.read_value("bytearray")
ByteArray_Type = extract_1value(ByteArray_Types)
ByteArray_Instance = TypeshedInstance(
    "bytearray", "builtins", "builtins.bytearray", ByteArray_Type
)

Bool_Types: Value = builtin_module_dict.read_value("bool")
Bool_Type = extract_1value(Bool_Types)
Bool_Instance = TypeshedInstance("bool", "builtins", "builtins.bool", Bool_Type)


# special enough
None_Instance = TypeshedInstance("None", "builtins", "builtins-None", None_Type)
NotImplemented_Instance = TypeshedInstance(
    "NotImplemented", "builtins", "builtins-NotImplemented", NotImplemented_Type
)
Ellipsis_Instance = TypeshedInstance(
    "ellipsis", "builtins", "builtins-ellipsis", Ellipsis_Type
)

# NotImplemented_Types: Value = builtin_module_dict.read_value("NotImplemented")
# NotImplemented_Type = extract_1value(NotImplemented_Types)
# Ellipsis_Types: Value = builtin_module_dict.read_value("Ellipsis")
# Ellipsis_Type = extract_1value(Ellipsis_Types)

Typeshed_Type_Type: Value = builtin_module_dict.read_value("type")
Type_Type.tp_fallback = Typeshed_Type_Type
builtin_module_dict.write_local_value("type", type_2_value(Type_Type))

Typeshed_Object_Type: Value = builtin_module_dict.read_value("object")
Object_Type.tp_fallback = Typeshed_Object_Type
builtin_module_dict.write_local_value("object", type_2_value(Object_Type))

# minic object.__new__
class Constructor:
    def __init__(self):
        self.tp_uuid = "arti-builtins.object.__new__"
        self.tp_class = Function_Type

    def __call__(self, tp_address, tp_class, tp_heap):
        tp_uuid = f"{tp_address}"
        tp_dict = tp_heap.write_instance_to_heap(tp_uuid)
        analysis_instance = AnalysisInstance(
            tp_address=tp_uuid, tp_dict=tp_dict, tp_class=tp_class
        )

        return analysis_instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return "object.__new__"


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
    def __call__(self, tp_address, tp_class, *args):
        # super(type1, type2)
        assert len(args) == 2, args
        type1_value, type2_value = args
        assert len(type1_value) == 1, type1_value
        assert len(type2_value) == 1, type2_value
        type1 = extract_1value(type1_value)
        type2 = extract_1value(type2_value)
        assert isinstance(type2, AnalysisInstance)

        type_type2 = type2.tp_class
        type_type2_mros = type_type2.tp_mro
        super_mros = []
        for type_type2_mro in type_type2_mros:
            found_in_curr_mro = False
            # each is a list [xxx, yyy, zzz]
            for idx, curr_type in enumerate(type_type2_mro):
                if type_type2.tp_uuid == type1.tp_uuid:
                    one_mro = type_type2_mro[idx + 1 :]
                    super_mros.append(one_mro)
                    found_in_curr_mro = True
                    break
            if not found_in_curr_mro:
                super_mros.append([MRO_Any])

        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        setattr(tp_dict, "super_self", type2)
        setattr(tp_dict, "super_mros", super_mros)
        return AnalysisInstance(tp_address, tp_class, tp_dict)


Super_Type = SuperArtificialClass("builtins.super")
Typeshed_Super_Type: Value = builtin_module_dict.read_value("super")
Super_Type.tp_fallback = Typeshed_Super_Type
builtin_module_dict.write_local_value("super", type_2_value(Super_Type))


# mimic builtins.property
class PropertyArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args):
        assert len(args) == 4, args
        fget, fset, fdel, doc, *_ = args

        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return PropertyAnalysisInstance(tp_address, tp_class, tp_dict, fget, fset, fdel)


Property_Type = PropertyArtificialClass("builtins.property")
Typeshed_Property_Type: Value = builtin_module_dict.read_value("property")
Property_Type.tp_fallback = Typeshed_Property_Type
builtin_module_dict.write_local_value("property", type_2_value(Property_Type))

# mimic builtins.classmethod
class ClassmethodArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args):
        assert len(args) == 1, args
        function, *_ = args
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return ClassmethodAnalysisInstance(tp_address, tp_class, tp_dict, function)


Classmethod_Type = ClassmethodArtificialClass("builtins.classmethod")
Typeshed_Classmethod_Type: Value = builtin_module_dict.read_value("classmethod")
Classmethod_Type.tp_fallback = Typeshed_Classmethod_Type
builtin_module_dict.write_local_value("classmethod", type_2_value(Classmethod_Type))

# mimic builtins.staticmethod
class StaticmethodArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *args):
        assert len(args) == 1, args
        function, *_ = args
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return StaticmethodAnalysisInstance(tp_address, tp_class, tp_dict, function)


Staticmethod_Type = StaticmethodArtificialClass("builtins.staticmethod")
Typeshed_Staticmethod_Type: Value = builtin_module_dict.read_value("staticmethod")
Staticmethod_Type.tp_fallback = Typeshed_Staticmethod_Type
builtin_module_dict.write_local_value("staticmethod", type_2_value(Staticmethod_Type))

# mimic generator
class GeneratorArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *arguments):
        # arguments contain all yielded types
        assert len(arguments) == 1
        init_container_value, *_ = arguments

        logger.critical(arguments)
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return GeneratorAnalysisInstance(
            tp_address, tp_class, tp_dict, init_container_value
        )


Generator_Type = GeneratorArtificialClass("types.GeneratorType")
Typeshed_Generator_Type: Value = types_module_dict.read_value("GeneratorType")
Generator_Type.tp_fallback = Typeshed_Generator_Type
types_module_dict.write_local_value("GeneratorType", type_2_value(Generator_Type))


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
    def __call__(self, tp_address, tp_class, *argument):
        init_container_value = type_2_value(Int_Instance)
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return RangeAnalysisInstance(
            tp_address, tp_class, tp_dict, init_container_value
        )


Range_Type = RangeArtificialClass("builtins.range")

Typeshed_Range_Type: Value = builtin_module_dict.read_value("range")
Range_Type.tp_fallback = Typeshed_Range_Type
builtin_module_dict.write_local_value("range", type_2_value(Range_Type))


def _setup_Range_Type():
    def __iter__(self):
        value = Value()
        for type in self:
            if isinstance(type, RangeAnalysisInstance):
                iterator_tp_address = f"{type.tp_address}-range-iterator"
                list_value = type.tp_dict.read_value(type.tp_container)
                one_type = Iterator_Type(iterator_tp_address, Iterator_Type, list_value)
                value.inject(one_type)
            else:
                raise NotImplementedError(type.tp_class)
        return value

    methods = filter(lambda symbol: isinstance(symbol, FunctionType), locals().values())
    for method in methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"builtins.range.{method.__name__}"
        )
        Range_Type.tp_dict.write_local_value(method.__name__, type_2_value(arti_method))


_setup_Range_Type()


class ListArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *arguments):
        if len(arguments) == 0:
            init_container_value = Value()
        else:
            init_container_value = Value().make_any()
        logger.critical(arguments)
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return ListAnalysisInstance(tp_address, tp_class, tp_dict, init_container_value)


List_Type = ListArtificialClass("builtins.list")
Typeshed_List_Type: Value = builtin_module_dict.read_value("list")
List_Type.tp_fallback = Typeshed_List_Type
builtin_module_dict.write_local_value("list", type_2_value(List_Type))


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
            if isinstance(one_self, ListAnalysisInstance):
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
            tp_function=method, tp_qualname=f"builtins.list.{method.__name__}"
        )
        List_Type.tp_dict.write_local_value(method.__name__, type_2_value(arti_method))


_setup_List_Type()


class TupleArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *arguments):
        if len(arguments) == 0:
            init_container_value = Value()
        else:
            init_container_value = Value().make_any()
        logger.critical(arguments)
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return TupleAnalysisInstance(
            tp_address, tp_class, tp_dict, init_container_value
        )


Tuple_Type = TupleArtificialClass("builtins.tuple")
Typeshed_Tuple_Type: Value = builtin_module_dict.read_value("tuple")
Tuple_Type.tp_fallback = Typeshed_Tuple_Type
builtin_module_dict.write_local_value("tuple", type_2_value(Tuple_Type))


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
    def __call__(self, tp_address, tp_class, *arguments):
        if len(arguments) == 0:
            init_container_value = Value()
        else:
            init_container_value = Value().make_any()
        logger.critical(arguments)
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return SetAnalysisInstance(tp_address, tp_class, tp_dict, init_container_value)


Set_Type = SetArtificialClass("builtins.set")
Typeshed_Set_Type: Value = builtin_module_dict.read_value("set")
Set_Type.tp_fallback = Typeshed_Set_Type
builtin_module_dict.write_local_value("set", type_2_value(Set_Type))


class FrozensetArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *arguments):
        if len(arguments) == 0:
            init_container_value = Value()
        else:
            init_container_value = Value().make_any()
        logger.critical(arguments)
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return FrozenSetAnalysisInstance(
            tp_address, tp_class, tp_dict, init_container_value
        )


Frozenset_Type = FrozensetArtificialClass("builtins.frozenset")
Typeshed_Frozenset_Type: Value = builtin_module_dict.read_value("frozenset")
Frozenset_Type.tp_fallback = Typeshed_Frozenset_Type
builtin_module_dict.write_local_value("frozenset", type_2_value(Frozenset_Type))


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
    def __call__(self, tp_address, tp_class, *arguments):
        # class dict(**kwargs)¶
        # class dict(mapping, **kwargs)
        # class dict(iterable, **kwargs)
        if len(arguments) == 0:
            init_key_value = Value()
            init_value_value = Value()
        else:
            init_key_value = Value.make_any()
            init_value_value = Value.make_any()
        logger.critical(arguments)
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        return DictAnalysisInstance(
            tp_address, tp_class, tp_dict, init_key_value, init_value_value
        )


Dict_Type = DictArtificialClass("builtins.dict")
Typeshed_Dict_Type: Value = builtin_module_dict.read_value("dict")
Dict_Type.tp_fallback = Typeshed_Dict_Type
builtin_module_dict.write_local_value("dict", type_2_value(Dict_Type))


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
    def __call__(self, tp_address, tp_class, *args):
        value, *_ = args
        # create instance dict
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        # create an iterator
        return IteratorAnalysisInstance(tp_address, tp_class, tp_dict, value)


Iterator_Type = IteratorArtificialClass("builtins.iterator")


def _setup_Iterator_Type():
    def __next__(self):
        value = Value()
        for one_type in self:
            one_value = one_type.tp_dict.read_value(one_type.tp_container)
            for each_one_value in one_value:
                _value = builtins.next(each_one_value)
                value.inject(_value)
        return value

    methods = filter(lambda symbol: isinstance(symbol, FunctionType), locals().values())
    for method in methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"builtins.iterator.{method.__name__}"
        )
        Iterator_Type.tp_dict.write_local_value(
            method.__name__, type_2_value(arti_method)
        )


_setup_Iterator_Type()

# true iterator, stored in heap
class Iterator:
    def __init__(self, tp_uuid, value):
        self.tp_uuid = tp_uuid
        if isinstance(value, Value):
            self.internal = list(value.values())
        else:
            raise NotImplementedError(value)

    def __next__(self) -> Value:
        value = Value()
        try:
            elt = self.internal.pop()
        except IndexError:
            return value
        else:
            value.inject(elt)
            return value

    def __le__(self, other: Iterator):
        # means no elements in iterator
        # raise NotImplementedError
        logger.critical(
            f"self.internal: {self.internal}, other.internal: {other.internal}"
        )
        return len(self.internal) == 0 and len(other.internal) == 0

    def __iadd__(self, other: Iterator):
        # raise NotImplementedError
        logger.critical(
            f"self.internal: {self.internal}, other.internal: {other.internal}"
        )
        return self


class AnalysisClass:
    def __init__(self, tp_uuid, tp_bases, tp_module, tp_dict, tp_code):
        # tp_uuid is flow label
        self.tp_uuid: str = str(tp_uuid)

        self.tp_class = Type_Type
        self.tp_bases = tp_bases
        self.tp_mro = c3(self)

        self.tp_module = tp_module
        self.tp_dict = tp_dict
        self.tp_code = tp_code

    def __le__(self, other: AnalysisClass):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisClass):
        self.tp_dict += other.tp_dict
        return self

    def __repr__(self):
        return f"analysis-class {self.tp_uuid}"


class AnalysisModule:
    def __init__(self, tp_name: str, tp_package: str, tp_code):
        # tp_uuid is module name
        self.tp_uuid: str = tp_name
        # same as tp_name
        self.tp_name: str = tp_name
        self.tp_class = Module_Type
        self.tp_package: str = tp_package
        self.tp_dict: Namespace = Namespace()
        setattr(self.tp_dict, PACKAGE_FLAG, self.tp_package)
        setattr(self.tp_dict, NAME_FLAG, self.tp_uuid)
        # entry and exit label of a module
        self.tp_code = tp_code

    def __le__(self, other: AnalysisModule):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisModule):
        self.tp_dict += other.tp_dict
        return self

    def __repr__(self):
        return f"analysis-module {self.tp_uuid}"


sys.AnalysisModule = AnalysisModule


class AnalysisFunction:
    def __init__(
        self,
        tp_uuid: int,
        tp_code: Tuple[int, int],
        tp_module: str,
        tp_defaults,
        tp_kwdefaults,
        tp_generator: bool = False,
    ):
        # tp_uuid is flow label
        self.tp_uuid: str = str(tp_uuid)
        self.tp_class = Function_Type
        self.tp_code: Tuple[int, int] = tp_code
        self.tp_module: str = tp_module
        self.tp_dict: Namespace = Namespace()
        self.tp_defaults = tp_defaults
        self.tp_kwdefaults = tp_kwdefaults
        self.tp_generator: bool = tp_generator

    def __le__(self, other: AnalysisFunction):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisFunction):
        self.tp_dict += other.tp_dict
        return self

    def __repr__(self):
        return f"analysis-function {self.tp_uuid}"


class AnalysisMethod:
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


class AnalysisDescriptor:
    def __init__(self, tp_function, *args):
        self.tp_uuid = f"{tp_function.tp_uuid}-descriptor"
        # tp_function is the descriptor function
        self.tp_function = tp_function
        self.tp_args = args

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.tp_uuid


class AnalysisInstance:
    def __init__(self, tp_address, tp_class, tp_dict):
        self.tp_uuid = tp_address
        self.tp_address = tp_address
        self.tp_class = tp_class
        self.tp_dict = tp_dict

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return f"{self.tp_class.tp_uuid} object"


class ClassmethodAnalysisInstance(AnalysisInstance):
    # args should be a single value containing analysis functions
    def __init__(self, tp_address, tp_class, tp_dict, value):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = "function"
        tp_dict.write_local_value(self.tp_container, value)


class StaticmethodAnalysisInstance(AnalysisInstance):
    # args should be a single value containing analysis functions
    def __init__(self, tp_address, tp_class, tp_dict, value):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = "function"
        tp_dict.write_local_value(self.tp_container, value)


class PropertyAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, tp_dict, fget, fset, fdel, doc=None):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = ("fget", "fset", "fdel", "doc")
        tp_dict.write_local_value(self.tp_container[0], fget)
        tp_dict.write_local_value(self.tp_container[1], fset)
        tp_dict.write_local_value(self.tp_container[2], fdel)
        doc_value = Value()
        doc_value.inject(None_Instance)
        doc_value.inject(Str_Instance)
        tp_dict.write_local_value(self.tp_container[3], doc_value)


class IteratorAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, tp_dict, init_value):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = "iterators"
        iterator = Iterator(tp_address, init_value)
        tp_dict.write_local_value(self.tp_container, type_2_value(iterator))


class GeneratorAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, tp_dict, init_value):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = "internal"
        tp_dict.write_local_value(self.tp_container, init_value)


class RangeAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, tp_dict, init_value):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = "internal"
        tp_dict.write_local_value(self.tp_container, init_value)


class ListAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, tp_dict, initial_value):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = "internal"
        tp_dict.write_local_value(self.tp_container, initial_value)


class TupleAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, tp_dict, initial_value):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = "internal"
        tp_dict.write_local_value(self.tp_container, initial_value)


class SetAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, tp_dict, initial_value):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = "internal"
        tp_dict.write_local_value(self.tp_container, initial_value)


class FrozenSetAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, tp_dict, initial_value):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = "internal"
        tp_dict.write_local_value(self.tp_container, initial_value)


class DictAnalysisInstance(AnalysisInstance):
    def __init__(self, tp_address, tp_class, tp_dict, initial_value1, initial_value2):
        super().__init__(tp_address, tp_class, tp_dict)
        self.tp_container = ("internal1", "internal2")
        tp_dict.write_local_value(self.tp_container[0], initial_value1)
        tp_dict.write_local_value(self.tp_container[1], initial_value2)


class TypeExprVisitor(ast.NodeVisitor):
    def __init__(self, module: str):
        # module to identify names
        self.module: str = module

    def visit_BinOp(self, node: ast.BinOp):
        value = Value()
        if not isinstance(node.op, ast.BitOr):
            raise NotImplementedError
        lhs_value = self.visit(node.left)
        value.inject(lhs_value)
        rhs_value = self.visit(node.right)
        value.inject(rhs_value)
        return value

    def visit_Num(self, node: ast.Num):
        if isinstance(node.n, int):
            value = type_2_value(Int_Instance)
            return value
        elif isinstance(node.n, float):
            value = type_2_value(Float_Instance)
            return value
        else:
            raise NotImplementedError(node)

    def visit_Str(self, node: ast.Str):
        value = type_2_value(Str_Instance)
        return value

    def visit_Bytes(self, node: ast.Bytes):
        value = type_2_value(Bytes_Instance)
        return value

    def visit_NameConstant(self, node: ast.NameConstant):
        if node.value is not None:
            value = type_2_value(Bool_Instance)
            return value
        else:
            value = type_2_value(None_Instance)
            return value

    def visit_Ellipsis(self, node: ast.Ellipsis):
        value = type_2_value(Ellipsis_Instance)
        return value

    def visit_Constant(self, node: ast.Constant):
        raise NotImplementedError

    def visit_Attribute(self, node: ast.Attribute):
        value = Value()

        receiver_visitor = TypeExprVisitor(self.module)
        receiver_value = receiver_visitor.visit(node.value)
        receiver_value = refine_value(receiver_value)
        for one in receiver_value:
            if node.attr in one.tp_dict:
                value.inject(one.tp_dict.read_value(node.attr))
            else:
                raise NotImplementedError(node)
        return value

    def visit_Subscript(self, node: ast.Subscript):
        if not isinstance(node.value, ast.Name):
            raise NotImplementedError(node)
        if node.value.id == "Literal":
            return self.visit(node.slice)
        return self.visit(ast.Name(id="Any"))

    def visit_Index(self, node: ast.Index):
        return self.visit(node.value)

    def visit_Starred(self, node: ast.Starred):
        raise NotImplementedError

    def visit_Name(self, node: ast.Name):
        id = node.id
        if id == "bool":
            value = type_2_value(Bool_Instance)
            return value
        elif id == "int":
            value = type_2_value(Int_Instance)
            return value
        elif id == "float":
            value = type_2_value(Float_Instance)
            return value
        elif id == "complex":
            raise NotImplementedError(node)
        elif id == "list":
            raise NotImplementedError
        elif id == "range":
            raise NotImplementedError
        elif id == "Any":
            return Value.make_any()
        elif id == "str":
            value = type_2_value(Str_Instance)
            return value
        elif id == "bytes":
            value = type_2_value(Bytes_Instance)
            return value
        elif id == "bytearray":
            raise NotImplementedError(node)
        elif id == "memoryview":
            raise NotImplementedError
        elif id == "set":
            raise NotImplementedError
        elif id == "frozenset":
            raise NotImplementedError
        elif id == "dict":
            raise NotImplementedError
        else:
            # check if it's in module
            value = Value()
            modules: Value = parse_typeshed_module(self.module)
            for module in modules:
                if id in module.tp_dict:
                    name_info = module.tp_dict.read_value(id)
                    res = refine_value(name_info)
                    value.inject(res)
            return value


# further parse types
# for instance, test: int to Int_Type
# but insert other types as normal
def refine_value(value_to_to_refined: Value):
    # at first resolve typeshed attributes, if any
    normalized_types = resolve_typeshed_value(value_to_to_refined)

    value = Value()
    for type in normalized_types:
        if isinstance(type, Typeshed):
            sub_value = refine_type(type)
            value.inject(sub_value)
        else:
            value.inject(type)

    return value


def refine_type(typeshed_type) -> Value:
    if isinstance(typeshed_type, Typeshed):
        typeshed_type_value = resolve_typeshed_type(typeshed_type)
    else:
        return type_2_value(typeshed_type)

    value = Value()
    for typeshed_type in typeshed_type_value:
        if isinstance(
            typeshed_type,
            (TypeshedModule, TypeshedClass, TypeshedFunction, TypeshedInstance),
        ):
            value.inject(typeshed_type)
        elif isinstance(typeshed_type, TypeshedDescriptorGetter):
            # extract returns of functions
            for getter in typeshed_type.functions:
                visitor: TypeExprVisitor = TypeExprVisitor(typeshed_type.tp_module)
                value.inject(visitor.visit(getter.returns))
        elif isinstance(typeshed_type, TypeshedAnnAssign):
            visitor = TypeExprVisitor(typeshed_type.tp_module)
            value.inject(visitor.visit(typeshed_type.tp_code.annotation))
        elif isinstance(typeshed_type, TypeshedAssign):
            visitor = TypeExprVisitor(typeshed_type.tp_module)
            value.inject(visitor.visit(typeshed_type.tp_code.value))
        else:
            raise NotImplementedError(typeshed_type)
    return value


def _function_resolve_self_to_value(self: TypeshedFunction, *args, **kwargs):
    visitor = TypeExprVisitor(self.tp_module)
    value = Value()
    for function in self.functions:
        _val = visitor.visit(function.returns)
        value.inject(_val)
    return value


TypeshedFunction.resolve_self_to_value = _function_resolve_self_to_value
