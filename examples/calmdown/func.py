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

x = 2


def test(x=1):
    return x


res = test()


def test1():
    yield 1


gen = test1()


# def test():
#     yield 1


# def test1(x):
#     def test1():
#         return x
#
#     return test1


# res = test1(2)
# real_res = res()
# a = test1(1)
# test1.x = 1
# y = test1.x
