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
_typing_names_37 = {
    "AbstractSet",
    "Any",
    "AnyStr",
    "AsyncContextManager",
    "AsyncGenerator",
    "AsyncIterable",
    "AsyncIterator",
    "Awaitable",
    "ByteString",
    "Callable",
    "ChainMap",
    "ClassVar",
    "Collection",
    "Container",
    "ContextManager",
    "Coroutine",
    "Counter",
    "DefaultDict",
    "Deque",
    "Dict",
    "FrozenSet",
    "Generator",
    "Generic",
    "Hashable",
    "ItemsView",
    "Iterable",
    "Iterator",
    "KeysView",
    "List",
    "Mapping",
    "MappingView",
    "MutableMapping",
    "MutableSequence",
    "MutableSet",
    "NamedTuple",
    "NewType",
    "Optional",
    "Reversible",
    "Sequence",
    "Set",
    "Sized",
    "SupportsAbs",
    "SupportsBytes",
    "SupportsComplex",
    "SupportsFloat",
    "SupportsInt",
    "SupportsRound",
    "Text",
    "Tuple",
    "Type",
    "TypeVar",
    "Union",
    "ValuesView",
    "TYPE_CHECKING",
    "cast",
    "get_type_hints",
    "no_type_check",
    "no_type_check_decorator",
    "overload",
    "ForwardRef",
    "NoReturn",
    "OrderedDict",
}

_typing_names_38 = {
    "Final",
    "Literal",
    "Protocol",
    "SupportsIndex",
    "TypedDict",
    "final",
    "get_args",
    "get_origin",
    "runtime_checkable",
}

_typing_names_39 = {"Annotated", "BinaryIO", "IO", "Match", "Pattern", "TextIO"}

_typing_names_310 = {
    "Concatenate",
    "ParamSpec",
    "ParamSpecArgs",
    "ParamSpecKwargs",
    "TypeAlias",
    "TypeGuard",
    "is_typeddict",
}

_typing_names_311 = {
    "LiteralString",
    "Never",
    "NotRequired",
    "Required",
    "Self",
    "TypeVarTuple",
    "Unpack",
    "assert_never",
    "assert_type",
    "clear_overloads",
    "dataclass_transform",
    "get_overloads",
    "reveal_type",
}

all_typing_names = (
    _typing_names_37
    | _typing_names_38
    | _typing_names_39
    | _typing_names_310
    | _typing_names_311
)

import builtins

all_builtin_names = set(builtins.__dict__.keys())
