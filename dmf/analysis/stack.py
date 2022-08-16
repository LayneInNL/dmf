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
from typing import List

import dmf.share
from dmf.analysis.types import (
    Value,
    Namespace,
    Var,
    CustomClass,
    Getattr,
    Instance,
    LocalVar,
    builtin_namespace,
)
from dmf.analysis.variables import (
    Namespace_Global,
    Namespace_Nonlocal,
    Namespace_Local,
    Namespace_Helper,
)
from dmf.log.logger import logger


class Frame:
    def __init__(self, *, f_locals, f_back=None, f_globals):
        self.f_locals: Namespace[Var, Value] = f_locals
        self.f_back: Frame | None = f_back
        self.f_globals: Namespace[Var, Value] = f_globals
        self.f_builtins: Namespace[Var, Value] = builtin_namespace

    # compare f_locals, f_globals and f_builtins
    # don't know how to compare f_back for now
    def __le__(self, other: Frame):
        res = self.f_locals <= other.f_locals and self.f_globals <= other.f_globals
        return res

    def __iadd__(self, other: Frame):
        self.f_locals += other.f_locals
        self.f_globals += other.f_globals
        return self

    def __repr__(self):
        return self.f_locals.__repr__()

    def read_var(self, name: str) -> Value:
        # Implement LEGB rule
        try:
            return self._read_local_namespace(name)
        except AttributeError:
            pass

        try:
            return self._read_nonlocal_namespace(name)
        except AttributeError:
            pass

        try:
            return self._read_global_namespace(name)
        except AttributeError:
            pass

        try:
            return self._read_builtin_namespace(name)
        except AttributeError:
            pass

        raise AttributeError(name)

    def _read_local_namespace(self, name: str) -> Value:
        if name in self.f_locals:
            var = self.f_locals.read_var_type(name)
            if isinstance(var, LocalVar):
                return self.f_locals.read_value(name)
            else:
                val = self.f_locals.read_value(name)
                assert isinstance(val, Namespace)
                return val.read_value(name)
        raise AttributeError

    # find one with (var_name, local)
    def _read_nonlocal_namespace(self, name: str) -> Value:
        parent_frame: Frame = self.f_back
        while (
            # not the last frame
            parent_frame is not None
            # share the same global namespace
            and parent_frame.f_globals is self.f_globals
            # parent_frame.f_locals itself should not be module namespace
            and parent_frame.f_locals is not self.f_globals
        ):
            if name in parent_frame.f_locals:
                var = parent_frame.f_locals.read_var_type(name)
                if isinstance(var, LocalVar):
                    return parent_frame.f_locals.read_value(name)
                else:
                    parent_frame = parent_frame.f_back
            else:
                parent_frame = parent_frame.f_back
        raise AttributeError(name)

    def _read_global_namespace(self, name: str) -> Value:
        if name in self.f_globals:
            var = self.f_globals.read_var_type(name)
            if isinstance(var, LocalVar):
                return self.f_globals.read_value(name)
            else:
                raise AttributeError(name)
        raise AttributeError(name)

    def _read_builtin_namespace(self, name: str) -> Value:
        if name in self.f_builtins:
            var = self.f_builtins.read_var_type(name)
            if isinstance(var, LocalVar):
                return self.f_builtins.read_value(name)
            else:
                raise AttributeError(name)
        raise AttributeError(name)

    def write_var(self, name: str, scope: str, value: Value):
        if name in self.f_locals:
            var = self.f_locals.read_var_type(name)
            if isinstance(var, LocalVar):
                self.f_locals.write_local_value(name, value)
                # if self.f_locals is self.f_globals:
                #     self.f_locals[var].inject_value(value)
                # else:
                #     self.f_locals[var] = value
            else:
                val = self.f_locals.read_value(name)
                assert isinstance(val, Namespace)
                val.write_local_value(name, value)
        else:
            if scope == Namespace_Local:
                self.f_locals.write_local_value(name, value)
            elif scope == Namespace_Nonlocal:
                namespace = self._find_nonlocal_namespace(name)
                self.f_locals.write_nonlocal_value(name, namespace)
            elif scope == Namespace_Global:
                namespace = self._find_global_namespace(name)
                self.f_locals.write_global_value(name, namespace)
            elif scope == Namespace_Helper:
                self.f_locals.write_special_value(name, value)

    def _find_nonlocal_namespace(self, name: str) -> Namespace:
        parent_frame: Frame = self.f_back
        while parent_frame is not None and parent_frame.f_globals is self.f_globals:
            if name in parent_frame.f_locals:
                (
                    var,
                    _,
                ) = parent_frame.f_locals.read_var_type(name)
                if isinstance(var, LocalVar):
                    return parent_frame.f_locals
                else:
                    parent_frame = parent_frame.f_back
            else:
                parent_frame = parent_frame.f_back
        raise AttributeError

    def _find_global_namespace(self, name: str) -> Namespace:
        if name not in self.f_globals:
            self.f_globals.write_local_value(name, Value(any=True))

        return self.f_globals

    def delete_var(self, name: str):
        if name in self.f_locals:
            var: Var = self.f_locals.read_var_type(name)
            if not isinstance(var, LocalVar):
                owner_namespace = self.f_locals.read_value(name)
                assert isinstance(owner_namespace, Namespace)
                owner = owner_namespace.read_var_type(name)
                assert isinstance(owner, LocalVar)
                del owner_namespace[owner]
            del self.f_locals[var]


class Stack:
    def __init__(self):
        self.frames: List[Frame] = []

    def __le__(self, other: Stack):
        frame_pairs = zip(reversed(self.frames), reversed(other.frames))
        for frame_pair in frame_pairs:
            if not frame_pair[0] <= frame_pair[1]:
                return False
        return True

    def __iadd__(self, other: Stack):
        frame_pairs = zip(reversed(self.frames), reversed(other.frames))
        for frame_pair1, frame_pair2 in frame_pairs:
            frame_pair1 += frame_pair2
        return self

    def __repr__(self):
        return self.frames.__repr__()

    def push_frame(self, frame: Frame):
        self.frames.append(frame)

    def pop_frame(self) -> Frame:
        top = self.top_frame()
        self.frames = self.frames[:-1]
        return top

    def top_frame(self) -> Frame:
        return self.frames[-1]

    def top_namespace_contains(self, name):
        return name in self.top_frame().f_locals

    def read_module(self):
        return self.top_frame().f_globals.read_value("__name__")

    def read_package(self):
        return self.top_frame().f_globals.read_value("__package__")

    def read_var(self, var: str):
        return self.top_frame().read_var(var)

    def write_var(self, var: str, scope: str, value):
        self.top_frame().write_var(var, scope, value)

    def write_helper_var(self, var: str, value):
        self.write_var(var, Namespace_Helper, value)

    def delete_var(self, var: str):
        self.top_frame().delete_var(var)

    def next_ns(self):
        curr_frame = self.top_frame()

        new_f_locals = Namespace()
        new_f_back = curr_frame
        new_f_globals = curr_frame.f_globals

        new_frame = Frame(
            f_locals=new_f_locals,
            f_back=new_f_back,
            f_globals=new_f_globals,
        )
        self.push_frame(new_frame)

    def check_module_diff(self, new_module_name=None):
        curr_module_name = self.read_module()
        if curr_module_name != new_module_name:
            self.top_frame().f_globals = dmf.share.analysis_modules[
                new_module_name
            ].namespace

    def compute_value_of_expr(self, expr: ast.expr, address=None):
        value = Value()
        if isinstance(expr, ast.Num):
            if isinstance(expr.n, int):
                value.inject_type(TypeInt())
            elif isinstance(expr.n, float):
                value.inject_type(TypeFloat())
            elif isinstance(expr.n, complex):
                value.inject_type(TypeComplex())
        elif isinstance(expr, ast.NameConstant):
            if expr.value is None:
                value.inject_type(TypeNone())
            else:
                value.inject_type(TypeBool())
        elif isinstance(expr, (ast.Str, ast.JoinedStr)):
            value.inject_type(TypeStr())
        elif isinstance(expr, ast.Bytes):
            value.inject_type(TypeBytes())
        elif isinstance(expr, ast.Compare):
            value.inject_type(TypeBool())
        elif isinstance(expr, ast.Name):
            return self.read_var(expr.id)
        elif isinstance(expr, ast.Attribute):
            receiver_value: Value = self.compute_value_of_expr(expr.value)
            receiver_attr: str = expr.attr
            value: Value = Value()
            for typ in receiver_value:
                if isinstance(typ, CustomClass):
                    try:
                        tmp = Getattr(typ, receiver_attr)
                    except AttributeError:
                        pass
                    else:
                        value.inject_value(tmp)
                elif isinstance(typ, Instance):
                    try:
                        tmp = Getattr(typ, receiver_attr)
                    except AttributeError:
                        pass
                    else:
                        value.inject_value(tmp)
                elif isinstance(typ, FunctionObject):
                    try:
                        tmp = Getattr(typ, receiver_attr)
                    except AttributeError:
                        pass
                    else:
                        value.inject_value(tmp)
            return value
        elif isinstance(expr, ast.BinOp):
            dunder_method = op2dunder(expr.op)
            lhs_value: Value = self.compute_value_of_expr(expr.left)
            rhs_value: Value = self.compute_value_of_expr(expr.right)
            for lab1, typ1 in lhs_value:
                for lab2, typ2 in rhs_value:
                    try:
                        res_type = typ1.binop(dunder_method, typ2)
                    except (AttributeError, TypeError):
                        pass
                    else:
                        value.inject_type(res_type)
            return value
        else:
            logger.warn(expr)
            assert False, expr
        return value


analysis_stack = Stack()
