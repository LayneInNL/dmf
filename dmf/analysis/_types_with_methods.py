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
from typing import Tuple

from ._types import (
    Object_Type,
    Type_Type,
    Int_Type,
    Float_Type,
    Complex_Type,
    List_Type,
    Tuple_Type,
    Range_Type,
    Str_Type,
    Bytes_Type,
    ByteArray_Type,
    MemoryView_Type,
    Set_Type,
    FrozenSet_Type,
    Dict_Type,
    Module_Type,
    Function_Type,
    Method_Type,
    None_Type,
    Bool_Type,
    Namespace,
    LocalVar,
    NonlocalVar,
    GlobalVar,
    SpecialVar,
    POS_ARG_END,
    INIT_FLAG,
    RETURN_FLAG,
    Namespace_Local,
    Namespace_Nonlocal,
    Namespace_Global,
    Namespace_Helper,
    Var,
)
from .exceptions import MROAnyError
from .special_types import Any
from .value import Value
from dmf.typeshed_client.parser import (
    parse_module,
    resolve_attribute,
    TypeshedModule as _TypeshedModule,
    TypeshedClass as _TypeshedClass,
    TypeshedFunction as _TypeshedFunction,
    AnnAssignNameInfo,
    AssignNameInfo,
)


class AnalysisModule:
    def __init__(self, tp_uuid, tp_package, tp_entry, tp_exit):
        self.tp_uuid: str = tp_uuid
        self.tp_package: str = tp_package
        self.tp_dict: Namespace = Namespace()
        self.tp_entry: int = tp_entry
        self.tp_exit: int = tp_exit

    def getattr(self, name: str):
        if name in self.tp_dict:
            return self.tp_dict.read_value(name)
        raise AttributeError(name)

    def __le__(self, other: AnalysisModule):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisModule):
        self.tp_dict += other.tp_dict
        return self


class TypeshedModule:
    def __init__(self, _typeshed_module: _TypeshedModule):
        self.tp_uuid = _typeshed_module.tp_uuid
        self.tp_dict = _typeshed_module.tp_dict
        self.tp_module = _typeshed_module.module_name

    def get_name(self, attr_name: str):
        if attr_name not in self.tp_dict:
            # possible it's a module
            sub_module = f"{self.tp_module}.{attr_name}"
            return parse_module(sub_module)
        name_info = self.tp_dict[attr_name]
        return resolve_attribute(name_info)


class AnalysisFunction:
    def __init__(
        self,
        tp_uuid: int,
        tp_code: Tuple[int, int],
        tp_module: str,
        tp_defaults,
        tp_kwdefautls,
    ):
        self.tp_uuid: int = tp_uuid
        self.tp_code: Tuple[int, int] = tp_code
        self.tp_module: str = tp_module
        self.tp_dict: Namespace = Namespace()
        self.tp_defaults = tp_defaults
        self.tp_kwdefaults = tp_kwdefautls

    def __le__(self, other: AnalysisFunction):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisFunction):
        self.tp_dict += other.tp_dict
        return self


class ArtificialFunction:
    def __init__(self, function):
        self.tp_uuid = id(function)
        self.tp_code = function
        self.tp_dict = Namespace()

    def __call__(self, *args, **kwargs):
        return self.tp_code(*args, **kwargs)


class TypeshedFunction:
    def __init__(self, tp_uuid, tp_oridinaries):
        self.tp_uuid = tp_uuid
        self.tp_ordinaries = tp_oridinaries


class AnalysisMethod:
    def __init__(self, function, instance):
        self.tp_uuid = f"{function.tp_uuid}-{instance.tp_uuid}"
        self.tp_function = function
        self.tp_instance = instance
        self.tp_module = function.tp_module


class AnalysisDescriptorGetFunction:
    def __init__(self, tp_self, tp_obj, tp_objtype):
        self.tp_uuid = f"{tp_self.tp_uuid}-{tp_obj.tp_uuid}"
        self.tp_self = tp_self
        self.tp_obj = tp_obj
        self.tp_objtype = tp_objtype


class AnalysisDescriptorSetFunction:
    def __init__(self, tp_self, tp_obj, tp_value):
        self.tp_uuid = f"{tp_self.tp_uuid}-{tp_obj.tp_uuid}"
        self.tp_self = tp_self
        self.tp_obj = tp_obj
        self.tp_value = tp_value


class ArtificialMethod:
    def __init__(self, function, instance):
        self.tp_uuid = f"{function.tp_uuid}-{instance.tp_uuid}"
        self.tp_function = function
        self.tp_instance = instance


class AnalysisClass:
    def __init__(self, tp_uuid, tp_bases, tp_module, tp_dict):
        self.tp_uuid = tp_uuid
        self.tp_bases = tp_bases
        try:
            self.tp_mro = c3(self)
        except MROAnyError:
            self.tp_mro = (self, Any)
        self.tp_module = tp_module
        self.tp_dict = tp_dict

    def __le__(self, other: AnalysisClass):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisModule):
        self.tp_dict += other.tp_dict
        return self


class TypeshedClass:
    def __init__(self, tp_uuid, tp_dict):
        self.tp_uuid = tp_uuid
        self.tp_dict = tp_dict


class AnalysisInstance:
    def __init__(self, tp_address, tp_type):
        self.tp_address = tp_address
        self.tp_type = tp_type
        self.tp_uuid = f"{tp_address}-{tp_type.tp_uuid}"


class ArtificialInstance:
    def __init__(self, tp_uuid, tp_class):
        self.tp_uuid = tp_uuid
        self.tp_class = tp_class

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class AnalysisInstanceConstructor:
    def __init__(self):
        pass

    def __call__(self, address, type):
        return AnalysisInstance(address, type)


class ArtificialInstanceConstructor:
    def __init__(self):
        pass

    def __call__(self, *args, **kwargs):
        raise NotImplementedError


def _py_type(obj):
    return obj.tp_class


def _pytype_lookup(type, name):
    res = _find_name_in_mro(type, name)
    return res


def _find_name_in_mro(type, name):
    res = None

    mro = type.tp_mro
    for base in mro:
        dict = base.tp_uuid
        if name in dict:
            return dict[name]
    return res


def GenericGetAttr(obj, name):
    res_value, descr_value = Value(), Value()

    tp = _py_type(obj)
    descrs = _pytype_lookup(tp, name)
    if descrs is not None:
        for descr in descrs:
            descr_tp = _py_type(descr)
            descr_tp_get = descr_tp.tp_uuid.get("__get__", NotImplemented)
            if descr_tp_get is not NotImplemented:
                if isinstance(descr_tp_get, AnalysisFunction):
                    # self = descr, obj = obj, type=tp
                    one_descr = AnalysisDescriptorGetFunction(
                        tp_self=descr, tp_obj=obj, tp_objtype=tp
                    )
                    descr_value.inject_type(one_descr)
                elif isinstance(descr_tp_get, ArtificialFunction):
                    one_res = descr_tp_get(descr, obj, tp)
                    res_value.inject_type(one_res)
                else:
                    raise NotImplementedError

    if isinstance(obj, AnalysisInstance):
        raise NotImplementedError
    else:
        if name in obj.tp_uuid:
            one_res = obj.tp_uuid.read_value(name)
            res_value.inject_value(one_res)

    if descrs is not None:
        res_value.inject_value(descrs)

    return res_value, descr_value


def GenericSetAttr(obj, name, value):
    descr_value = Value()

    tp = _py_type(obj)
    descrs = _pytype_lookup(tp, name)
    if descrs is not None:
        for descr in descrs:
            descr_tp = _py_type(descr)
            descr_tp_set = descr_tp.tp_uuid.get("__set__", NotImplemented)
            if descr_tp_set is not NotImplemented:
                if isinstance(descr_tp_set, AnalysisFunction):
                    one_descr = AnalysisDescriptorSetFunction(
                        tp_self=descr_tp, tp_obj=obj, tp_value=value
                    )
                    descr_value.inject_type(one_descr)
                elif isinstance(descr_tp_set, ArtificialFunction):
                    descr_tp_set(descr, obj, tp)
                else:
                    raise NotImplementedError

    if isinstance(obj, AnalysisInstance):
        raise NotImplementedError
    else:
        obj.tp_uuid.write_local_value(name, value)

    return descr_value


def type_getattro(type, name):
    res_value, descr_value = Value(), Value()

    descrs = _pytype_lookup(type, name)
    if descrs is not None:
        for descr in descrs:
            descr_tp = _py_type(descr)
            descr_tp_get = descr_tp.tp_uuid.get("__get__", NotImplemented)
            if descr_tp_get is not NotImplemented:
                if isinstance(descr_tp_get, AnalysisFunction):
                    one_descr = AnalysisDescriptorGetFunction(
                        tp_self=descr, tp_obj=None_Type, tp_objtype=type
                    )
                    descr_value.inject_type(one_descr)
                elif isinstance(descr_tp_get, ArtificialFunction):
                    one_res = descr_tp_get(descr, None_Type, type)
                    res_value.inject_type(one_res)
                else:
                    raise NotImplementedError

    if name in type.tp_uuid:
        one_res = type.tp_uuid.read_value(name)
        res_value.inject_value(one_res)

    if descrs is not None:
        res_value.inject_value(descrs)

    return res_value, descr_value


def type_setattro(type, name, value):
    return GenericSetAttr(type, name, value)


class MRO(list):
    ...


class CompleteMRO(MRO):
    ...


class InCompleteMRO(MRO):
    ...


def c3(cls_obj):
    mro = static_c3(cls_obj)
    return mro[0], mro[1:]


def static_c3(cls_obj):
    if cls_obj is Object_Type:
        return [cls_obj]
    elif cls_obj.tp_bases is Any:
        raise MROAnyError
    else:
        return [cls_obj] + static_merge([static_c3(base) for base in cls_obj.tp_bases])


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


_object_getattro = ArtificialFunction(GenericGetAttr)
Object_Type.tp_dict.write_local_value("__getattribute__", _object_getattro)
_object_setattro = ArtificialFunction(GenericSetAttr)
Object_Type.tp_dict.write_local_value("__setattr__", _object_setattro)
_type_getattro = ArtificialFunction(type_getattro)
Type_Type.tp_dict.write_local_value("__getattribute__", _type_getattro)
_type_setattro = ArtificialFunction(type_getattro)
Type_Type.tp_dict.write_local_value("__setattr__", _type_setattro)

Int_Instance = ArtificialInstance(-1, Int_Type)
Float_Instance = ArtificialInstance(-2, Float_Type)
Complex_Instance = ArtificialInstance(-3, Complex_Type)
Str_Instance = ArtificialInstance(-4, Str_Type)
Bytes_Instance = ArtificialInstance(-5, Bytes_Type)
ByteArray_Instance = ArtificialInstance(-6, ByteArray_Type)
None_Instance = ArtificialInstance(-7, None_Type)
Bool_Instance = ArtificialInstance(-8, Bool_Type)

# Object,
# Type,
# List,
# Tuple,
# Range,
# MemoryView,
# Set,
# FrozenSet,
# Dict,
# Module,
# Function,
# Method,


def evaluate(name_info):
    if isinstance(name_info, _TypeshedModule):
        return TypeshedModule(name_info)
    elif isinstance(name_info, _TypeshedClass):
        return TypeshedClass(name_info.qualified_name, name_info.tp_dict)
    elif isinstance(name_info, _TypeshedFunction):
        if name_info.ordinaries:
            return TypeshedFunction(name_info.qualified_name, name_info.ordinaries)
        else:
            value = Value()
            if name_info.getters:
                for getter in name_info.getters:
                    _value = TypeExprVisitor(
                        name_info.module_name, getter.returns
                    ).evaluate()
                    value.inject_value(_value)
            elif name_info.setters or name_info.deleters:
                value.inject_type(None_Instance)
            return value
    elif isinstance(name_info, AnnAssignNameInfo):
        return TypeExprVisitor(
            name_info.module_name, name_info.node.annotation
        ).evaluate()
    elif isinstance(name_info, AssignNameInfo):
        raise NotImplementedError
    else:
        raise NotImplementedError


class TypeExprVisitor(ast.NodeVisitor):
    def __init__(self, module, expr):
        self.module = module
        self.expr = expr

    def evaluate(self):
        return self.visit(self.expr)

    def visit_BoolOp(self, node: ast.BoolOp):
        raise NotImplementedError

    def visit_BinOp(self, node: ast.BinOp):
        value = Value()
        if not isinstance(node.op, ast.BitOr):
            raise NotImplementedError
        lhs_value = self.visit(node.left)
        value.inject_value(lhs_value)
        rhs_value = self.visit(node.right)
        value.inject_value(rhs_value)
        return value

    def visit_UnaryOp(self, node: ast.UnaryOp):
        raise NotImplementedError

    def visit_Lambda(self, node: ast.Lambda):
        raise NotImplementedError

    def visit_IfExp(self, node: ast.IfExp):
        raise NotImplementedError

    def visit_Dict(self, node: ast.Dict):
        raise NotImplementedError

    def visit_Set(self, node: ast.Set):
        raise NotImplementedError

    def visit_ListComp(self, node: ast.ListComp):
        raise NotImplementedError

    def visit_SetComp(self, node: ast.SetComp):
        raise NotImplementedError

    def visit_DictComp(self, node: ast.DictComp):
        raise NotImplementedError

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        raise NotImplementedError

    def visit_Await(self, node: ast.Await):
        raise NotImplementedError

    def visit_Yield(self, node: ast.Yield):
        raise NotImplementedError

    def visit_YieldFrom(self, node: ast.YieldFrom):
        raise NotImplementedError

    def visit_Compare(self, node: ast.Compare):
        raise NotImplementedError

    def visit_Call(self, node: ast.Call):
        raise NotImplementedError

    def visit_Num(self, node: ast.Num):
        raise NotImplementedError

    def visit_Str(self, node: ast.Str):
        raise NotImplementedError

    def visit_FormattedValue(self, node: ast.FormattedValue):
        raise NotImplementedError

    def visit_JoinedStr(self, node: ast.JoinedStr):
        raise NotImplementedError

    def visit_Bytes(self, node: ast.Bytes):
        raise NotImplementedError

    def visit_NameConstant(self, node: ast.NameConstant):
        value = Value()
        if node.value is not None:
            value.inject_type(Bool_Instance)
        else:
            value.inject_type(None_Instance)
        return value

    def visit_Ellipsis(self, node: ast.Ellipsis):
        raise NotImplementedError

    def visit_Constant(self, node: ast.Constant):
        raise NotImplementedError

    def visit_Attribute(self, node: ast.Attribute):
        raise NotImplementedError

    def visit_Subscript(self, node: ast.Subscript):
        if not isinstance(node.value, ast.Name):
            raise NotImplementedError

        value = self.visit(node.value)
        return value

    def visit_Starred(self, node: ast.Starred):
        raise NotImplementedError

    def visit_Name(self, node: ast.Name):
        value = Value()
        id = node.id
        if id == "bool":
            value.inject_type(Bool_Instance)
            return value
        elif id == "int":
            value.inject_type(Int_Instance)
            return value
        elif id == "float":
            value.inject_type(Float_Instance)
            return value
        elif id == "complex":
            value.inject_type(Complex_Instance)
        elif id == "list":
            raise NotImplementedError
        elif id == "range":
            raise NotImplementedError
        elif id == "Any":
            value.inject_type(Any)
            return value
        elif id == "str":
            value.inject_type(Str_Instance)
            return value
        elif id == "bytes":
            value.inject_type(Bytes_Instance)
            return value
        elif id == "bytearray":
            value.inject_type(ByteArray_Instance)
            return value
        elif id == "memoryview":
            raise NotImplementedError
        elif id == "set":
            raise NotImplementedError
        elif id == "frozenset":
            raise NotImplementedError
        elif id == "dict":
            raise NotImplementedError
        else:
            module: _TypeshedModule = parse_module(self.module)
            if id in module.tp_dict:
                name_info = module.get_name(id)
                return evaluate(name_info)
            else:
                raise NotImplementedError

    def visit_List(self, node: ast.List):
        raise NotImplementedError

    def visit_Tuple(self, node: ast.Tuple):
        raise NotImplementedError


builtin_module = parse_module("builtins")

_typeshed_int = builtin_module.get_name("int")
typeshed_int = evaluate(_typeshed_int)
Int_Instance.tp_class = typeshed_int
Int_Type.tp_mro = [typeshed_int, Object_Type]

_typeshed_float = builtin_module.get_name("float")
typeshed_float = evaluate(_typeshed_float)
Float_Instance.tp_class = typeshed_float
Float_Type.tp_mro = [typeshed_float, Object_Type]
