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
import logging

from dmf.analysis.pointsto import TypeAnalysis
from dmf.py2flows.py2flows.main import construct_CFG

parser = argparse.ArgumentParser()
parser.add_argument("file_name", help="the file name")

if __name__ == "__main__":
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    CFG = construct_CFG(args.file_name)
    mfp = TypeAnalysis(CFG)
    mfp.compute_fixed_point()
