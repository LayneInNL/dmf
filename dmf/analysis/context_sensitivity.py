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

"""
In this thesis we are gonna use object sensitivity.
"""

from typing import Tuple

# The context grows from left to right, since in this way it's simpler to implement in Python.


def record(heap: int, ctx: Tuple) -> Tuple:
    """
    record to create new heap context
    :param heap: allocation site label
    :param ctx:  context
    :return: new heap context
    """
    return ctx[-1:] + (heap,)


def merge(heap: int, hctx: Tuple, ctx: Tuple) -> Tuple:
    return hctx[-2:]
