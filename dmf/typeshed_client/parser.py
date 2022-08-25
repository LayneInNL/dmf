"""This module is responsible for parsing a stub AST into a dictionary of names."""
from __future__ import annotations

import ast
import logging
import sys
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from . import finder
from .LiteralEvalVisitor import LiteralEvalVisitor
from .finder import get_search_context, SearchContext

log = logging.getLogger(__name__)


class InvalidStub(Exception):
    pass


class BasicNameInfo:
    def __init__(
        self, name: str, is_exported: bool, module_name: str, qualified_name: str
    ):
        self.name: str = name
        self.is_exported: bool = is_exported
        self.module_name: str = module_name
        self.qualified_name: str = qualified_name


class TypeshedModule(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module_name: str,
        qualified_name: str,
        tp_dict: Dict,
    ):
        super().__init__(name, is_exported, module_name, qualified_name)
        self.tp_uuid = name
        self.tp_dict: Dict = tp_dict

    def get_name(self, attr_name: str):
        if attr_name not in self.tp_dict:
            # possible it's a module
            sub_module = f"{self.module_name}.{attr_name}"
            return parse_module(sub_module)
        name_info = self.tp_dict[attr_name]
        return resolve_attribute(name_info)


class AssignNameInfo(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module_name: str,
        qualified_name: str,
        node: ast.Assign,
    ):
        super().__init__(name, is_exported, module_name, qualified_name)
        self.node: ast.Assign = node


class AnnAssignNameInfo(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module: str,
        full_name: str,
        node: ast.AnnAssign,
    ):
        super().__init__(name, is_exported, module, full_name)
        self.node: ast.AnnAssign = node


class TypeshedClass(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module_name: str,
        qualified_name: str,
        node: ast.ClassDef,
        child_nodes: Dict[str, ...],
    ):
        super().__init__(name, is_exported, module_name, qualified_name)
        self.node: ast.ClassDef = node
        self.tp_dict: Dict[str, ...] = child_nodes

    def get_name(self, attr: str):
        if attr not in self.tp_dict:
            # possible it's a module
            raise AttributeError(attr)
        name_info = self.tp_dict[attr]
        return resolve_attribute(name_info)


class PossibleImportedNameInfo(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module_name: str,
        full_name: str,
        imported_module: str,
        imported_name: Optional[str],
    ):
        super().__init__(name, is_exported, module_name, full_name)
        self.imported_module: str = imported_module
        self.imported_name: Optional[str] = imported_name


class ImportedModuleInfo(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module: str,
        full_name: str,
        imported_module: str,
    ):
        super().__init__(name, is_exported, module, full_name)
        self.imported_module: str = imported_module


class ImportedNameInfo(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module: str,
        full_name: str,
        imported_module: str,
        imported_name: str,
    ):
        super().__init__(name, is_exported, module, full_name)
        self.imported_module: str = imported_module
        self.imported_name: str = imported_name


class TypeshedFunction(BasicNameInfo):
    def __init__(self, name: str, is_exported: bool, module: str, full_name: str):
        super().__init__(name, is_exported, module, full_name)
        self.ordinaries: List[ast.FunctionDef] = []
        self.getters: List[ast.FunctionDef] = []
        self.setters: List[ast.FunctionDef] = []
        self.deleters: List[ast.FunctionDef] = []

    def append_ordinary(self, node: ast.FunctionDef):
        self.ordinaries.append(node)

    def append_getter(self, node: ast.FunctionDef):
        self.getters.append(node)

    def append_setter(self, node: ast.FunctionDef):
        self.setters.append(node)

    def append_deleter(self, node: ast.FunctionDef):
        self.deleters.append(node)


sys.analysis_typeshed_modules: Dict[str, TypeshedModule] = {}


def parse_module(
    module_name: str, search_context: SearchContext = None
) -> TypeshedModule:
    if module_name in sys.analysis_typeshed_modules:
        return sys.analysis_typeshed_modules[module_name]
    log.critical(f"Parsing {module_name}")
    if search_context is None:
        search_context = get_search_context()

    path = finder.get_stub_file(module_name)
    if path is None:
        raise FileNotFoundError(module_name)

    is_init = path.name == "__init__.pyi"
    module_content = path.read_text()
    module_ast = ast.parse(module_content)

    visitor = ModuleVisitor(search_context, module_name, module_name, is_init=is_init)
    module_dict = visitor.build(module_ast)
    module = TypeshedModule(module_name, True, module_name, module_name, module_dict)
    sys.analysis_typeshed_modules[module_name] = module

    return module


def is_exported_attr(name: str) -> bool:
    return not name.startswith("_")


def concatenate(prefix: str, curr: str):
    return f"{prefix}.{curr}"


class ModuleVisitor(ast.NodeVisitor):
    """Extract names from a stub module."""

    def __init__(
        self,
        search_context: SearchContext,
        module_name: str,
        qualified_name: str,
        is_init: bool = False,
    ) -> None:
        self.search_context = search_context
        self.module_name: str = module_name
        self.qualified_name: str = qualified_name
        self.is_init: bool = is_init
        self.module_dict = {}

    def build(self, module_ast: ast.AST):
        self.visit(module_ast)
        return self.module_dict

    def visit_FunctionDef(self, node: ast.FunctionDef):
        function_name = node.name
        is_exported = is_exported_attr(function_name)
        if function_name not in self.module_dict:
            self.module_dict[function_name] = TypeshedFunction(
                function_name,
                is_exported,
                self.module_name,
                f"{self.qualified_name}.{function_name}",
            )
        function_name_info: TypeshedFunction = self.module_dict[function_name]

        if not node.decorator_list:
            function_name_info.append_ordinary(node)
        else:
            # as far as I know, the decorators of ast.FunctionDef in typeshed could be classified as three categories:
            # 1. Normal functions(without decorators)
            # 2. Descriptor functions(@property, @xxx.setter and @xxx.deleter)
            # 3. other functions( such as @abstractmethod, @classmethod)
            getter, setter, deleter = False, False, False
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == "property":
                    function_name_info.append_getter(node)
                    getter = True
                elif (
                    isinstance(decorator, ast.Attribute) and decorator.attr == "setter"
                ):
                    function_name_info.append_setter(node)
                    setter = True
                elif (
                    isinstance(decorator, ast.Attribute) and decorator.attr == "deleter"
                ):
                    function_name_info.append_deleter(node)
                    deleter = True
            if any([getter, setter, deleter]):
                if getter + setter + deleter > 1:
                    raise NotImplementedError
            else:
                function_name_info.append_ordinary(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name = node.name
        is_exported = is_exported_attr(class_name)
        children_name_extractor = ModuleVisitor(
            self.search_context,
            self.module_name,
            f"{self.qualified_name}.{class_name}",
            is_init=self.is_init,
        )
        class_body_dict = children_name_extractor.build(ast.Module(body=node.body))
        self.module_dict[class_name] = TypeshedClass(
            class_name,
            is_exported,
            module_name=self.module_name,
            qualified_name=f"{self.qualified_name}.{class_name}",
            node=node,
            child_nodes=class_body_dict,
        )

    def visit_Assign(self, node: ast.Assign):
        assert len(node.targets) == 1, node
        for target in node.targets:
            if not isinstance(target, ast.Name):
                raise InvalidStub(
                    f"Assignment should only be to a simple name: {ast.dump(node)}"
                )
            self.module_dict[target.id] = AssignNameInfo(
                target.id,
                not target.id.startswith("_"),
                module_name=self.module_name,
                qualified_name=f"{self.qualified_name}.{target.id}",
                node=node,
            )

    def visit_AnnAssign(self, node: ast.AnnAssign):
        target = node.target
        if not isinstance(target, ast.Name):
            raise InvalidStub(
                f"Assignment should only be to a simple name: {ast.dump(node)}"
            )
        self.module_dict[target.id] = AnnAssignNameInfo(
            target.id,
            not target.id.startswith("_"),
            module=self.module_name,
            full_name=f"{self.qualified_name}.{target.id}",
            node=node,
        )

    def visit_If(self, node: ast.If):
        visitor = LiteralEvalVisitor(self.search_context)
        value = visitor.visit(node.test)
        if value:
            self.visit(ast.Module(body=node.body))
        else:
            self.visit(ast.Module(body=node.orelse))

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.asname is not None:
                self.module_dict[alias.asname] = ImportedModuleInfo(
                    alias.asname,
                    True,
                    module=self.module_name,
                    full_name=concatenate(self.qualified_name, alias.asname),
                    imported_module=alias.name,
                )
            else:
                # "import a.b" just binds the name "a"
                name = alias.name.partition(".")[0]
                self.module_dict[name] = ImportedModuleInfo(
                    name,
                    True,
                    module=self.module_name,
                    full_name=concatenate(self.qualified_name, name),
                    imported_module=name,
                )

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
                is_exported = not alias.asname.startswith("_")
                self.module_dict[alias.asname] = PossibleImportedNameInfo(
                    alias.asname,
                    is_exported,
                    module_name=self.module_name,
                    full_name=concatenate(self.qualified_name, alias.asname),
                    imported_module=source_module,
                    imported_name=alias.name,
                )
            elif alias.name == "*":
                module = parse_module(source_module)
                name_dict = module.tp_dict
                if name_dict is None:
                    log.critical(
                        f"could not import {source_module} with "
                        f"{self.search_context}"
                    )
                    raise ModuleNotFoundError
                for name, info in name_dict.items():
                    if info.is_exported:
                        self.module_dict[name] = ImportedNameInfo(
                            name,
                            True,
                            module=self.module_name,
                            full_name=concatenate(self.qualified_name, name),
                            imported_module=source_module,
                            imported_name=name,
                        )
            else:
                is_exported: bool = not alias.name.startswith("_")
                self.module_dict[alias.name] = PossibleImportedNameInfo(
                    alias.name,
                    is_exported,
                    module_name=self.module_name,
                    full_name=concatenate(self.qualified_name, alias.name),
                    imported_module=source_module,
                    imported_name=alias.name,
                )

    def visit_Expr(self, node: ast.Expr):
        if not isinstance(node.value, (ast.Ellipsis, ast.Str)):
            raise InvalidStub(f"Cannot handle node {ast.dump(node)}")


def resolve_attribute(attribute: BasicNameInfo):
    if isinstance(attribute, PossibleImportedNameInfo):
        res = parse_module(attribute.imported_module)
        if attribute.imported_name in res.tp_dict:
            new_attribute = res.tp_dict[attribute.imported_name]
            return resolve_attribute(new_attribute)
        else:
            return parse_module(
                f"{attribute.imported_module}.{attribute.imported_name}"
            )
    elif isinstance(attribute, ImportedModuleInfo):
        return parse_module(attribute.imported_module)
    elif isinstance(attribute, ImportedNameInfo):
        module = parse_module(attribute.imported_module)
        new_attribute = module.tp_dict[attribute.imported_name]
        return resolve_attribute(new_attribute)
    elif isinstance(attribute, TypeshedClass):
        return attribute
    elif isinstance(attribute, TypeshedFunction):
        return attribute
    elif isinstance(attribute, AssignNameInfo):
        raise NotImplementedError(attribute)
    elif isinstance(attribute, AnnAssignNameInfo):
        return attribute
    else:
        raise NotImplementedError(attribute)
