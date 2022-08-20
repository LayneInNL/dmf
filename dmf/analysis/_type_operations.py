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
    c3,
    Function,
)
from .exceptions import MROAnyError, AnalysisAttributeError
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


# Every entity in Python is an object.
class ObjectLevel:
    def __init__(self, tp_class):
        self.tp_class = tp_class


# object has class type
class ClassLevel:
    pass


# object has instance type
class Instance:
    pass


class AnalysisModule(ObjectLevel):
    def __init__(self, tp_uuid, tp_package, tp_code):
        super().__init__(tp_class=Module_Type)
        self.tp_uuid: str = tp_uuid
        self.tp_package: str = tp_package
        self.tp_dict: Namespace = Namespace()
        self.tp_dict.write_special_value("__package__", self.tp_package)
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


class TypeshedModule(ObjectLevel):
    def __init__(self, _typeshed_module: _TypeshedModule):
        super().__init__(tp_class=Module_Type)
        self.tp_uuid = _typeshed_module.tp_uuid
        self.tp_dict = _typeshed_module.tp_dict
        self.tp_module = _typeshed_module.module_name

    def getattr(self, attr_name: str):
        if attr_name not in self.tp_dict:
            # possible it's a module
            sub_module = f"{self.tp_module}.{attr_name}"
            return parse_module(sub_module)
        name_info = self.tp_dict[attr_name]
        return resolve_attribute(name_info)

    def __len__(self):
        return True

    def __iadd__(self, other):
        return self


class AnalysisFunction(ObjectLevel):
    def __init__(
        self,
        tp_uuid: int,
        tp_code: Tuple[int, int],
        tp_module: str,
        tp_defaults,
        tp_kwdefaults,
    ):
        super().__init__(Function_Type)
        self.tp_uuid: int = tp_uuid
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


class ArtificialFunction(ObjectLevel):
    def __init__(self, tp_function):
        super().__init__(Function_Type)
        self.tp_uuid = id(tp_function)
        self.tp_code = tp_function
        self.tp_dict = Namespace()
        self.tp_repr = None

    def __call__(self, *args, **kwargs):
        return self.tp_code(*args, **kwargs)

    def __le__(self, other: ArtificialFunction):
        return True

    def __iadd__(self, other: ArtificialFunction):
        return self

    def __repr__(self):
        if self.tp_repr is not None:
            return self.tp_repr
        return str(self.tp_uuid)


class TypeshedFunction:
    def __init__(self, tp_uuid, tp_oridinaries):
        self.tp_uuid = tp_uuid
        self.tp_ordinaries = tp_oridinaries


class AnalysisMethod:
    def __init__(self, tp_function, tp_instance):
        self.tp_uuid = f"{tp_function.tp_uuid}-{tp_instance.tp_uuid}"
        self.tp_function = tp_function
        self.tp_instance = tp_instance
        self.tp_module = tp_function.tp_module

    def __le__(self):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.tp_uuid


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


class AnalysisClass(ClassLevel):
    def __init__(self, tp_uuid, tp_bases, tp_module, tp_dict, tp_code):
        self.tp_uuid = tp_uuid
        self.tp_class = Type_Type
        self.tp_bases = tp_bases
        try:
            self.tp_mro_curr, self.tp_mro_rest = c3(self)
        except MROAnyError:
            self.tp_mro_curr, self.tp_mro_rest = self, Any
        self.tp_module = tp_module
        self.tp_dict = tp_dict
        self.tp_code = tp_code

    def __le__(self, other: AnalysisClass):
        return self.tp_dict <= other.tp_dict

    def __iadd__(self, other: AnalysisModule):
        self.tp_dict += other.tp_dict
        return self


class TypeshedClass:
    def __init__(self, tp_uuid, tp_dict, tp_module):
        self.tp_uuid = tp_uuid
        self.tp_dict = tp_dict
        self.tp_module = tp_module
        self.tp_mro_curr, self.tp_mro_rest = self, [Object_Type]

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class AnalysisInstance(Instance):
    def __init__(self, tp_uuid, tp_dict, tp_class):
        self.tp_uuid = tp_uuid
        self.tp_dict = tp_dict
        self.tp_class = tp_class

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class ArtificialInstance:
    def __init__(self, tp_uuid, tp_class):
        self.tp_uuid = tp_uuid
        self.tp_class = tp_class
        self.tp_repr = None

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        if self.tp_repr is not None:
            return self.tp_repr
        return self


class Constructor:
    def __init__(self):
        self.tp_uuid = id(self)

    def __call__(self, tp_uuid, tp_dict):
        return AnalysisInstance(tp_uuid, tp_dict)

    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]


constructor = Constructor()


class ArtificialInstanceConstructor:
    def __init__(self):
        pass

    def __call__(self, *args, **kwargs):
        raise NotImplementedError


def _py_type(obj):
    return obj.tp_class


def _pytype_lookup(type, name):
    res = _find_name_in_mro(type, name)
    if res is None:
        return Value()
    else:
        return res


def _pytype_lookup_set(type, name, value):
    res = _find_name_in_mro(type, name)

    # no class variable called name
    if res is None:
        type.tp_dict.write_local_value(name, value)
        return type.tp_dict.read_value(name)
    # class variable exists, return this one
    else:
        res.inject_value(value)
        return res


def _find_name_in_mro(type, name) -> Value:
    res = None
    tp_mro_curr, tp_mro_rest = type.tp_mro_curr, type.tp_mro_rest
    # name in tp_mro_curr
    if name in tp_mro_curr.tp_dict:
        return tp_mro_curr.tp_dict.read_value(name)

    # the rest of mro is Any, the best result is Any
    if tp_mro_rest is Any:
        return Value.make_any()
    # try find class variable
    for base in tp_mro_rest:
        dict = base.tp_dict
        if name in dict:
            return dict.read_value(name)

    return res


def GenericGetAttr(obj, name):
    res_value, descr_value = Value(), Value()

    tp = _py_type(obj)
    descrs = _pytype_lookup(tp, name)
    if descrs.is_Any():
        return Value.make_any(), Value.make_any()
    for descr in descrs:
        descr_tp = _py_type(descr)

        # if descr_tp is function type
        if isinstance(descr_tp, Function):
            if isinstance(descr, AnalysisFunction):
                one_descr = AnalysisMethod(tp_function=descr, tp_instance=obj)
                descr_value.inject_type(one_descr)
            elif isinstance(descr, ArtificialFunction):
                one_descr = ArtificialMethod(tp_function=descr, tp_instance=obj)
                descr_value.inject_type(one_descr)
            else:
                raise NotImplementedError
        else:
            descr_tp_gets = _pytype_lookup(descr_tp, "__get__")
            if descr_tp_gets.is_Any():
                return Value.make_any(), Value.make_any()
            for descr_tp_get in descr_tp_gets:
                if isinstance(descr_tp_get, AnalysisFunction):
                    # self = descr, obj = obj, type=tp
                    one_descr = AnalysisDescriptorGetFunction(
                        tp_self=descr, tp_obj=obj, tp_objtype=tp
                    )
                    descr_value.inject_type(one_descr)
                elif isinstance(descr_tp_get, ArtificialFunction):
                    one_res = descr_tp_get(descr, obj, tp)
                    res_value.inject_type(one_res)
                elif isinstance(descr_tp_get, TypeshedFunction):
                    raise NotImplementedError
                else:
                    raise NotImplementedError

    tp_dict = obj.tp_dict
    if name in obj.tp_dict:
        one_res = tp_dict.read_value(name)
        res_value.inject_value(one_res)

    res_value.inject_value(descrs)

    return res_value, descr_value


def GenericSetAttr(obj, name, value):
    descr_value = Value()

    tp = _py_type(obj)
    # look up class dict
    descrs = _pytype_lookup_set(tp, name, value)
    if descrs.is_Any():
        return Value.make_any()
    for descr in descrs:
        descr_tp = _py_type(descr)
        descr_tp_sets = _pytype_lookup(descr_tp, "__set__")
        if descr_tp_sets.is_Any():
            return Value.make_any()
        for descr_tp_set in descr_tp_sets:
            if isinstance(descr_tp_set, AnalysisFunction):
                one_descr = AnalysisDescriptorSetFunction(
                    tp_self=descr_tp, tp_obj=obj, tp_value=value
                )
                descr_value.inject_type(one_descr)
            elif isinstance(descr_tp_set, ArtificialFunction):
                # return type is None
                descr_tp_set(descr, obj, tp)
            else:
                raise NotImplementedError

    # instance dict assignment
    obj.tp_dict.write_local_value(name, value)

    return descr_value


def type_getattro(type, name) -> Tuple[Value, Value]:
    res_value, descr_value = Value(), Value()

    descrs = _pytype_lookup(type, name)
    if descrs.is_Any():
        return Value.make_any(), Value.make_any()
    for descr in descrs:
        descr_tp = _py_type(descr)
        descr_tp_gets = _pytype_lookup(descr_tp, "__get__")
        if descr_tp_gets.is_Any():
            return Value.make_any(), Value.make_any()
        for descr_tp_get in descr_tp_gets:
            if isinstance(descr_tp_get, AnalysisFunction):
                one_descr = AnalysisDescriptorGetFunction(
                    tp_self=descr, tp_obj=None_Type, tp_objtype=type
                )
                descr_value.inject_type(one_descr)
            elif isinstance(descr_tp_get, ArtificialFunction):
                one_res = descr_tp_get(descr, None_Type, type)
                res_value.inject_type(one_res)
            elif isinstance(descr_tp_get, TypeshedFunction):
                raise NotImplementedError
            else:
                raise NotImplementedError

    if name in type.tp_dict:
        one_res = type.tp_dict.read_value(name)
        res_value.inject_value(one_res)

    if descrs is not None:
        res_value.inject_value(descrs)

    return res_value, descr_value


def type_setattro(type, name, value):
    return GenericSetAttr(type, name, value)


def _setup_Object_Type():
    # _object_getattro = ArtificialFunction(tp_function=GenericGetAttr)
    # _value = Value()
    # _value.inject_type(_object_getattro)
    # Object_Type.tp_dict.write_local_value("__getattribute__", _value)
    #
    # _value = Value()
    # _object_setattro = ArtificialFunction(tp_function=GenericSetAttr)
    # _value.inject_type(_object_setattro)
    # Object_Type.tp_dict.write_local_value("__setattr__", _value)

    _value = Value()

    def __init__(self):
        return self

    _object_init = ArtificialFunction(tp_function=__init__)
    _value.inject_type(_object_init)
    Object_Type.tp_dict.write_local_value("__init__", _value)


def _setup_Type_Type():
    pass
    # _value = Value()
    # _type_getattro = ArtificialFunction(tp_function=type_getattro)
    # _value.inject_type(_type_getattro)
    # Type_Type.tp_dict.write_local_value("__getattribute__", _value)
    #
    # _value = Value()
    # _type_setattro = ArtificialFunction(tp_function=type_setattro)
    # _value.inject_type(_type_setattro)
    # Type_Type.tp_dict.write_local_value("__setattr__", _value)


def _setup_Function_Type():
    pass
    # self is a function object
    # obj is class object or None
    # def __set__(self, obj, objtype):
    #     if obj is None_Instance:
    #         return self
    #     if isinstance(self, AnalysisFunction):
    #         return AnalysisMethod(tp_function=self, tp_instance=obj)
    #     elif isinstance(self, ArtificialFunction):
    #         return ArtificialMethod(tp_function=self, tp_instance=obj)
    #     else:
    #         raise NotImplementedError
    #
    # _value = Value()
    # _value.inject_type(ArtificialFunction(tp_function=__set__))
    # Function_Type.tp_dict.write_local_value("__set__", _value)


_setup_Object_Type()
_setup_Type_Type()
_setup_Function_Type()

Int_Instance = ArtificialInstance(-1, Int_Type)
Int_Instance.tp_repr = "int object"
Float_Instance = ArtificialInstance(-2, Float_Type)
Float_Instance.tp_repr = "float object"
Complex_Instance = ArtificialInstance(-3, Complex_Type)
Str_Instance = ArtificialInstance(-4, Str_Type)
Bytes_Instance = ArtificialInstance(-5, Bytes_Type)
ByteArray_Instance = ArtificialInstance(-6, ByteArray_Type)
None_Instance = ArtificialInstance(-7, None_Type)
Bool_Instance = ArtificialInstance(-8, Bool_Type)
Bool_Instance.tp_repr = "bool object"

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
        return TypeshedClass(name_info.qualified_name, name_info.tp_dict, "builtins")
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
Int_Type.tp_mro_curr, Int_Type.tp_mro_rest = typeshed_int, [Object_Type]

_typeshed_float = builtin_module.get_name("float")
typeshed_float = evaluate(_typeshed_float)
Float_Instance.tp_class = typeshed_float
Float_Type.tp_mro_curr, Float_Type.tp_mro_rest = typeshed_float, [Object_Type]

# simulate builtins.getattr, but operate on a set of objects
def getattrs(objs: Value, name, default=None) -> Tuple[Value, Value]:
    if objs.is_Any():
        return Value(any=True), Value(any=True)

    res = Value()
    descrs = Value()
    for obj in objs:
        curr_res, curr_descrs = _getattr(obj, name)
        res += curr_res
        descrs += curr_descrs

    if default is not None:
        res.inject_type(default)

    return res, descrs


def _getattr(obj, name) -> Tuple[Value, Value]:

    if obj is Any:
        return Value(any=True), Value(any=True)

    tp = _py_type(obj)
    # get the __getattribute__ of this obj
    tp_getattributes = _pytype_lookup(tp, "__getattribute__")
    if len(tp_getattributes) == 0:
        # work on class
        if isinstance(obj, ClassLevel):
            return type_getattro(obj, name)
        elif isinstance(obj, Instance):
            return GenericGetAttr(obj, name)
        elif isinstance(obj, AnalysisFunction):
            return GenericGetAttr(obj, name)
        elif isinstance(obj, AnalysisModule):
            try:
                res = obj.getattr(name)
            except AttributeError:
                return Value(), Value()
            else:
                direct_res = Value()
                direct_res.inject_value(res)
                return direct_res, Value()
        else:
            raise NotImplementedError
    else:
        return Value.make_any(), Value.make_any()


def setattrs(objs, name, value) -> Value:
    if objs.is_Any():
        return Value.make_any()

    descrs = Value()
    for obj in objs:
        curr_descrs = _setattr(obj, name)
        descrs += curr_descrs

    return descrs


def _setattr(obj, name, value) -> Value:
    if obj is Any:
        return Value(any=True)

    tp = _py_type(obj)
    tp_setattr = _pytype_lookup(tp, "__setattr__")
    if len(tp_setattr) == 0:
        # work on class
        if isinstance(obj, ClassLevel):
            return type_setattro(obj, name, value)
        elif isinstance(obj, Instance):
            return GenericSetAttr(obj, name, value)
        elif isinstance(obj, AnalysisFunction):
            return GenericSetAttr(obj, name, value)
        else:
            raise NotImplementedError(f"setattr({obj},{name},{value})")
    else:
        return Value(any=True)
