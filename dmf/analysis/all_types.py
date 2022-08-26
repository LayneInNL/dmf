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
from types import FunctionType
from typing import List, Tuple

import astor

from dmf.analysis.exceptions import MROAnyError
from dmf.analysis.namespace import Namespace
from dmf.analysis.special_types import MRO_Any, Bases_Any
from dmf.analysis.typeshed import get_stub_file
from dmf.analysis.value import Value, type_2_value


class ArtificialFunction:
    def __init__(self, tp_function, tp_addon=None):
        self.tp_uuid: str = str(id(tp_function))
        self.tp_code: FunctionType = tp_function
        self.tp_dict: Namespace = Namespace()
        if tp_addon is not None:
            self.tp_addon = tp_addon

    def __call__(self, *args, **kwargs):
        return self.tp_code(*args, **kwargs)

    def __le__(self, other: ArtificialFunction):
        return True

    def __iadd__(self, other: ArtificialFunction):
        return self

    def __repr__(self):
        if hasattr(self, "tp_addon"):
            return self.tp_addon
        return self.tp_uuid


# ArtificialClass = builtins.type
class ArtificialClass:
    def __init__(self, tp_qualname: str):
        self.tp_uuid: str = tp_qualname
        self.tp_qualname = tp_qualname
        self.tp_dict: Namespace = Namespace()

    def __repr__(self):
        return self.tp_uuid

    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]


# create a type
Type_Type = ArtificialClass("builtins.type")
Type_Type_Value = type_2_value(Type_Type)
# tp_class is a set of types
Type_Type.tp_class = type_2_value(Type_Type)

# modify __init__ to create builtins.object
def __init__(self, tp_qualname: str):
    self.tp_uuid: str = tp_qualname
    self.tp_qualname: str = tp_qualname
    self.tp_dict: Namespace = Namespace()
    self.tp_bases = []


ArtificialClass.__init__ = __init__

Object_Type = ArtificialClass("builtins.object")
Object_Type_Value = type_2_value(Object_Type)
Object_Type.tp_bases = []
Object_Type.tp_class = Type_Type_Value
Type_Type.tp_bases = [[Object_Type]]


# if MROAnyError, it means mro can not be fully constructed.
# we only know current class and the rest of mro is Any
def c3(cls_obj):
    try:
        mros = static_c3(cls_obj)
    except MROAnyError:
        # return cls_obj, MRO_Any
        return mros
    else:
        # return mros[0], mros[1:]
        return mros


def static_c3(cls_obj) -> List[List]:
    if cls_obj is Object_Type:
        return [[cls_obj]]
    elif cls_obj is Bases_Any:
        return [[MROAnyError]]
        # raise MROAnyError
    else:
        mros = []
        # cls_obj is like [[1,2,3]]
        for base_list in cls_obj.tp_bases:
            base_list: List
            merge_list: List = []
            for base in base_list:
                many_c3: List[List] = static_c3(base)
                for one_c3 in many_c3:
                    merge_list.append(one_c3)
                    one_mro: List = static_merge(merge_list)
                    mros.append([cls_obj] + one_mro)
        return mros
        # return [cls_obj] + static_merge([static_c3(base) for base in cls_obj.tp_bases])


def static_merge(mro_list) -> List:
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


# Type_Type.tp_bases = [[Bases_Any], [Object_Type]]
Type_Type.tp_mro = c3(Type_Type)
Object_Type.tp_mro = c3(Object_Type)

# redefine __init__ to create other ArtificialClasses
def __init__(self, tp_qualname: str):
    self.tp_uuid: str = tp_qualname
    self.tp_qualname: str = tp_qualname
    self.tp_dict: Namespace = Namespace()
    self.tp_class = Type_Type_Value
    self.tp_bases = [Type_Type_Value.value_2_list()]
    self.tp_mro = c3(self)


ArtificialClass.__init__ = __init__


class ListArtificialClass(ArtificialClass):
    # def __init__(self, iterable=None):
    #     if iterable is not None:
    #         self.tp_dict.write_local_value("internal", iterable)
    #

    def __call__(self, tp_address, tp_class, tp_heap):
        tp_dict = tp_heap.write_instance_to_heap(tp_address)
        return AnalysisInstance(tp_address, tp_class, tp_dict)


List_Type = ListArtificialClass("builtins.list")


def _setup_List_Type():
    def __init__(self, iterable=None):
        pass

    def append(self, x):
        value = Value()
        value.inject(x)

        if "internal" in self.tp_dict:
            prev_value = self.tp_dict.read_value("internal")
            value.inject(prev_value)
        self.tp_dict.write_local_value("internal", value)
        return type_2_value(None_Instance)

    arti_append = ArtificialFunction(tp_function=append, tp_addon="list.append")
    arti_append_value = type_2_value(arti_append)
    List_Type.tp_dict.write_local_value(append.__name__, arti_append_value)


_setup_List_Type()

Tuple_Type = ArtificialClass("builtins.tuple")
Range_Type = ArtificialClass("range")
Set_Type = ArtificialClass("set")
FrozenSet_Type = ArtificialClass("frozenset")
Dict_Type = ArtificialClass("dict")
Module_Type = ArtificialClass("module")
Function_Type = ArtificialClass("function")
Method_Type = ArtificialClass("method")
None_Type = ArtificialClass("NoneType")
Bool_Type = ArtificialClass("Bool")
Iterator_Type = ArtificialClass("others.iterator")


class AnalysisClass:
    def __init__(self, tp_uuid: str, tp_bases, tp_module, tp_dict, tp_code):
        self.tp_uuid: str = tp_uuid

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


class Module:
    pass


class AnalysisModule(Module):
    def __init__(self, tp_uuid: str, tp_package: str, tp_code):
        self.tp_uuid: str = tp_uuid
        self.tp_class = Module_Type
        self.tp_package: str = tp_package
        self.tp_dict: Namespace = Namespace()
        self.tp_dict.package = self.tp_package
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


class AnalysisFunction:
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


class Typeshed:
    def __init__(self, tp_name: str, tp_module: str, tp_qualname: str):
        self.tp_uuid = tp_qualname
        self.tp_name = tp_name
        self.tp_module = tp_module
        self.tp_qualname = tp_qualname

    def __le__(self):
        return True

    def __iadd__(self, other):
        return self


class TypeshedModule(Typeshed):
    def __init__(
        self, tp_name: str, tp_module: str, tp_qualname: str, tp_dict: Namespace
    ):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_class = Module_Type
        self.tp_dict: Namespace = tp_dict

    def __repr__(self):
        return f"typeshed module object {self.tp_name}"


class TypeshedAssign(Typeshed):
    def __init__(self, tp_name, tp_module, tp_qualname, tp_code):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_code = tp_code


class TypeshedAnnAssign(Typeshed):
    def __init__(self, tp_name, tp_module, tp_qualname, tp_code):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_code = tp_code


class TypeshedClass(Typeshed):
    def __init__(self, tp_name, tp_module, tp_qualname, tp_dict):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_dict = tp_dict
        self.tp_class = Type_Type_Value
        self.tp_bases = [[Bases_Any]]
        self.tp_mro = c3(self)


class TypeshedFunction(Typeshed):
    def __init__(self, tp_name, tp_module, tp_qualname):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.ordinaries: List[ast.FunctionDef] = []
        self.getters: List[ast.FunctionDef] = []
        self.setters: List[ast.FunctionDef] = []
        self.deleters: List[ast.FunctionDef] = []


class TypeshedPossibleImportedName(Typeshed):
    def __init__(
        self, tp_name, tp_module, tp_qualname, tp_imported_module, tp_imported_name
    ):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_imported_module = tp_imported_module
        self.tp_imported_name = tp_imported_name


class TypeshedImportedModule(Typeshed):
    def __init__(self, tp_name, tp_module, tp_qualname, tp_imported_module):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_imported_module = tp_imported_module


class TypeshedImportedName(Typeshed):
    def __init__(
        self, tp_name, tp_module, tp_qualname, tp_imported_module, tp_imported_name
    ):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_imported_module = tp_imported_module
        self.tp_imported_name = tp_imported_name


def parse_typeshed_module(module: str):
    if module in sys.analysis_typeshed_modules:
        return sys.analysis_typeshed_modules.read_value(module)

    # find stub file
    path = get_stub_file(module)
    # read file
    module_content = path.read_text()
    # parse module
    module_ast = ast.parse(module_content)
    # setup parsing env
    visitor = ModuleVisitor(module, module_ast)
    module_dict = visitor.build()
    typeshed_module = TypeshedModule(
        tp_name=module, tp_module=module, tp_qualname=module, tp_dict=module_dict
    )

    # write to sys.analysis_typeshed_modules
    value = type_2_value(typeshed_module)
    sys.analysis_typeshed_modules.write_local_value(module, value)
    return sys.analysis_typeshed_modules.read_value(module)


sys.AnalysisModule = AnalysisModule


class ModuleVisitor(ast.NodeVisitor):
    def __init__(self, module: str, module_ast: ast.Module) -> None:
        self.module_name: str = module
        self.module_ast = module_ast
        self.module_dict = Namespace()
        self.qualname = module

    def build(self):
        self.visit(self.module_ast)
        return self.module_dict

    def visit_FunctionDef(self, node: ast.FunctionDef):
        function_name = node.name

        # no function named function_name detected
        if function_name not in self.module_dict:
            typeshed_function = TypeshedFunction(
                function_name, self.module_name, f"{self.qualname}-{function_name}"
            )
            value = type_2_value(typeshed_function)
            self.module_dict.write_local_value(function_name, value)
        functions: Value = self.module_dict.read_value(function_name)

        for typeshed_function in functions:
            if not node.decorator_list:
                typeshed_function.ordinaries.append(node)
            else:
                # as far as I know, the decorators of
                # ast.FunctionDef in typeshed could be classified as three categories:
                # 1. Normal functions(without decorators)
                # 2. Descriptor functions(@property, @xxx.setter and @xxx.deleter)
                # 3. other functions( such as @abstractmethod, @classmethod)
                getter, setter, deleter = False, False, False
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "property":
                        typeshed_function.getters.append(node)
                        getter = True
                    elif (
                        isinstance(decorator, ast.Attribute)
                        and decorator.attr == "setter"
                    ):
                        typeshed_function.setters.append(node)
                        setter = True
                    elif (
                        isinstance(decorator, ast.Attribute)
                        and decorator.attr == "deleter"
                    ):
                        typeshed_function.deleters.append(node)
                        deleter = True
                if any([getter, setter, deleter]):
                    if getter + setter + deleter > 1:
                        raise NotImplementedError
                else:
                    typeshed_function.ordinaries.append(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name = node.name

        children_name_extractor = ModuleVisitor(
            self.module_name, ast.Module(body=node.body)
        )
        class_body_dict = children_name_extractor.build()

        typeshed_class = TypeshedClass(
            tp_name=class_name,
            tp_module=self.module_name,
            tp_qualname=f"{self.qualname}-{class_name}",
            tp_dict=class_body_dict,
        )
        value = type_2_value(typeshed_class)
        self.module_dict.write_local_value(class_name, value)

    def visit_Assign(self, node: ast.Assign):
        assert len(node.targets) == 1, node
        for target in node.targets:
            if not isinstance(target, ast.Name):
                raise NotImplementedError(
                    f"Assignment should only be to a simple name: {ast.dump(node)}"
                )
            typeshed_assign = TypeshedAssign(
                tp_name=target.id,
                tp_module=self.module_name,
                tp_qualname=f"{self.qualname}-{target.id}",
                tp_code=node,
            )
            value = type_2_value(typeshed_assign)
            self.module_dict.write_local_value(target.id, value)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        target = node.target
        if not isinstance(target, ast.Name):
            raise NotImplementedError(
                f"Assignment should only be to a simple name: {ast.dump(node)}"
            )
        typeshed_annassign = TypeshedAnnAssign(
            tp_name=target.id,
            tp_module=self.module_name,
            tp_qualname=f"{self.qualname}-{target.id}",
            tp_code=node,
        )
        value = type_2_value(typeshed_annassign)
        self.module_dict.write_local_value(target.id, value)

    def visit_If(self, node: ast.If):
        test_source = astor.to_source(node.test)
        value: bool = eval(test_source)
        if value:
            self.visit(ast.Module(body=node.body))
        else:
            self.visit(ast.Module(body=node.orelse))

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.asname is not None:
                typeshed_importedmodule = TypeshedImportedModule(
                    tp_name=alias.asname,
                    tp_module=self.module_name,
                    tp_qualname=f"{self.qualname}-{alias.asname}",
                    tp_imported_module=alias.name,
                )
                value = type_2_value(typeshed_importedmodule)
                self.module_dict.write_local_value(alias.asname, value)
            else:
                # "import a.b" just binds the name "a"
                name = alias.name.partition(".")[0]
                typeshed_importedmodule = TypeshedImportedModule(
                    tp_name=name,
                    tp_module=self.module_name,
                    tp_qualname=f"{self.qualname}-{alias.name}",
                    tp_imported_module=name,
                )
                value = type_2_value(typeshed_importedmodule)
                self.module_dict.write_local_value(name, value)

    def _resolve_name(self, node: ast.ImportFrom) -> str:
        if node.level == 0:
            return node.module
        name = "" if node.module is None else node.module
        package = self.module_name
        level = node.level
        bits = package.rsplit(".", level - 1)
        if len(bits) < level:
            raise ValueError("attempted relative import beyond top-level package")
        base = bits[0]
        return "{}.{}".format(base, name) if name else base

    def visit_ImportFrom(self, node: ast.ImportFrom):
        source_module = self._resolve_name(node)

        for alias in node.names:
            if alias.asname is not None:
                typeshed_possible_importedname = TypeshedPossibleImportedName(
                    tp_name=alias.asname,
                    tp_module=self.module_name,
                    tp_qualname=f"{self.qualname}-{alias.asname}",
                    tp_imported_module=source_module,
                    tp_imported_name=alias.name,
                )
                value = type_2_value(typeshed_possible_importedname)
                self.module_dict.write_local_value(alias.asname, value)
            elif alias.name == "*":
                raise NotImplementedError
            else:
                typeshed_possible_importedname = TypeshedPossibleImportedName(
                    tp_name=alias.name,
                    tp_module=self.module_name,
                    tp_qualname=f"{self.qualname}-{alias.name}",
                    tp_imported_module=source_module,
                    tp_imported_name=alias.name,
                )
                value = type_2_value(typeshed_possible_importedname)
                self.module_dict.write_local_value(alias.name, value)


def resolve_typeshed_types(attributes: Value) -> Value:
    if attributes.is_Any():
        return Value.make_any()

    value = Value()
    for attribute in attributes:
        tmp = resolve_typeshed_type(attribute)
        value.inject(tmp)

    return value


def resolve_typeshed_type(attribute):
    # maybe in curr module, maybe a submodule
    if isinstance(attribute, TypeshedPossibleImportedName):
        res = parse_typeshed_module(attribute.tp_imported_module)
        # in curr module
        if attribute.tp_imported_name in res.tp_dict:
            new_attribute: Value = res.tp_dict.read_value(attribute.tp_imported_name)
            return resolve_typeshed_types(new_attribute)
        else:
            return parse_typeshed_module(
                f"{attribute.tp_imported_module}.{attribute.tp_imported_name}"
            )
    # a module, definitely
    elif isinstance(attribute, TypeshedImportedModule):
        return parse_typeshed_module(attribute.tp_imported_module)
    # a name in the module
    elif isinstance(attribute, TypeshedImportedName):
        modules: Value = parse_typeshed_module(attribute.tp_imported_module)
        value = Value()
        for module in modules:
            new_attributes: Value = module.tp_dict.read_value(
                attribute.tp_imported_name
            )
            tmp_value = resolve_typeshed_types(new_attributes)
            value.inject(tmp_value)
        return value
    # can't be simplified
    elif isinstance(attribute, TypeshedClass):
        return attribute
    # can't be simplified
    elif isinstance(attribute, TypeshedFunction):
        return attribute
    elif isinstance(attribute, TypeshedAssign):
        raise NotImplementedError(attribute)
    elif isinstance(attribute, TypeshedAnnAssign):
        return attribute
    elif isinstance(attribute, TypeshedModule):
        return attribute
    else:
        raise NotImplementedError(attribute)


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
        self.tp_uuid = f"{tp_self.tp_uuid}-getter"
        self.tp_self = type_2_value(tp_self)
        self.tp_obj = tp_obj
        self.tp_objtype = tp_objtype


class AnalysisDescriptorSetFunction:
    def __init__(self, tp_self, tp_obj, tp_value):
        self.tp_uuid = f"{tp_self.tp_qualname}-{tp_obj.tp_qualname}"
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


class Constructor:
    def __init__(self):
        self.tp_uuid = id(self)
        self.tp_class = Function_Type

    def __call__(self, tp_address, tp_class, tp_heap):
        tp_uuid = f"{tp_address}-{tp_class.tp_qualname}"
        tp_dict = tp_heap.write_instance_to_heap(tp_uuid)
        analysis_instance = AnalysisInstance(
            tp_address=tp_uuid, tp_dict=tp_dict, tp_class=tp_class
        )

        return analysis_instance

    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]


constructor = Constructor()


def _setup_Object_Type():
    def __init__(self):
        return self

    init = ArtificialFunction(tp_function=__init__)
    value = type_2_value(init)
    Object_Type.tp_dict.write_local_value("__init__", value)

    new = constructor
    value = type_2_value(new)
    Object_Type.tp_dict.write_local_value("__new__", value)


# typeshed instance
class TypeshedInstance(Typeshed):
    def __init__(self, tp_name, tp_module, tp_qualname, tp_class):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_uuid = f"{self.tp_qualname}-instance"
        self.tp_class = tp_class


# since we use static analysis, builtin_module is a set of modules
# but in fact there will only be one module
_builtin_module: Value = parse_typeshed_module("builtins")
for builtin_module in _builtin_module:
    # get builtin_module
    pass
builtin_module_dict: Namespace = builtin_module.tp_dict
Int_Type: Value = builtin_module_dict.read_value("int")
Int_Instance = TypeshedInstance("int", "builtins", "builtins-int", Int_Type)
Typeshed_List_Type: Value = builtin_module_dict.read_value("list")
List_Type.tp_fallback = Typeshed_List_Type
builtin_module_dict.write_local_value("list", type_2_value(List_Type))
None_Instance = TypeshedInstance("None", "builtins", "builtins-None", None_Type)


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
        value = type_2_value(Int_Instance)
        raise value

    def visit_Str(self, node: ast.Str):
        raise NotImplementedError

    def visit_Bytes(self, node: ast.Bytes):
        raise NotImplementedError

    def visit_NameConstant(self, node: ast.NameConstant):
        raise NotImplementedError
        value = Value()

        if node.value is not None:
            bool_value = builtin_module_dict.read_value("bool")
            for value in bool_value:
                value.inject(ArtificialInstance())
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
            raise NotImplementedError(node)

        return self.visit(ast.Name(id="Any"))

    def visit_Starred(self, node: ast.Starred):
        raise NotImplementedError

    def visit_Name(self, node: ast.Name):
        value = Value()
        id = node.id
        if id == "bool":
            value = Value()
            value.inject(Bool_Instance)
            return value
        elif id == "int":
            value = type_2_value(Int_Instance)
            return value
        elif id == "float":
            value.inject(Float_Instance)
            return value
        elif id == "complex":
            value.inject(Complex_Instance)
        elif id == "list":
            raise NotImplementedError
        elif id == "range":
            raise NotImplementedError
        elif id == "Any":
            value.inject(Any)
            return value
        elif id == "str":
            value.inject(Str_Instance)
            return value
        elif id == "bytes":
            value.inject(Bytes_Instance)
            return value
        elif id == "bytearray":
            value.inject(ByteArray_Instance)
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
            return self.visit(ast.Name(id="Any"))
            # check if it's in module
            module: _TypeshedModule = parse_module(self.module)
            if id in module.tp_dict:
                name_info = module.get_name(id)
                res = evaluate(name_info)
                value.inject(res)
                return value
            else:
                raise NotImplementedError


def evaluate(typeshed_value):
    if isinstance(typeshed_value, TypeshedModule):
        return typeshed_value
    elif isinstance(typeshed_value, TypeshedClass):
        return typeshed_value
    elif isinstance(typeshed_value, TypeshedFunction):
        if typeshed_value.ordinaries:
            return typeshed_value
        else:
            value = Value()
            if typeshed_value.getters:
                for getter in typeshed_value.getters:
                    visitor: TypeExprVisitor = TypeExprVisitor(typeshed_value.tp_module)
                    value.inject(visitor.visit(getter))
            elif typeshed_value.setters or typeshed_value.deleters:
                value.inject(None_Instance)
            return value
    elif isinstance(typeshed_value, TypeshedAnnAssign):
        visitor = TypeExprVisitor(typeshed_value.tp_module)
        value = visitor.visit(typeshed_value.tp_code.annotation)
        return value
    elif isinstance(typeshed_value, TypeshedAssign):
        raise NotImplementedError
    else:
        raise NotImplementedError


def _py_type(obj) -> Value:
    return obj.tp_class


def _pytype_lookup(obj_type, name) -> Value:
    res = _find_name_in_mro(obj_type, name)
    return res


def _find_name_in_mro(obj_type, name) -> Value:
    all_mro_value = Value()
    tp_mros = obj_type.tp_mro
    for tp_mro in tp_mros:
        for cls in tp_mro:
            if cls is Bases_Any:
                return Value.make_any()
            else:
                # tp_dict could belong to AnalysisClass, ArtificialClass and
                # TypeshedClass
                if name not in cls.tp_dict:
                    if hasattr(cls, "tp_fallback"):
                        fallback_clses = cls.tp_fallback
                        assert len(fallback_clses) == 1
                        fallback_cls = fallback_clses.value_2_list()[0]
                        if name in fallback_cls.tp_dict:
                            curr_mro_value = fallback_cls.tp_dict.read_value(name)
                            all_mro_value.inject(curr_mro_value)
                            break

                else:
                    curr_mro_value = cls.tp_dict.read_value(name)
                    all_mro_value.inject(curr_mro_value)
                    break

    return all_mro_value


# simulate builtins.getattr, but operate on a set of objects
def getattrs(objs: Value, name: str, default=None) -> Tuple[Value, Value]:
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

    obj_types = _py_type(obj)
    for obj_type in obj_types:
        # get the __getattribute__ of this obj
        tp_getattributes = _pytype_lookup(obj_type, "__getattribute__")
        if len(tp_getattributes) == 0:
            if isinstance(obj, AnalysisInstance):
                return GenericGetAttr(obj, name)
            elif isinstance(obj, ArtificialClass):
                return type_getattro(obj, name)
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


def GenericGetAttr(obj, name):
    # two preset return values
    res_value, descr_value = Value(), Value()

    # get types of obj
    obj_types = _py_type(obj)

    # traverse types
    for obj_type in obj_types:
        # try finding descriptors
        descrs = _pytype_lookup(obj_type, name)
        if descrs.is_Any():
            return Value.make_any(), Value.make_any()

        # traverse descrs
        for descr in descrs:
            if isinstance(descr, AnalysisFunction):
                one_descr = AnalysisMethod(tp_function=descr, tp_instance=obj)
                descr_value.inject(one_descr)
            elif isinstance(descr, ArtificialFunction):
                one_descr = ArtificialMethod(tp_function=descr, tp_instance=obj)
                descr_value.inject(one_descr)
            else:
                # types of descriptor
                descr_types = _py_type(descr)
                if descr_types.is_Any():
                    return Value.make_any(), Value.make_any()

                for descr_type in descr_types:
                    descr_tp_gets = _pytype_lookup(descr_type, "__get__")
                    if descr_tp_gets.is_Any():
                        return Value.make_any(), Value.make_any()

                    for descr_tp_get in descr_tp_gets:
                        # descr_tp_get must be AnalysisFunction
                        if isinstance(descr_tp_get, AnalysisFunction):
                            # self = descr, obj = obj, type=tp
                            one_descr = AnalysisDescriptorGetFunction(
                                tp_self=descr,
                                tp_obj=type_2_value(obj),
                                tp_objtype=obj_types,
                            )
                            descr_value.inject(one_descr)
                        else:
                            raise NotImplementedError

        tp_dict = obj.tp_dict
        if name in obj.tp_dict:
            one_res = tp_dict.read_value(name)
            res_value.inject(one_res)

        res_value.inject(descrs)

        return res_value, descr_value


def type_getattro(type, name) -> Tuple[Value, Value]:
    res_value, descr_value = Value(), Value()

    descrs = _pytype_lookup(type, name)
    if descrs.is_Any():
        return Value.make_any(), Value.make_any()

    for descr in descrs:
        # the __get__ of function is id.
        if isinstance(descr, (AnalysisFunction, ArtificialFunction)):
            res_value.inject(descr)
        elif isinstance(descr, TypeshedFunction):
            typeshed_value = evaluate(descr)
            res_value.inject(typeshed_value)
        else:
            descriptor_types = _py_type(descr)
            if descriptor_types.is_Any():
                return Value.make_any(), Value.make_any()

            for descriptor_type in descriptor_types:
                descriptor_type_gets = _pytype_lookup(descriptor_type, "__get__")
                if descriptor_type_gets.is_Any():
                    return Value.make_any(), Value.make_any()

                for descriptor_type_get in descriptor_type_gets:
                    if isinstance(descriptor_type_get, AnalysisFunction):
                        one_descr = AnalysisDescriptorGetFunction(
                            tp_self=descr,
                            tp_obj=type_2_value(None_Instance),
                            tp_objtype=type_2_value(type),
                        )
                        descr_value.inject(one_descr)
                    else:
                        raise NotImplementedError

    if name in type.tp_dict:
        one_res = type.tp_dict.read_value(name)
        res_value.inject_value(one_res)

    if descrs is not None:
        res_value.inject_value(descrs)

    return res_value, descr_value
