"""The machinery of static_importlib: finders, loaders, hooks, etc."""

import _imp

from .bootstrap import ModuleSpec
from .bootstrap import BuiltinImporter
from .bootstrap import FrozenImporter
from .bootstrap_external import (SOURCE_SUFFIXES, DEBUG_BYTECODE_SUFFIXES,
                                 OPTIMIZED_BYTECODE_SUFFIXES, BYTECODE_SUFFIXES,
                                 EXTENSION_SUFFIXES)
from .bootstrap_external import WindowsRegistryFinder
from .bootstrap_external import PathFinder
from .bootstrap_external import FileFinder
from .bootstrap_external import SourceFileLoader
from .bootstrap_external import SourcelessFileLoader
from .bootstrap_external import ExtensionFileLoader


def all_suffixes():
    """Returns a list of all recognized module suffixes for this process"""
    return SOURCE_SUFFIXES + BYTECODE_SUFFIXES + EXTENSION_SUFFIXES
