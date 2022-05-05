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
import ast
import logging
from typing import List, Set, Tuple

from dmf.analysis.lattice import Lattice
from dmf.analysis.state import State
from dmf.analysis.value import (
    Value,
    ClassObject,
)


def is_func(value: Value):
    func_type = value.extract_func_type()
    if func_type:
        return True
    return False


def is_class(value: Value):
    class_object = value.extract_class_object()
    if class_object is None:
        return False
    return True


def get_func_label(name: str, lattice: Lattice):
    values: List[State] = list(lattice.values())
    state: State = values[0]
    value: Value = state.read_var_from_stack(name)
    logging.debug("Value is {}".format(value))
    func_labels = list(value.extract_func_type())
    if not func_labels:
        class_object: ClassObject = value.extract_class_object()
        func_value: Value = class_object.attributes["__init__"]
        func_labels = list(func_value.extract_func_type())
    return func_labels[0]


def get_func_name(expr: ast.expr):
    assert isinstance(expr, ast.Call)
    if isinstance(expr.func, ast.Name):
        return expr.func.id
    else:
        assert False


def record(label, context):
    return label


def merge(label, heap, context):
    return context[-1:] + (label,)


def compute_value_of_expr(expr: ast.expr, state: State):
    if isinstance(expr, ast.Num):
        value = Value()
        value.inject_num()
        return value
    elif isinstance(expr, ast.NameConstant):
        value = Value()
        if expr.value is None:
            value.inject_none()
        else:
            value.inject_bool()
        return value
    elif isinstance(expr, (ast.Str, ast.JoinedStr)):
        value = Value()
        value.inject_str()
        return value
    elif isinstance(expr, ast.Bytes):
        value = Value()
        value.inject_byte()
        return value
    elif isinstance(expr, ast.Name):
        return state.read_var_from_stack(expr.id)
    elif isinstance(expr, ast.Attribute):
        attr = expr.attr
        assert isinstance(expr.value, ast.Name)
        name = expr.value.id
        value = state.read_var_from_stack(name)
        heaps: Set[Tuple[int, ClassObject]] = value.extract_heap_type()
        ret_value = Value()
        for (lab, cls) in heaps:
            tmp_value = state.read_field_from_heap(lab, cls, attr)
            ret_value += tmp_value
        return ret_value
    else:
        assert False
