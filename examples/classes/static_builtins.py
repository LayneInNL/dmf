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
# class EOFB(Exception):
#     pass
#
#
# class InvalidData(Exception):
#     pass


# Given integer x, this returns the integer floor(sqrt(x)).
def sqrt(x: int) -> int:
    assert x >= 0
    i: int = 1
    while i * i <= x:
        i *= 2
    y: int = 0
    while i > 0:
        if (y + i) ** 2 <= x:
            y += i
        i //= 2
    return y
