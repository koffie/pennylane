# Copyright 2022 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for the classical shadows measurement process"""

import pytest
import copy

import pennylane as qml
from pennylane import numpy as np


def get_circuit(wires, shots, seed_recipes, interface="autograd", force_super=False):
    """
    Return a QNode that prepares the state (|00...0> + |11...1>) / sqrt(2)
        and performs the classical shadow measurement
    """
    dev = qml.device("default.qubit", wires=wires, shots=shots)

    if force_super:
        # make the device call the superclass method to switch between the general qubit device and device specific implementations (i.e. for default qubit)
        dev.classical_shadow = super(type(dev), dev).classical_shadow

    @qml.qnode(dev, interface=interface)
    def circuit():
        qml.Hadamard(wires=0)

        for target in range(1, wires):
            qml.CNOT(wires=[0, target])

        return qml.classical_shadow(wires=range(wires), seed_recipes=seed_recipes)

    return circuit


class TestShadowMeasurement:

    wires_list = [1, 2, 3, 5, 8]
    shots_list = [1, 10, 100, 1000]
    seed_recipes_list = [True, False]

    @pytest.mark.parametrize("wires", wires_list)
    @pytest.mark.parametrize("shots", shots_list)
    @pytest.mark.parametrize("seed", seed_recipes_list)
    def test_measurement_process_numeric_type(self, wires, shots, seed):
        """Test that the numeric type of the MeasurementProcess instance is correct"""
        dev = qml.device("default.qubit", wires=wires, shots=shots)
        res = qml.classical_shadow(wires=range(wires), seed_recipes=seed)
        assert res.numeric_type == int

    @pytest.mark.parametrize("wires", wires_list)
    @pytest.mark.parametrize("shots", shots_list)
    @pytest.mark.parametrize("seed", seed_recipes_list)
    def test_measurement_process_shape(self, wires, shots, seed):
        """Test that the shape of the MeasurementProcess instance is correct"""
        dev = qml.device("default.qubit", wires=wires, shots=shots)
        res = qml.classical_shadow(wires=range(wires), seed_recipes=seed)
        assert res.shape(dev) == (2, shots, wires)

    @pytest.mark.parametrize("wires", wires_list)
    @pytest.mark.parametrize("shots", shots_list)
    @pytest.mark.parametrize("seed", seed_recipes_list)
    def test_measurement_process_copy(self, wires, shots, seed):
        """Test that the attributes of the MeasurementProcess instance are
        correctly copied"""
        dev = qml.device("default.qubit", wires=wires, shots=shots)
        res = qml.classical_shadow(wires=range(wires), seed_recipes=seed)

        copied_res = copy.copy(res)
        assert type(copied_res) == type(res)
        assert copied_res.return_type == res.return_type
        assert copied_res.wires == res.wires
        assert copied_res.seed == res.seed

    @pytest.mark.all_interfaces
    @pytest.mark.parametrize("wires", wires_list)
    @pytest.mark.parametrize("shots", shots_list)
    @pytest.mark.parametrize("seed", seed_recipes_list)
    @pytest.mark.parametrize("interface", ["autograd", "jax", "tf", "torch"])
    @pytest.mark.parametrize("default_impl", [False, True])
    def test_format(self, wires, shots, seed, interface, default_impl):
        """Test that the format of the returned classical shadow
        measurement is correct"""
        import torch

        circuit = get_circuit(wires, shots, seed, interface, default_impl)
        shadow = circuit()

        # test shape and dtype are correct
        assert shadow.shape == (2, shots, wires)
        assert shadow.dtype == np.uint8 if interface != "torch" else torch.uint8

        bits, recipes = shadow

        # test allowed values of bits and recipes
        assert qml.math.all(np.logical_or(bits == 0, bits == 1))
        assert qml.math.all(np.logical_or(recipes == 0, np.logical_or(recipes == 1, recipes == 2)))

    @pytest.mark.parametrize("wires", wires_list)
    @pytest.mark.parametrize("seed", seed_recipes_list)
    def test_shots_none_error(self, wires, seed):
        """Test that an error is raised when a device with shots=None is used
        to obtain classical shadows"""
        circuit = get_circuit(wires, None, seed)

        msg = "The number of shots has to be explicitly set on the device when using sample-based measurements"
        with pytest.raises(qml.QuantumFunctionError, match=msg):
            shadow = circuit()
