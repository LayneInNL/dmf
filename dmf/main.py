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

from dmf.analysis.analysis import Analysis
from dmf.analysis.analysis_types import AnalysisModule
from dmf.share import create_and_update_cfg, analysis_modules

parser = argparse.ArgumentParser()
parser.add_argument("main", help="the main file path")


def add_main_module(path):
    entry_label, exit_label = create_and_update_cfg(path)
    main_module = AnalysisModule(
        tp_uuid="__main__", tp_package="", tp_entry=entry_label, tp_exit=exit_label
    )
    analysis_modules["__main__"] = main_module


# def add_sys_path(path):
#     # our custom root path, simulating sys.path
#     # insert being analyzed dir into sys.path
#     # for example, dir_name = "C:\\Users\\Layne Liu\\PycharmProjects\\cfg\\dmf\\examples\\"
#     dir_name = os.path.dirname(path)
#     # insert to the beginning of sys.path
#     sys.path.insert(0, dir_name)
#     logger.debug("updated sys.path {}".format(sys.path))


if __name__ == "__main__":
    args = parser.parse_args()
    main_file_path = args.main
    if not main_file_path:
        exit()

    # get main module absolute path
    main_abs_file_path = os.path.abspath(main_file_path)
    add_main_module(main_abs_file_path)

    # module name
    # main_module_name = os.path.basename(main_abs_path).rpartition(".")[0]
    # add_sys_path(main_abs_path)

    # load cfg of main module

    analysis = Analysis("__main__")
    analysis.compute_fixed_point()
