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

Unused_Name = "-1024"


class RandomVariableName:
    counter = 0

    @classmethod
    def gen_random_name(cls) -> str:
        cls.counter += 1
        return str(cls.counter) + "var"


class RandomGeneratorName:
    counter = 0
    prefix = "_gen_exp_"

    @classmethod
    def gen_generator_name(cls) -> str:
        cls.counter += 1
        return cls.prefix + str(cls.counter)


class RandomIterable:
    counter = 0
    prefix = "_tmp_iter_"

    @classmethod
    def gen_iter(cls) -> str:
        cls.counter += 1
        return cls.prefix + str(cls.counter)


class RandomReturnName:
    counter = 0
    prefix = "_tmp_return_"

    @classmethod
    def gen_return_name(cls) -> str:
        cls.counter += 1
        return cls.prefix + str(cls.counter)
