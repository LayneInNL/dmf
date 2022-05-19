"""A pure Python implementation of import."""
__all__ = ["import_module"]

# Bootstrap help #####################################################

# Until bootstrapping is complete, DO NOT import any modules that attempt
# to import importlib._bootstrap (directly or indirectly). Since this
# partially initialised package would be present in sys.modules, those
# modules would get an uninitialised copy of the source version, instead
# of a fully initialised version (either the frozen one or the one
# initialised below if the frozen one is not available).
import _imp  # Just the builtin component, NOT the full Python module
import dmf.share
import sys

from . import _bootstrap

_bootstrap._setup(sys, _imp)

from . import _bootstrap_external

_bootstrap_external._setup(_bootstrap)
_bootstrap._bootstrap_external = _bootstrap_external

# try:
#     import _frozen_importlib as _bootstrap
# except ImportError:
#     from . import _bootstrap
#
#     _bootstrap._setup(sys, _imp)
# else:
#     # importlib._bootstrap is the built-in import, ensure we don't create
#     # a second copy of the module.
#     _bootstrap.__name__ = "importlib._bootstrap"
#     _bootstrap.__package__ = "importlib"
#     try:
#         _bootstrap.__file__ = __file__.replace("__init__.py", "_bootstrap.py")
#     except NameError:
#         # __file__ is not guaranteed to be defined, e.g. if this code gets
#         # frozen by a tool like cx_Freeze.
#         pass
#     sys.modules["importlib._bootstrap"] = _bootstrap
#
# try:
#     import _frozen_importlib_external as _bootstrap_external
# except ImportError:
#     from . import _bootstrap_external
#
#     _bootstrap_external._setup(_bootstrap)
#     _bootstrap._bootstrap_external = _bootstrap_external
# else:
#     _bootstrap_external.__name__ = "importlib._bootstrap_external"
#     _bootstrap_external.__package__ = "importlib"
#     try:
#         _bootstrap_external.__file__ = __file__.replace(
#             "__init__.py", "_bootstrap_external.py"
#         )
#     except NameError:
#         # __file__ is not guaranteed to be defined, e.g. if this code gets
#         # frozen by a tool like cx_Freeze.
#         pass
#     sys.modules["importlib._bootstrap_external"] = _bootstrap_external

# To simplify imports in test code
_w_long = _bootstrap_external._w_long
_r_long = _bootstrap_external._r_long

# Fully bootstrapped at this point, import whatever you like, circular
# dependencies and startup overhead minimisation permitting :)

import types
import warnings


# Public API #########################################################

# from ._bootstrap import __import__


def import_module(name, package=None):
    """Import a module.

    The 'package' argument is required when performing a relative import. It
    specifies the package to use as the anchor point from which to resolve the
    relative import to an absolute import.

    """
    level = 0
    if name.startswith("."):
        if not package:
            msg = (
                "the 'package' argument is required to perform a relative "
                "import for {!r}"
            )
            raise TypeError(msg.format(name))
        for character in name:
            if character != ".":
                break
            level += 1
    return _bootstrap._gcd_import(name[level:], package, level)


dmf.share.static_import_module = import_module

_RELOADING = {}
