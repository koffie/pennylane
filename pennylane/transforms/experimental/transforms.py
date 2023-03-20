# Copyright 2018-2022 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
This module contains the transform decorator.
"""
import functools
import inspect
import os
import warnings

import pennylane as qml


class OperationTransformError(Exception):
    """Raised when there is an error with the op_transform logic"""


def default_qnode_postprocessing():
    return lambda res: res


class transform:
    r"""Convert a function that applies to op/tape into a QNode transform."""

    def __init__(self, fn):
        if not callable(fn):
            raise OperationTransformError(
                f"The operator function to register, {fn}, "
                "does not appear to be a valid Python function or callable."
            )

        self.fn = fn
        # TODO check signature to force the fn style (batch_tape, fn) - > (batch_tape, fn)
        self._sig = inspect.signature(fn).parameters
        functools.update_wrapper(self, fn)

    def __call__(self, *targs, **tkwargs):
        obj = None

        if targs:
            # assume the first argument passed to the transform
            # is the object we wish to transform
            obj, *targs = targs

        if isinstance(obj, qml.tape.QuantumTape):
            return self._fn(obj, *targs, **tkwargs)
        elif isinstance(obj, qml.QNodeExperimental):
            return self.default_qnode_transform(obj, targs, tkwargs)
        elif callable(obj):
            return self.default_qfunc_transform(obj, targs, tkwargs)

    def default_qfunc_transform(self, qfunc, targs, tkwargs):
        """Register a qnode transformation"""

        def wrap(*args, **kwargs):
            tape = qml.tape.make_qscript(qfunc)(*args, **kwargs)
            new_tape, _ = self.fn(tape, *targs, **tkwargs)

            for op in new_tape[0].circuit:
                qml.apply(op)
        return wrap
    def default_qnode_transform(self, qnode, targs, tkwargs, expand_fn=None):
        """Register a qnode transformation"""
        qnode.transform_program.push(
            Transform(self.fn, targs, tkwargs, expand_fn, default_qnode_postprocessing)
        )
        return qnode


class Transform:
    def __init__(self, fn, args, kwargs, expand_fn, qnode_processing):
        self.transform_fn = fn
        self.targs = args
        self.tkwargs = kwargs
        self.expand_fn = expand_fn
        self.qnode_processing = qnode_processing


class TransformProgram:
    def __init__(self):
        self._transform_program = []

    def push(self, transform):
        self._transform_program.append(transform)

    def pop(self):
        transform = self._transform_program.pop(0)
        return (
            transform.transform_fn,
            transform.targs,
            transform.tkwargs,
            transform.expand_fn,
            transform.qnode_processing,
        )

    def dag(self):
        import networkx as nx
        g = nx.MultiDiGraph()
        for transf in self._transform_program:
            g.add_node(transf)
        for i in range(len(self._transform_program)-1):
            g.add_edge(self._transform_program[i], self._transform_program[i+1])
        return g
