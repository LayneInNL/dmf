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
from typing import Tuple

from dmf.analysis.artificial_basic_types import (
    ArtificialClass,
    ArtificialFunction,
    Type_Type,
    Object_Type,
    c3,
    None_Type,
    Singleton,
    Immutable,
)
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
    resolve_typeshed_type,
    resolve_typeshed_types,
)
from dmf.analysis.value import Value, type_2_value
from dmf.log.logger import logger

# since we use static analysis, builtin_module is a set of modules
# but in fact there will only be one module
builtin_modules: Value = parse_typeshed_module("builtins")
builtin_module = extract_1value(builtin_modules)
builtin_module_dict: Namespace = builtin_module.tp_dict

types_modules: Value = parse_typeshed_module("types")
types_module: TypeshedModule = extract_1value(types_modules)
types_module_dict: Namespace = types_module.tp_dict

Module_Types: Value = types_module_dict.read_value("ModuleType")
Module_Type = extract_1value(Module_Types)
TypeshedModule.tp_class = Module_Type

Function_Types: Value = types_module_dict.read_value("FunctionType")
Function_Type = extract_1value(Function_Types)

Int_Types: Value = builtin_module_dict.read_value("int")
Int_Type = extract_1value(Int_Types)
Int_Instance = TypeshedInstance("int", "builtins", "builtins-int", Int_Type)

Float_Types: Value = builtin_module_dict.read_value("float")
Float_Type = extract_1value(Float_Types)
Float_Instance = TypeshedInstance("float", "builtins", "builtins-float", Float_Type)

Str_Types: Value = builtin_module_dict.read_value("str")
Str_Type = extract_1value(Str_Types)
Str_Instance = TypeshedInstance("str", "builtins", "builtins-str", Str_Type)

Bytes_Types: Value = builtin_module_dict.read_value("bytes")
Bytes_Type = extract_1value(Bytes_Types)
Bytes_Instance = TypeshedInstance("bytes", "builtins", "builtins-bytes", Bytes_Type)

ByteArray_Types: Value = builtin_module_dict.read_value("bytearray")
ByteArray_Type = extract_1value(ByteArray_Types)
ByteArray_Instance = TypeshedInstance(
    "bytearray", "builtins", "builtins-bytearray", ByteArray_Type
)

Bool_Types: Value = builtin_module_dict.read_value("bool")
Bool_Type = extract_1value(Bool_Types)
Bool_Instance = TypeshedInstance("bool", "builtins", "builtins-bool", Bool_Type)


# special enough
None_Instance = TypeshedInstance("None", "builtins", "builtins-None", None_Type)

NotImplemented_Types: Value = builtin_module_dict.read_value("NotImplemented")
NotImplemented_Type = extract_1value(NotImplemented_Types)
NotImplemented_Instance = TypeshedInstance(
    "NotImplemented", "builtins", "builtins-NotImplemented", NotImplemented_Type
)
Ellipsis_Types: Value = builtin_module_dict.read_value("Ellipsis")
Ellipsis_Type = extract_1value(Ellipsis_Types)
Ellipsis_Instance = TypeshedInstance(
    "ellipsis", "builtins", "builtins-ellipsis", Ellipsis_Type
)

Typeshed_Type_Type: Value = builtin_module_dict.read_value("type")
Type_Type.tp_fallback = Typeshed_Type_Type
builtin_module_dict.write_local_value("type", type_2_value(Type_Type))

# minic object.__new__
class Constructor(Singleton, Immutable):
    def __init__(self):
        self.tp_uuid = id(self)
        self.tp_class = Function_Type

    def __call__(self, tp_address, tp_class, tp_heap):
        # tp_uuid = f"{tp_address}-{tp_class.tp_uuid}"
        tp_uuid = f"{tp_address}"
        tp_dict = tp_heap.write_instance_to_heap(tp_uuid)
        analysis_instance = AnalysisInstance(
            tp_address=tp_uuid, tp_dict=tp_dict, tp_class=tp_class
        )

        return analysis_instance


constructor = Constructor()


def _setup_Object_Type():
    def __init__(self):
        return self

    init = ArtificialFunction(
        tp_function=__init__, tp_qualname="builtins.object.__init__"
    )
    Object_Type.tp_dict.write_local_value("__init__", type_2_value(init))

    Object_Type.tp_dict.write_local_value("__new__", type_2_value(constructor))


_setup_Object_Type()


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
        fget, fset, fdel, doc = args

        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        tp_dict.write_local_value("fget", fget)
        tp_dict.write_local_value("fset", fset)
        tp_dict.write_local_value("fdel", fdel)
        tp_dict.write_local_value("doc", doc)
        return AnalysisInstance(
            tp_address=tp_address, tp_class=tp_class, tp_dict=tp_dict
        )


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
        tp_dict.write_local_value("function", function)
        return AnalysisInstance(
            tp_address=tp_address, tp_class=tp_class, tp_dict=tp_dict
        )


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
        tp_dict.write_local_value("function", function)
        return AnalysisInstance(
            tp_address=tp_address, tp_class=tp_class, tp_dict=tp_dict
        )


Staticmethod_Type = StaticmethodArtificialClass("builtins.staticmethod")
Typeshed_Staticmethod_Type: Value = builtin_module_dict.read_value("staticmethod")
Staticmethod_Type.tp_fallback = Typeshed_Staticmethod_Type
builtin_module_dict.write_local_value("staticmethod", type_2_value(Staticmethod_Type))


class ListArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, *arguments):
        if len(arguments) == 0:
            init_container_value = Value()
        else:
            init_container_value = Value().make_any()
        logger.critical(arguments)
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        setattr(tp_dict, "container_type", "list")
        tp_dict.write_local_value("internal", Value())
        return AnalysisInstance(tp_address, tp_class, tp_dict)


List_Type = ListArtificialClass("builtins.list")

Typeshed_List_Type: Value = builtin_module_dict.read_value("list")
List_Type.tp_fallback = Typeshed_List_Type
builtin_module_dict.write_local_value("list", type_2_value(List_Type))


def _setup_List_Type():
    def __init__(self, iterable=None):
        pass

    def append(self, x):
        value = Value()
        value.inject(x)

        prev_value = self.tp_dict.read_value("internal")
        value.inject(prev_value)
        self.tp_dict.write_local_value("internal", value)
        return type_2_value(None_Instance)

    arti_append = ArtificialFunction(
        tp_function=append, tp_qualname="builtins.list.append"
    )
    arti_append_value = type_2_value(arti_append)
    List_Type.tp_dict.write_local_value(append.__name__, arti_append_value)

    def __iter__(self):
        if self.is_Any():
            return Value.make_any()
        # find list type
        value = Value()
        for type in self:
            if isinstance(type.tp_class, ListArtificialClass):
                iterator_tp_address = f"{type.tp_address}-list-iterator"
                list_value = type.tp_dict.read_value("internal")
                one_type = List_Iterator_Type(
                    iterator_tp_address, List_Iterator_Type, list_value
                )
                value.inject(one_type)
            else:
                raise NotImplementedError(type.tp_class)
        return value

    arti_iter = ArtificialFunction(
        tp_function=__iter__, tp_qualname="builtins.list.__iter__"
    )
    arti_iter_value = type_2_value(arti_iter)
    List_Type.tp_dict.write_local_value(__iter__.__name__, arti_iter_value)


_setup_List_Type()


class TupleArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, tp_heap, *arguments):
        tp_dict = tp_heap.write_instance_to_heap(tp_address)
        tp_dict.write_local_value("internal", Value())
        return AnalysisInstance(tp_address, tp_class, tp_dict)


Tuple_Type = TupleArtificialClass("builtins.tuple")


class SetArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, tp_heap, *arguments):
        tp_dict = tp_heap.write_instance_to_heap(tp_address)
        tp_dict.write_local_value("internal", Value())
        return AnalysisInstance(tp_address, tp_class, tp_dict)


Set_Type = SetArtificialClass("builtins.set")


class FrozensetArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, tp_heap, *arguments):
        tp_dict = tp_heap.write_instance_to_heap(tp_address)
        tp_dict.write_local_value("internal", Value())
        return AnalysisInstance(tp_address, tp_class, tp_dict)


Frozenset_Type = FrozensetArtificialClass("builtins.frozenset")


class DictArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, tp_heap, *arguments):
        tp_dict = tp_heap.write_instance_to_heap(tp_address)
        tp_dict.write_local_value("internal", Value())
        return AnalysisInstance(tp_address, tp_class, tp_dict)


Dict_Type = DictArtificialClass("builtins.dict")


class ListIteratorArtificialClass(ArtificialClass):
    def __call__(self, tp_address, tp_class, value):
        # create instance dict
        tp_dict = sys.heap.write_instance_to_heap(tp_address)
        # create an iterator
        iterator = Iterator(tp_address, value)
        # read instance dict
        value = Value()
        value.inject(iterator)
        tp_dict.write_local_value("iterators", value)
        return AnalysisInstance(tp_address, tp_class, tp_dict)


List_Iterator_Type = ListIteratorArtificialClass("builtins.iterator")


def _setup_List_Iterator_Type():
    def __next__(self):
        if self.is_Any():
            return Value.make_any()

        value = Value()
        for one_type in self:
            one_value = one_type.tp_dict.read_value("iterators")
            if one_value.is_Any():
                return Value.make_any()

            for each_one_value in one_value:
                _value = builtins.next(each_one_value)
                value.inject(_value)
        return value

    arti_next = ArtificialFunction(
        tp_function=__next__, tp_qualname="builtins.list_iterator.__next__"
    )
    List_Iterator_Type.tp_dict.write_local_value(
        __next__.__name__, type_2_value(arti_next)
    )


_setup_List_Iterator_Type()


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
            elt_value = type_2_value(elt)
            value.inject(elt_value)
            return value

    def __le__(self, other: Iterator):
        # means no elements in iterator
        return len(self.internal) == 0 and len(other.internal) == 0

    def __iadd__(self, other: Iterator):
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
        return self.tp_uuid


class AnalysisModule:
    def __init__(self, tp_name: str, tp_package: str, tp_code):
        # tp_uuid is module name
        self.tp_uuid: str = tp_name
        self.tp_class = Module_Type
        self.tp_package: str = tp_package
        self.tp_dict: Namespace = Namespace()
        setattr(self.tp_dict, PACKAGE_FLAG, self.tp_package)
        setattr(self.tp_dict, NAME_FLAG, self.tp_uuid)
        self.tp_code = tp_code

    def getattr(self, name: str):
        if name in self.tp_dict:
            return self.tp_dict.read_value(name)
        raise AttributeError(name)

    def __le__(self, other: AnalysisModule):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisModule):
        self.tp_dict += other.tp_dict
        return self

    def __repr__(self):
        return f"module object {self.tp_uuid}"


sys.AnalysisModule = AnalysisModule


class AnalysisFunction:
    def __init__(
        self,
        tp_uuid: int,
        tp_code: Tuple[int, int],
        tp_module: str,
        tp_defaults,
        tp_kwdefaults,
    ):
        # tp_uuid is flow label
        self.tp_uuid: int = tp_uuid
        self.tp_class = Function_Type
        self.tp_code: Tuple[int, int] = tp_code
        self.tp_module: str = tp_module
        self.tp_dict: Namespace = Namespace()
        self.tp_defaults = tp_defaults
        self.tp_kwdefaults = tp_kwdefaults

    def __le__(self, other: AnalysisFunction):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisFunction):
        self.tp_dict += other.tp_dict
        return self

    def __repr__(self):
        return str(self.tp_uuid)


class AnalysisMethod:
    def __init__(self, tp_function, tp_instance):
        self.tp_uuid = f"{tp_function.tp_uuid}-{tp_instance.tp_uuid}"
        self.tp_function = tp_function
        self.tp_instance = tp_instance
        self.tp_module = tp_function.tp_module

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.tp_uuid


class AnalysisDescriptorGetFunction:
    def __init__(self, tp_self, tp_obj, tp_objtype, tp_function):
        self.tp_uuid = f"{tp_self.tp_uuid}-getter"
        # descriptor instance
        self.tp_self = tp_self
        # class var
        self.tp_obj = tp_obj
        # type of class var
        self.tp_objtype = tp_objtype
        # __get__ function
        self.tp_function = tp_function


class AnalysisClassmethodMethod:
    def __init__(self, tp_function, tp_instance):
        self.tp_uuid = f"{tp_function.tp_uuid}-{tp_instance.tp_uuid}-classmethod"
        self.tp_function = tp_function
        self.tp_instance = tp_instance
        self.tp_module = tp_function.tp_module

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.tp_uuid


class AnalysisStaticMethod:
    def __init__(self, tp_function):
        self.tp_uuid = f"{tp_function.tp_uuid}-staticmethod"
        self.tp_function = tp_function
        self.tp_module = tp_function.tp_module

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.tp_uuid


class AnalysisPropertyGetFunction:
    def __init__(self, tp_obj, tp_function):
        self.tp_uuid = f"{tp_obj.tp_uuid}-property-getter"
        self.tp_obj = tp_obj
        self.tp_function = tp_function

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.tp_uuid


class AnalysisDescriptorSetFunction:
    def __init__(self, tp_self, tp_obj, tp_value):
        self.tp_uuid = f"{tp_self.tp_uuid}-setter"
        self.tp_self = tp_self
        self.tp_obj = tp_obj
        self.tp_value = tp_value


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
        raise NotImplementedError

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
            return Value.make_any()
            # check if it's in module
            module: _TypeshedModule = parse_typeshed_module(self.module)
            if id in module.tp_dict:
                name_info = module.get_name(id)
                res = refine_type(name_info)
                value.inject(res)
                return value
            else:
                raise NotImplementedError


# further parse types
# for instance, test: int to Int_Type
# but insert other types as normal
def refine_value(value_to_to_refined: Value):
    if value_to_to_refined.is_Any():
        return Value.make_any()

    normalized_types = resolve_typeshed_types(value_to_to_refined)

    value = Value()
    for type in normalized_types:
        if isinstance(type, Typeshed):
            sub_value = refine_type(type)
            value.inject(sub_value)
        else:
            value.inject(type)

    return value


def refine_type(typeshed_type):

    if isinstance(typeshed_type, TypeshedModule):
        return typeshed_type
    elif isinstance(typeshed_type, TypeshedClass):
        return typeshed_type
    elif isinstance(typeshed_type, TypeshedFunction):
        if typeshed_type.ordinaries:
            return typeshed_type
        else:
            value = Value()
            if typeshed_type.getters:
                for getter in typeshed_type.getters:
                    visitor: TypeExprVisitor = TypeExprVisitor(typeshed_type.tp_module)
                    value.inject(visitor.visit(getter))
            elif typeshed_type.setters or typeshed_type.deleters:
                value.inject(None_Instance)
            return value
    elif isinstance(typeshed_type, TypeshedAnnAssign):
        visitor = TypeExprVisitor(typeshed_type.tp_module)
        value = visitor.visit(typeshed_type.tp_code.annotation)
        return value
    elif isinstance(typeshed_type, TypeshedAssign):
        raise NotImplementedError
    else:
        raise NotImplementedError


def resolve_ordinary_types(self):
    module = self.tp_module
    visitor = TypeExprVisitor(module)

    value = Value()
    for ordinary in self.ordinaries:
        one_value = visitor.visit(ordinary.returns)
        value.inject(one_value)
    return value


TypeshedFunction.resolve_ordinary_types = resolve_ordinary_types
