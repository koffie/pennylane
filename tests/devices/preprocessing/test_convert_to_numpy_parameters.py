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
"""This file tests the convert_to_numpy_parameters function."""
import pytest

import numpy as np

import pennylane as qml
from pennylane.devices.preprocessing import convert_to_numpy_parameters


ml_frameworks_list = [
    pytest.param("autograd", marks=pytest.mark.autograd),
    pytest.param("jax", marks=pytest.mark.jax),
    pytest.param("torch", marks=pytest.mark.torch),
    pytest.param("tensorflow", marks=pytest.mark.tf),
]


@pytest.mark.parametrize("framework", ml_frameworks_list)
def test_convert_autograd_arrays_to_numpy(framework):
    """Tests that convert_to_numpy_parameters works with autograd arrays."""

    x = qml.math.asarray(np.array(1.234), like=framework)
    y = qml.math.asarray(np.array(0.652), like=framework)
    M = qml.math.asarray(np.eye(2), like=framework)
    state = qml.math.asarray(np.array([1, 0]), like=framework)

    numpy_data = np.array(0.62)

    ops = [qml.RX(x, 0), qml.RY(y, 1), qml.CNOT((0, 1)), qml.RZ(numpy_data, 0)]
    m = [qml.state(), qml.expval(qml.Hermitian(M, 0))]
    prep = [qml.QubitStateVector(state, 0)]

    qs = qml.tape.QuantumScript(ops, m, prep)
    new_qs = convert_to_numpy_parameters(qs)

    # check ops that should be unaltered
    assert new_qs[3] is qs[3]
    assert new_qs[4] is qs[4]
    assert new_qs.measurements[0] is qs.measurements[0]

    for ind in (0, 1, 2, 6):
        assert qml.equal(new_qs[ind], qs[ind], check_interface=False, check_trainability=False)
        assert qml.math.get_interface(*new_qs[ind].data) == "numpy"
