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

import argparse
import os.path
import sys
import time

# Must put it here to initialize static_importlib
import dmf.static_importlib

import dmf.share
from dmf.analysis.heap import analysis_heap
from dmf.analysis.value import ModuleType
from dmf.log.logger import logger

parser = argparse.ArgumentParser()
parser.add_argument("main", help="the main file path")


def add_builtin_module(path):
    static_builtin_module = ModuleType(name="static_builtins", package=None, file=path)
    static_builtin_module.namespace["__object__"] = object()
    dmf.share.analysis_modules["static_builtins"] = static_builtin_module


def add_main_module(path):
    # main_module = type(sys)("__main__")
    # dmf.share.modules["__main__"] = main_module
    analysis_main_module = ModuleType(name="__main__", package="", file=path)
    dmf.share.analysis_modules["__main__"] = analysis_main_module


def add_sys_path(path):
    # our custom root path, simulating sys.path
    # insert being analyzed dir into sys.path
    # for example, dir_name = "C:\\Users\\Layne Liu\\PycharmProjects\\cfg\\dmf\\examples\\"
    dir_name = os.path.dirname(path)
    # insert to the beginning of sys.path
    sys.path.insert(0, dir_name)
    logger.debug("updated sys.path {}".format(sys.path))


if __name__ == "__main__":
    args = parser.parse_args()
    main_file_path = args.main
    if not main_file_path:
        exit()
    # get main module absolute path
    main_abs_path = os.path.abspath(main_file_path)

    add_main_module(main_abs_path)
    # add builtin objects
    builtin_file_path = "./share/static_builtins.py"
    builtin_abs_path = os.path.abspath(builtin_file_path)
    add_builtin_module(builtin_abs_path)

    from dmf.analysis.analysis import Analysis

    # load cfg of static builtin module
    analysis = Analysis("static_builtins")
    analysis.compute_fixed_point()
    # calculate builtin module
    dmf.share.static_builtins = True
    # sleep 2 seconds
    time.sleep(1)

    # module name
    main_module_name = os.path.basename(main_abs_path).rpartition(".")[0]
    add_main_module(main_abs_path)
    add_sys_path(main_abs_path)

    # load cfg of main module
    analysis = Analysis("__main__")
    analysis.compute_fixed_point()
    print(analysis_heap)
