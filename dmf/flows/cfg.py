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
import ast
import logging
import os

from dmf.flows import flows, comments


def pre_check(project_dir):
    for (path_dir, _, file_names) in os.walk(project_dir):
        for name in file_names:
            path = os.path.join(path_dir, name)
            if name.endswith(".py"):
                logging.critical(f"Checking {path}")
                with open(path) as handler:
                    source = handler.read()
                    comments_cleaner = comments.CommentsCleaner(source)
                    visitor = flows.CFGVisitor()
                    base_name = os.path.basename(path)
                    visitor.build(base_name, ast.parse(comments_cleaner.source))


def construct_CFG(file_path) -> flows.CFG:
    with open(file_path) as handler:
        source = handler.read()
        comments_cleaner = comments.CommentsCleaner(source)
        visitor = flows.CFGVisitor()
        base_name = os.path.basename(file_path)
        cfg = visitor.build(base_name, ast.parse(comments_cleaner.source))
        logging.debug("Previous edges: {}".format(sorted(cfg.edges.keys())))
        logging.debug("Refactored flows: {}".format(visitor.cfg.flows))
        logging.debug(
            "Refactored inter flows: {}".format(visitor.cfg.call_return_flows)
        )
        cfg.show()

        return cfg
