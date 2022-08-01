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

from dmf.analysis.namespace import Namespace


# class Function:
#     pass


# class LabelBasedFunction(Function):
#     def __init__(self, uuid, code, module, name=None, argdefs=None, closure=None):
#         self.nl__uuid__ = uuid
#         self.nl__dict__ = Namespace()
#         # self.nl__dict__.write_special_value("nl__doc__", None)
#         # self.nl__dict__.write_special_value("nl__qualname__", None)
#         self.nl__dict__.write_special_value("nl__module__", module)
#         # self.nl__dict__.write_special_value("nl__defaults__", None)
#         self.nl__dict__.write_special_value("nl__code__", code)
#         # self.nl__dict__.write_special_value("nl__globals__", None)
#         self.nl__dict__.write_special_value("nl__name__", name)
#         # self.nl__dict__.write_special_value("nl__closure__", None)
#         # self.nl__dict__.write_special_value("nl__annotations__", None)
#         # self.nl__dict__.write_special_value("nl__kwdefaults__", None)
#
#     def __le__(self, other):
#         return self.nl__dict__ <= other.nl__dict__
#
#     def __iadd__(self, other):
#         self.nl__dict__ += other.nl__dict__
#         return self
#
#
# class ArtificialFunction(Function):
#     def __init__(self, function):
#         self.nl__uuid__ = id(function)
#         self.nl__code__ = function
#
#     def __le__(self, other):
#         return True
#
#     def __iadd__(self, other):
#         return self
#
#     def __call__(self, *args, **kwargs):
#         return self.nl__code__(*args, **kwargs)
from dmf.typeshed_client import NameInfo, OverloadedName


class TypeshedVariable:
    def __init__(self, qualified_name, nameinfo):
        self.nl__uuid__ = qualified_name
        self.nl__nameinfo__ = nameinfo

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeshedFunction:
    def __init__(self, qualified_name, nameinfo):
        self.nl__uuid__ = qualified_name
        self.nl__nameinfo__ = nameinfo

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeshedOverloadedFunction:
    def __init__(self, qualified_name, nameinfo):
        self.nl__uuid__ = qualified_name
        self.nl__nameinfo__ = nameinfo

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeshedClass:
    def __init__(self, qualified_name, nameinfo):
        self.nl__uuid__ = qualified_name
        self.name = nameinfo.name
        self.ast = nameinfo.ast
        self.nl__dict__ = nameinfo.child_nodes

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeshedModule:
    def __init__(self, qualified_name, namedict):
        self.nl__uuid__ = qualified_name
        self.nl__dict__ = namedict

    def __getattr__(self, name):
        print(type(self.nl__dict__))
        if name in self.nl__dict__:
            attr = self.nl__dict__[name]
            qualified_name = self.nl__uuid__ + (name,)
            if isinstance(attr, dict):
                return TypeshedModule(qualified_name, attr)
            elif isinstance(attr, NameInfo):
                if isinstance(attr.ast, ast.ClassDef):
                    return TypeshedClass(qualified_name, attr)
                elif isinstance(attr.ast, ast.FunctionDef):
                    return TypeshedFunction(qualified_name, attr)
                elif isinstance(attr.ast, OverloadedName):
                    return TypeshedOverloadedFunction(qualified_name, attr)
                elif isinstance(attr.ast, ast.AnnAssign):
                    return TypeshedVariable(qualified_name, attr)
                else:
                    raise NotImplementedError(attr)

        raise AttributeError

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.nl__uuid__.__repr__()

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self
