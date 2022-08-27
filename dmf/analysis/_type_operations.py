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

from typing import Tuple

from dmf.typeshed_client.parser import (
    parse_module,
)
from .special_types import Any
from .value import Value
from ..importer import import_module


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


def _setup_List_Type():
    def append(self, x):
        self.tp_dict.write_local_value("internal", x)
        return None_Instance

    artificial_function = ArtificialFunction(tp_function=append)
    value = Value()
    value.inject(artificial_function)
    List_Type.tp_dict.write_local_value("append", value)


_setup_List_Type()

builtin_module = parse_module("builtins")

# simulate builtins.getattr, but operate on a set of objects
def getattrs(objs: Value, name, default=None) -> Tuple[Value, Value]:
    # if objs is Any, just return two Anys
    if objs.is_Any():
        return Value(any=True), Value(any=True)

    # direct results
    direct_res = Value()
    # possible descriptor getters
    descr_gets = Value()

    for obj in objs:
        curr_direct_res, curr_descr_gets = _getattr(obj, name)
        direct_res += curr_direct_res
        descr_gets += curr_descr_gets

    # add default to direct_res
    if default is not None:
        direct_res.inject(default)

    return direct_res, descr_gets


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
        elif isinstance(obj, ArtificialInstance):
            return GenericGetAttr(obj, name)
        elif isinstance(obj, AnalysisModule):
            try:
                res = obj.getattr(name)
            except AttributeError:
                return Value(), Value()
            else:
                return res, Value()
        elif isinstance(obj, TypeshedModule):
            try:
                res = obj.getattr(name)
            except AttributeError:
                return Value(), Value()
            else:
                direct_res, descr_gets = Value(), Value()
                direct_res.inject(res)
                return direct_res, descr_gets
        else:
            raise NotImplementedError
    else:
        return Value.make_any(), Value.make_any()


def setattrs(objs, name, value) -> Value:
    # if objs is Any, return Any
    if objs.is_Any():
        return Value.make_any()

    descr_sets = Value()
    for obj in objs:
        curr_descr_sets = _setattr(obj, name, value)
        descr_sets += curr_descr_sets

    return descr_sets


def _setattr(obj, name, value) -> Value:
    if obj is Any:
        return Value.make_any()

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


def _resolve_name(name, package, level):
    """Resolve a relative module name to an absolute one."""
    bits = package.rsplit(".", level - 1)
    if len(bits) < level:
        raise ValueError("attempted relative import beyond top-level package")
    base = bits[0]
    return "{}.{}".format(base, name) if name else base


def import_a_module_from_typeshed(name):
    module = parse_module(name)
    typeshed_module = TypeshedModule(module)
    return typeshed_module


def import_a_module(name, package=None, level=0) -> Value:
    import isort

    # package is needed
    if level > 0:
        name = _resolve_name(name, package, level)
    category = isort.place_module(name)

    value = Value()
    if category == "STDLIB":
        module = import_a_module_from_typeshed(name)
    else:
        module = import_module(name)

    value.inject(module)
    return value
