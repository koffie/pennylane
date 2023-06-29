# Copyright 2018-2023 Xanadu Quantum Technologies Inc.

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
This file contains preprocessings steps that may be called internally
during execution.
"""
import copy

import pennylane as qml
from pennylane import math
from pennylane.tape import QuantumTape
from pennylane.typing import ResultBatch

from typing import Tuple, Callable

from .core import transform


def _is_count_result(r):
    """Checks if ``r`` is a single count (or broadcasted count) result"""
    return isinstance(r, dict) or isinstance(r, list) and all(isinstance(i, dict) for i in r)


def _recursive_asarray(res, like="jax"):
    """From a list of tapes results (each result is either a np.array or tuple), transform it to a list of Jax
    results (structure stay the same)."""
    res_ = []
    for r in res:
        if _is_count_result(r):
            res_.append(r)
        elif not isinstance(r, tuple):
            res_.append(math.asarray(r, like=like))
        else:
            sub_r = []
            for r_i in r:
                if _is_count_result(r_i):
                    sub_r.append(r_i)
                else:
                    sub_r.append(math.asarray(r_i, like=like))
            res_.append(tuple(sub_r))
    return tuple(res_) if len(res_) > 1 else res_[0]


def _convert_op_to_numpy_data(op: qml.operation.Operator) -> qml.operation.Operator:
    if math.get_interface(*op.data) == "numpy":
        return op
    # Use operator method to change parameters when it become available
    copied_op = copy.copy(op)
    copied_op.data = math.unwrap(op.data)
    return copied_op


def _convert_measurement_to_numpy_data(
    m: qml.measurements.MeasurementProcess,
) -> qml.measurements.MeasurementProcess:
    if m.obs is None or math.get_interface(*m.obs.data) == "numpy":
        return m
    # Use measurement method to change parameters when it becomes available
    copied_m = copy.copy(m)
    if isinstance(copied_m.obs, qml.operation.Tensor):
        copied_m.obs.data = math.unwrap([o.data for o in m.obs.obs])
    else:
        copied_m.obs.data = math.unwrap(m.obs.data)
    return copied_m


# pylint: disable=protected-access
def convert_to_numpy_parameters(
    circuit: QuantumTape,
) -> Tuple[Tuple[QuantumTape], Callable[[ResultBatch], ResultBatch]]:
    """Transforms a circuit to one with purely numpy parameters.

    Args:
        tape (QuantumScript): a circuit with parameters of any interface

    Returns:
        QuantumScript: A circuit with purely numpy parameters

    .. seealso::

        :class:`pennylane.tape.Unwrap` modifies a :class:`~.pennylane.tape.QuantumScript` in place instead of creating
        a new class. It will also set all parameters on the circuit, not just ones that need to be unwrapped.

    >>> ops = [qml.S(0), qml.RX(torch.tensor(0.1234), 0)]
    >>> measurements = [qml.state(), qml.expval(qml.Hermitian(torch.eye(2), 0))]
    >>> circuit = qml.tape.QuantumScript(ops, measurements )
    >>> new_circuit = convert_to_numpy_parameters(circuit)
    >>> new_circuit.circuit
    [S(wires=[0]),
    RX(0.1234000027179718, wires=[0]),
    state(wires=[]),
    expval(Hermitian(array([[1., 0.],
            [0., 1.]], dtype=float32), wires=[0]))]

    If the component's data does not need to be transformed, it is left uncopied.

    >>> circuit[0] is new_circuit[0]
    True
    >>> circuit[1] is new_circuit[1]
    False
    >>> circuit[2] is new_circuit[2]
    True
    >>> circuit[3] is new_circuit[3]
    False

    """
    all_parameters = circuit.get_parameters()
    initial_interface = math.get_interface(*all_parameters)

    new_prep = (_convert_op_to_numpy_data(op) for op in circuit._prep)
    new_ops = (_convert_op_to_numpy_data(op) for op in circuit._ops)
    new_measurements = (_convert_measurement_to_numpy_data(m) for m in circuit.measurements)
    new_circuit = circuit.__class__(new_ops, new_measurements, new_prep, shots=circuit.shots)
    # must preserve trainable params as we lose information about the machine learning interface
    new_circuit.trainable_params = circuit.trainable_params
    new_circuit._qfunc_output = circuit._qfunc_output

    def cast_result_back_to_initial_interface(results: ResultBatch) -> ResultBatch:
        """Returns results to the initial interface removed in convert_to_numpy_parameters

        Args:
            results (ResultBatch): the result of executions

        Returns:
            ResultBatch

        Closure:
            initial_interface: the interface we need to cast the data back to.
        """
        return _recursive_asarray(results, like=initial_interface)

    return (new_circuit,), cast_result_back_to_initial_interface


convert_to_numpy_parameters_dispatcher = transform(convert_to_numpy_parameters)
