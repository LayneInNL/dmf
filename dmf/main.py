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
import builtins
import logging
import os.path
import sys

# from analysis import Analysis
from dmf import static_importlib

logging.basicConfig(level=logging.DEBUG)
parser = argparse.ArgumentParser()
parser.add_argument("entry_file_path", help="the entry file path")

if __name__ == "__main__":
    args = parser.parse_args()
    entry_file_path = args.entry_file_path
    abs_path = os.path.abspath(entry_file_path)
    logging.debug("Absolute entry file path is: {}".format(abs_path))

    # our custom modules, simulating sys.modules
    builtins.analysis_modules = {}
    # used in analysis
    builtins.custom_analysis_modules = {}
    # our custom root path, simulating sys.path
    # insert being analyzed dir into sys.path
    dir_name = os.path.dirname(entry_file_path)
    # dir_name = "C:\\Users\\Layne Liu\\PycharmProjects\\cfg\\dmf\\examples\\"
    sys.path.insert(0, dir_name)
    logging.debug("updated sys.path {}".format(sys.path))

    mod_file = os.path.basename(entry_file_path)
    mod_name = mod_file.rpartition(".")[0]
    main_module = static_importlib.import_module(mod_name)
    print(main_module)
