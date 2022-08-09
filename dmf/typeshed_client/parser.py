"""This module is responsible for parsing a stub AST into a dictionary of names."""
from __future__ import annotations
import ast
import logging
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

from . import finder
from .finder import get_search_context, SearchContext, ModulePath

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


class ModuleNameInfo(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module: str,
        full_name: str,
        nl__dict__: Dict,
    ):
        super().__init__(name, is_exported, module, full_name)
        self.nl__dict__: Dict = nl__dict__

    def get_name(self, attr_name: str):
        if attr_name not in self.nl__dict__:
            raise AttributeError(attr_name)
        name_info = self.nl__dict__[attr_name]
        return name_info


class AssignNameInfo(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module: str,
        full_name: str,
        node: ast.Assign,
    ):
        super().__init__(name, is_exported, module, full_name)
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


class ClassNameInfo(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module: str,
        full_name: str,
        node: ast.ClassDef,
        child_nodes: Dict[str, ...],
    ):
        super().__init__(name, is_exported, module, full_name)
        self.node: ast.ClassDef = node
        self.child_nodes: Dict[str, ...] = child_nodes


class PossibleImportedNameInfo(BasicNameInfo):
    def __init__(
        self,
        name: str,
        is_exported: bool,
        module: str,
        full_name: str,
        imported_module: str,
        imported_name: Optional[str],
    ):
        super().__init__(name, is_exported, module, full_name)
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


class FunctionNameInfo(BasicNameInfo):
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


module_cache: Dict[str, ModuleNameInfo] = {}


def parse_module(
    module_name: str, search_context: SearchContext = None
) -> ModuleNameInfo:
    if module_name in module_cache:
        return module_cache[module_name]
    log.critical(f"Parsing {module_name}")
    if search_context is None:
        search_context = get_search_context()

    path = finder.get_stub_file(module_name)
    if path is None:
        raise FileNotFoundError(module_name)

    is_init = path.name == "__init__.pyi"
    module_content = path.read_text()
    module_ast = ast.parse(module_content)

    visitor = TypeshedVisitor(search_context, module_name, module_name, is_init=is_init)
    module_dict = visitor.build(module_ast)
    module = ModuleNameInfo(module_name, True, module_name, module_name, module_dict)
    module_cache[module_name] = module

    return module


def is_exported_attr(name: str) -> bool:
    return not name.startswith("_")


def concatenate(prefix: str, curr: str):
    return f"{prefix}.{curr}"


class TypeshedVisitor(ast.NodeVisitor):
    """Extract names from a stub module."""

    def __init__(
        self,
        search_context: SearchContext,
        module_name: str,
        full_name: str,
        is_init: bool = False,
    ) -> None:
        self.search_context = search_context
        self.module_name: str = module_name
        self.module_path = ModulePath(tuple(module_name.split(".")))
        self.full_name: str = full_name
        self.is_init: bool = is_init
        self.module_dict = {}

    def build(self, module_ast: ast.AST):
        self.visit(module_ast)
        return self.module_dict

    def visit_FunctionDef(self, node: ast.FunctionDef):
        function_name = node.name
        is_exported = is_exported_attr(function_name)
        if function_name not in self.module_dict:
            self.module_dict[function_name] = FunctionNameInfo(
                function_name,
                is_exported,
                self.module_name,
                f"{self.full_name}.{function_name}",
            )
        function_name_info: FunctionNameInfo = self.module_dict[function_name]

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
        children_name_extractor = TypeshedVisitor(
            self.search_context,
            self.module_name,
            f"{self.full_name}.{class_name}",
            is_init=self.is_init,
        )
        module_dict = children_name_extractor.build(ast.Module(body=node.body))
        self.module_dict[class_name] = ClassNameInfo(
            class_name,
            is_exported,
            module=self.module_name,
            full_name=f"{self.full_name}.{class_name}",
            node=node,
            child_nodes=module_dict,
        )

    def visit_Assign(self, node: ast.Assign):
        assert len(node.targets) == 1
        for target in node.targets:
            if not isinstance(target, ast.Name):
                raise InvalidStub(
                    f"Assignment should only be to a simple name: {ast.dump(node)}"
                )
            self.module_dict[target.id] = AssignNameInfo(
                target.id,
                not target.id.startswith("_"),
                module=self.module_name,
                full_name=f"{self.full_name}.{target.id}",
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
            full_name=f"{self.full_name}.{target.id}",
            node=node,
        )

    def visit_If(self, node: ast.If):
        visitor = _LiteralEvalVisitor(self.search_context)
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
                    full_name=concatenate(self.full_name, alias.asname),
                    imported_module=alias.name,
                )
            else:
                # "import a.b" just binds the name "a"
                name = alias.name.partition(".")[0]
                self.module_dict[name] = ImportedModuleInfo(
                    name,
                    True,
                    module=self.module_name,
                    full_name=concatenate(self.full_name, name),
                    imported_module=name,
                )

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module is None:
            module = ()
        else:
            module = tuple(node.module.split("."))
        if node.level == 0:
            source_module = ModulePath(module)
        elif node.level == 1:
            if self.is_init:
                source_module = ModulePath(self.module_path + module)
            else:
                source_module = ModulePath(self.module_path[:-1] + module)
        else:
            if self.is_init:
                source_module = ModulePath(self.module_path[: 1 - node.level] + module)
            else:
                source_module = ModulePath(self.module_path[: -node.level] + module)
        for alias in node.names:
            if alias.asname is not None:
                is_exported = not alias.asname.startswith("_")
                self.module_dict[alias.asname] = PossibleImportedNameInfo(
                    alias.asname,
                    is_exported,
                    module=self.module_name,
                    full_name=concatenate(self.full_name, alias.asname),
                    imported_module=".".join(source_module),
                    imported_name=alias.name,
                )
            elif alias.name == "*":
                module = parse_module(".".join(source_module))
                name_dict = module.nl__dict__
                if name_dict is None:
                    log.critical(
                        f"could not import {source_module} in {self.module_path} with "
                        f"{self.search_context}"
                    )
                    raise ModuleNotFoundError
                for name, info in name_dict.items():
                    if info.is_exported:
                        self.module_dict[name] = ImportedNameInfo(
                            name,
                            True,
                            module=self.module_name,
                            full_name=concatenate(self.full_name, name),
                            imported_module=".".join(source_module),
                            imported_name=name,
                        )
            else:
                is_exported: bool = not alias.name.startswith("_")
                self.module_dict[alias.name] = PossibleImportedNameInfo(
                    alias.name,
                    is_exported,
                    module=self.module_name,
                    full_name=concatenate(self.full_name, alias.name),
                    imported_module=".".join(source_module),
                    imported_name=alias.name,
                )

    def visit_Expr(self, node: ast.Expr):
        if not isinstance(node.value, (ast.Ellipsis, ast.Str)):
            raise InvalidStub(f"Cannot handle node {ast.dump(node)}")


_CMP_OP_TO_FUNCTION = {
    ast.Eq: lambda x, y: x == y,
    ast.NotEq: lambda x, y: x != y,
    ast.Lt: lambda x, y: x < y,
    ast.LtE: lambda x, y: x <= y,
    ast.Gt: lambda x, y: x > y,
    ast.GtE: lambda x, y: x >= y,
    ast.Is: lambda x, y: x is y,
    ast.IsNot: lambda x, y: x is not y,
    ast.In: lambda x, y: x in y,
    ast.NotIn: lambda x, y: x not in y,
}


class _LiteralEvalVisitor(ast.NodeVisitor):
    def __init__(self, ctx: SearchContext) -> None:
        self.ctx = ctx

    def visit_Num(self, node: ast.Num) -> Union[int, float]:
        return node.n

    def visit_Str(self, node: ast.Str) -> str:
        return node.s

    def visit_Index(self, node: ast.Index) -> int:
        return self.visit(node.value)

    def visit_Tuple(self, node: ast.Tuple) -> Tuple[Any, ...]:
        return tuple(self.visit(elt) for elt in node.elts)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        value = self.visit(node.value)
        slc = self.visit(node.slice)
        return value[slc]

    def visit_Compare(self, node: ast.Compare) -> bool:
        if len(node.ops) != 1:
            raise InvalidStub(f"Cannot evaluate chained comparison {ast.dump(node)}")
        fn = _CMP_OP_TO_FUNCTION[type(node.ops[0])]
        return fn(self.visit(node.left), self.visit(node.comparators[0]))

    def visit_BoolOp(self, node: ast.BoolOp) -> bool:
        for val_node in node.values:
            val = self.visit(val_node)
            if (isinstance(node.op, ast.Or) and val) or (
                isinstance(node.op, ast.And) and not val
            ):
                return val
        return val

    def visit_Slice(self, node: ast.Slice) -> slice:
        lower = self.visit(node.lower) if node.lower is not None else None
        upper = self.visit(node.upper) if node.upper is not None else None
        step = self.visit(node.step) if node.step is not None else None
        return slice(lower, upper, step)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        val = node.value
        if not isinstance(val, ast.Name):
            raise InvalidStub(f"Invalid code in stub: {ast.dump(node)}")
        if val.id != "sys":
            raise InvalidStub(
                f"Attribute access must be on the sys module: {ast.dump(node)}"
            )
        if node.attr == "platform":
            return self.ctx.platform
        elif node.attr == "version_info":
            return self.ctx.version
        else:
            raise InvalidStub(f"Invalid attribute on {ast.dump(node)}")


class Resolver:
    def __init__(self, search_context: Optional[SearchContext] = None) -> None:
        if search_context is None:
            search_context = get_search_context()
        self.search_context = search_context

    def resolve_module(self, module_name: str) -> ModuleNameInfo:
        return parse_module(module_name)

    def resolve_attribute(self, module_name: str, attr_name: str):
        module = self.resolve_module(module_name)
        attr = module.get_name(attr_name)
        if isinstance(attr, PossibleImportedNameInfo):
            res = self.resolve_module(attr.imported_module)
            if attr_name in res.nl__dict__:
                return self.resolve_attribute(attr.imported_module, attr.imported_name)
            else:
                return self.resolve_module(
                    f"{attr.imported_module}.{attr.imported_name}"
                )
        elif isinstance(attr, ImportedModuleInfo):
            return self.resolve_module(attr.imported_module)
        elif isinstance(attr, ImportedNameInfo):
            return self.resolve_attribute(attr.imported_module, attr.imported_name)
        elif isinstance(attr, ClassNameInfo):
            return attr
        elif isinstance(attr, FunctionNameInfo):
            return attr
        elif isinstance(attr, AssignNameInfo):
            return attr
        elif isinstance(attr, AnnAssignNameInfo):
            return attr
        else:
            raise NotImplementedError(attr)


class AbstractValue:
    def __init__(self):
        self.abstract_value = dict()

    def inject(self, abstract_value):
        self.abstract_value.update(abstract_value)


class TypeExprResolver(ast.NodeVisitor):
    def __init__(self, resolver: Resolver, module: str, expr: ast.expr):
        self.resolver: Resolver = resolver
        self.module: str = module
        self.expr: ast.expr = expr

    def resolve(self, name_info):
        if isinstance(name_info, ModuleNameInfo):
            return name_info
        elif isinstance(name_info, ClassNameInfo):
            return name_info
        elif isinstance(name_info, FunctionNameInfo):
            if any([name_info.getters, name_info.setters, name_info.deleters]):
                raise NotImplementedError
            else:
                return name_info
        elif isinstance(name_info, PossibleImportedNameInfo):
            res = self.resolver.resolve_module(name_info.imported_module)
            if name_info.imported_name in res.nl__dict__:
                return self.resolver.resolve_attribute(
                    name_info.imported_module, name_info.imported_name
                )
            else:
                return self.resolver.resolve_module(
                    f"{name_info.imported_module}.{name_info.imported_name}"
                )
        elif isinstance(name_info, ImportedModuleInfo):
            return self.resolver.resolve_module(name_info.imported_module)
        elif isinstance(name_info, ImportedNameInfo):
            return self.resolver.resolve_attribute(
                name_info.imported_module, name_info.imported_name
            )

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        raise NotImplementedError

    def visit_BinOp(self, node: ast.BinOp) -> AbstractValue:
        if not isinstance(node.op, ast.Or):
            raise NotImplementedError
        lhs_value = self.visit(node.left)
        rhs_value = self.visit(node.right)
        lhs_value.inject(rhs_value)
        return lhs_value

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        raise NotImplementedError

    def visit_Lambda(self, node: ast.Lambda) -> Any:
        raise NotImplementedError

    def visit_IfExp(self, node: ast.IfExp) -> Any:
        raise NotImplementedError

    def visit_Dict(self, node: ast.Dict) -> Any:
        raise NotImplementedError

    def visit_Set(self, node: ast.Set) -> Any:
        raise NotImplementedError

    def visit_ListComp(self, node: ast.ListComp) -> Any:
        raise NotImplementedError

    def visit_SetComp(self, node: ast.SetComp) -> Any:
        raise NotImplementedError

    def visit_DictComp(self, node: ast.DictComp) -> Any:
        raise NotImplementedError

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> Any:
        raise NotImplementedError

    def visit_Await(self, node: ast.Await) -> Any:
        raise NotImplementedError

    def visit_Yield(self, node: ast.Yield) -> Any:
        raise NotImplementedError

    def visit_YieldFrom(self, node: ast.YieldFrom) -> Any:
        raise NotImplementedError

    def visit_Compare(self, node: ast.Compare) -> Any:
        raise NotImplementedError

    def visit_Call(self, node: ast.Call) -> Any:
        raise NotImplementedError

    def visit_Num(self, node: ast.Num) -> Any:
        raise NotImplementedError

    def visit_Str(self, node: ast.Str) -> Any:
        raise NotImplementedError

    def visit_FormattedValue(self, node: ast.FormattedValue) -> Any:
        raise NotImplementedError

    def visit_JoinedStr(self, node: ast.JoinedStr) -> Any:
        raise NotImplementedError

    def visit_Bytes(self, node: ast.Bytes) -> Any:
        raise NotImplementedError

    def visit_NameConstant(self, node: ast.NameConstant) -> Any:
        if node.value is not None:
            raise NotImplementedError

    def visit_Ellipsis(self, node: ast.Ellipsis) -> Any:
        raise NotImplementedError

    def visit_Constant(self, node: ast.Constant) -> Any:
        raise NotImplementedError

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        raise NotImplementedError

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        if not isinstance(node.value, ast.Name):
            raise NotImplementedError

        value = self.visit(node.value)
        return value

    def visit_Starred(self, node: ast.Starred) -> Any:
        raise NotImplementedError

    def visit_Name(self, node: ast.Name) -> Any:
        id = node.id
        if id == "bool":
            pass
        elif id == "int":
            pass
        elif id == "float":
            pass
        elif id == "complex":
            pass
        elif id == "list":
            pass
        elif id == "range":
            pass
        elif id == "any":
            pass
        elif id == "str":
            pass
        elif id == "bytes":
            pass
        elif id == "bytearray":
            pass
        elif id == "memoryview":
            pass
        elif id == "set":
            pass
        elif id == "frozenset":
            pass
        elif id == "dict":
            pass
        else:
            module: ModuleNameInfo = module_cache[self.module]
            module_dict = module.nl__dict__
            if id in module_dict:
                name_info = module_dict[id]

            else:
                raise NotImplementedError

    def visit_List(self, node: ast.List) -> Any:
        raise NotImplementedError

    def visit_Tuple(self, node: ast.Tuple) -> Any:
        raise NotImplementedError
