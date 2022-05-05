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
    func = value.extract_func_label()
    cls = value.extract_class_object()
    if func is not None and cls is not None:
        assert False

    if func is not None:
        return True
    return False


def is_class(value: Value):
    func = value.extract_func_label()
    cls = value.extract_class_object()
    if func is not None and cls is not None:
        assert False

    if cls is None:
        return False
    return True


def record(label, context):
    return label


def merge(label, heap, context):
    return context[-1:] + (label,)


def compute_value_of_expr(expr: ast.expr, state: State) -> Value:
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
    elif isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Name):
            return compute_value_of_expr(expr.func, state)
        elif isinstance(expr.func, ast.Attribute):
            instance_value = compute_value_of_expr(expr.func.value, state)
            heaps = instance_value.extract_heap_type()
            value = Value()
            for hcontext, cls in heaps:
                attribute_value = state.read_field_from_heap(
                    hcontext, cls, expr.func.attr
                )
                value += attribute_value()
            return value
    else:
        assert False
