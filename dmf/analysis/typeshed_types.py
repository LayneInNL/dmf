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
import sys
from typing import List

import astor

from dmf.analysis.namespace import Namespace
from dmf.analysis.special_types import Bases_Any, Any, MRO_Any
from dmf.analysis.typeshed import get_stub_file
from dmf.analysis.value import type_2_value, Value


class UniqueTypeshedObject(type):
    typeshed_object_dict = {}

    def __call__(cls, tp_name, tp_module, tp_qualname, *args, **kwargs):
        if tp_qualname in cls.typeshed_object_dict:
            return cls.typeshed_object_dict[tp_qualname]

        typeshed_object = super().__call__(
            tp_name, tp_module, tp_qualname, *args, **kwargs
        )
        cls.typeshed_object_dict[tp_qualname] = typeshed_object
        return typeshed_object


class Typeshed(metaclass=UniqueTypeshedObject):
    def __init__(self, tp_name: str, tp_module: str, tp_qualname: str):
        # fully qualified name
        self.tp_uuid: str = f"typeshed.{tp_qualname}"
        # name
        self.tp_name: str = tp_name
        # module
        self.tp_module: str = tp_module
        # fully qualified name
        self.tp_qualname: str = tp_qualname

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]

    def refine_self_to_value(self, *args, **kwargs) -> Value:
        value = Value()
        value.inject(self)
        return value


class TypeshedModule(Typeshed):
    def __init__(
        self, tp_name: str, tp_module: str, tp_qualname: str, tp_dict: Namespace
    ):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_dict: Namespace = tp_dict

    def custom_getattr(self, name):
        raise NotImplementedError
        # if name not in self.tp_dict:
        #     return Value.make_any()
        # else:
        #     value = Value()
        #     one_value = self.tp_dict.read_value(name)
        #     value.inject(one_value)
        #     return value

    def __repr__(self):
        return f"typeshed module object {self.tp_name}"


class TypeshedAssign(Typeshed):
    def __init__(self, tp_name, tp_module, tp_qualname, tp_code: ast.expr):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_code: ast.expr = tp_code


class TypeshedClass(Typeshed):
    def __init__(self, tp_name, tp_module, tp_qualname, tp_dict: Namespace):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_dict = tp_dict
        self.tp_class = Any
        self.tp_bases = [[Bases_Any]]
        self.tp_mro = [[self, MRO_Any]]

    def __repr__(self):
        return self.tp_qualname

    def __call__(self, *args, **kwargs):
        value = Value()
        instance_name = f"{self.tp_name}.object"
        instance_qual_name = f"{self.tp_qualname}.object"
        an_object = TypeshedInstance(
            tp_name=instance_name,
            tp_module=self.tp_module,
            tp_qualname=instance_qual_name,
            tp_class=self,
        )
        value.inject(an_object)
        return value


class TypeshedFunction(Typeshed):
    def __init__(self, tp_name, tp_module, tp_qualname):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.functions: List[ast.FunctionDef] = []

    def add_one_function(self, function: ast.FunctionDef):
        self.functions.append(function)


class TypeshedDescriptorGetter(Typeshed):
    def __init__(self, tp_name, tp_module, tp_qualname):
        super().__init__(tp_name, tp_module, tp_qualname)
        self.functions: List[ast.FunctionDef] = []

    def add_one_function(self, function: ast.FunctionDef):
        self.functions.append(function)


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


# typeshed instance
class TypeshedInstance(Typeshed):
    def __init__(self, tp_name: str, tp_module: str, tp_qualname: str, tp_class):
        tp_name = f"{tp_name}"
        tp_qualname = f"{tp_qualname}"
        super().__init__(tp_name, tp_module, tp_qualname)
        self.tp_class = tp_class
        self.tp_dict: Namespace = Namespace()

    def __repr__(self):
        return f"{self.tp_qualname}"


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

        is_property = False
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "property":
                is_property = True
                break

        # no function named function_name detected
        if function_name not in self.module_dict:
            if is_property:
                func_class = TypeshedDescriptorGetter
            else:
                func_class = TypeshedFunction
            typeshed_function = func_class(
                function_name, self.module_name, f"{self.qualname}.{function_name}"
            )
            value = type_2_value(typeshed_function)
            self.module_dict.write_local_value(function_name, value)

        functions: Value = self.module_dict.read_value(function_name)

        if node.decorator_list and not is_property:
            # other decorators, ignore
            return

        # as far as I know, the decorators of
        # ast.FunctionDef in typeshed could be classified as three categories:
        # 1. Normal functions(without decorators)
        # 2. Descriptor functions(@property, @xxx.setter and @xxx.deleter)
        # 3. other functions( such as @abstractmethod, @classmethod)
        for typeshed_function in functions:
            typeshed_function.add_one_function(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name = node.name

        children_name_extractor = ModuleVisitor(
            f"{self.module_name}.{class_name}", ast.Module(body=node.body)
        )
        class_body_dict = children_name_extractor.build()

        typeshed_class = TypeshedClass(
            tp_name=class_name,
            tp_module=self.module_name,
            tp_qualname=f"{self.qualname}.{class_name}",
            tp_dict=class_body_dict,
        )
        value = type_2_value(typeshed_class)
        self.module_dict.write_local_value(class_name, value)

    def visit_Assign(self, node: ast.Assign):
        assert len(node.targets) == 1, node
        for target in node.targets:
            typeshed_assign = TypeshedAssign(
                tp_name=target.id,
                tp_module=self.module_name,
                tp_qualname=f"{self.qualname}.{target.id}",
                tp_code=node.value,
            )
            value = type_2_value(typeshed_assign)
            self.module_dict.write_local_value(target.id, value)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        target = node.target
        typeshed_annassign = TypeshedAssign(
            tp_name=target.id,
            tp_module=self.module_name,
            tp_qualname=f"{self.qualname}.{target.id}",
            tp_code=node.annotation,
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
                    tp_qualname=f"{self.qualname}.{alias.asname}",
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
                typeshed_possible_importedname = TypeshedImportedName(
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
                typeshed_possible_importedname = TypeshedImportedName(
                    tp_name=alias.name,
                    tp_module=self.module_name,
                    tp_qualname=f"{self.qualname}-{alias.name}",
                    tp_imported_module=source_module,
                    tp_imported_name=alias.name,
                )
                value = type_2_value(typeshed_possible_importedname)
                self.module_dict.write_local_value(alias.name, value)


# further parse typeshed types to standard typeshed types.
# for instance, importedname to typeshedclass
# but insert other types as normal
def resolve_typeshed_value(attributes: Value) -> Value:
    value = Value()
    for attribute in attributes:
        # if type is Typeshed, resolve is needed
        if isinstance(attribute, Typeshed):
            tmp = resolve_typeshed_type(attribute)
            value.inject(tmp)
        # else just insert it into value
        else:
            value.inject(attribute)
    return value


def resolve_typeshed_type(attribute: Typeshed) -> Value:
    if isinstance(attribute, TypeshedImportedModule):
        return parse_typeshed_module(attribute.tp_imported_module)
    # a name in the module
    elif isinstance(attribute, TypeshedImportedName):
        modules: Value = parse_typeshed_module(attribute.tp_imported_module)
        value = Value()
        for module in modules:
            new_attributes: Value = module.tp_dict.read_value(
                attribute.tp_imported_name
            )
            tmp_value = resolve_typeshed_value(new_attributes)
            value.inject(tmp_value)
        return value
    # can't be simplified
    elif isinstance(
        attribute,
        (
            TypeshedClass,
            TypeshedFunction,
            TypeshedDescriptorGetter,
            TypeshedAssign,
            TypeshedModule,
        ),
    ):
        value = Value()
        value.inject(attribute)
        return value
    else:
        raise NotImplementedError(attribute)


def extract_1value(classes: Value):
    assert len(classes) == 1
    return classes.value_2_list()[0]


def import_a_module_from_typeshed(module_name: str) -> Value:
    module: Value = parse_typeshed_module(module_name)
    return module
