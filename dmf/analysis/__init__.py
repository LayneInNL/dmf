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
import sys

# heap of state
sys.heap = None
# program_point
sys.program_point = None

# mimic sys.path
sys.analysis_path = []
# mimic sys.meta_path
sys.analysis_meta_path = []
# mimic sys.path_hooks
sys.analysis_path_hooks = []

# mimic sys.modules, as fake ones
sys.analysis_modules = {}
# mimic sys.modules, but used for typeshed
sys.analysis_typeshed_modules = {}
# mimic sys.modules
sys.fake_analysis_modules = {}

# mimic exec(module)
sys.prepend_flows = []
