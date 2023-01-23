# Copyright 2018-2021 Xanadu Quantum Technologies Inc.

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
Unit tests for the qubit matrix-based operations.
"""
import numpy as np
import pytest
from gate_data import H, I, S, T, X, Z
from scipy.stats import unitary_group

import pennylane as qml
from pennylane.operation import DecompositionUndefinedError
from pennylane.wires import Wires
from pennylane.ops.qubit.matrix_ops import pauli_basis, pauli_words, special_unitary_matrix


class TestUtilitiesForSpecialUnitary:
    """Test the utility functions ``pauli_basis``, ``pauli_words`` and ``special_unitary_matrix``
    that are used by the Operation SpecialUnitary."""

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_pauli_basis(self, n):
        """Test that the Pauli basis matrices are correct."""
        basis = pauli_basis(n)
        d = 4**n - 1
        assert basis.shape == (d, 2**n, 2**n)
        assert np.allclose(basis, basis.conj().transpose([0, 2, 1]))
        assert all(np.allclose(np.eye(2**n), b @ b) for b in basis)

    def test_pauli_basis_raises_too_few_wires(self):
        """Test that pauli_basis raises an error if less than one wire is given."""
        with pytest.raises(ValueError, match="Require at least one"):
            basis = pauli_basis(0)

    def test_pauli_basis_raises_too_many_wires(self):
        """Test that pauli_basis raises an error if too many wires are given."""
        with pytest.raises(ValueError, match="Creating the Pauli basis tensor"):
            basis = pauli_basis(8)

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_pauli_words(self, n):
        """Test that the Pauli words are correct."""
        words = pauli_words(n)
        d = 4**n - 1
        assert len(words) == d  # There are d words
        assert len(set(words)) == d  # The words are unique
        assert all(len(w) == n for w in words)  # The words all have length n

        # The words consist of I, X, Y, Z, all appear if n>1
        expected_letters = {"I", "X", "Y", "Z"} if n > 1 else {"X", "Y", "Z"}
        assert set("".join(words)) == expected_letters

        # The words are sorted lexicographically
        assert sorted(words) == words

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.parametrize("seed", [214, 2491, 8623])
    def test_special_unitary_matrix_random(self, n, seed):
        """Test that ``special_unitary_matrix`` returns a correctly-shaped
        unitary matrix for random input parameters."""
        np.random.seed(seed)
        d = 4**n - 1
        theta = np.random.random(d)
        matrix = special_unitary_matrix(theta, n)
        assert matrix.shape == (2**n, 2**n)
        assert np.allclose(matrix @ matrix.conj().T, np.eye(2**n))

    @pytest.mark.parametrize("seed", [214, 8623])
    def test_special_unitary_matrix_random_many_wires(self, seed):
        """Test that ``special_unitary_matrix`` returns a correctly-shaped
        unitary matrix for random input parameters and more than 5 wires."""
        np.random.seed(seed)
        n = 6
        d = 4**n - 1
        theta = np.random.random(d)
        matrix = special_unitary_matrix(theta, n)
        assert matrix.shape == (2**n, 2**n)
        assert np.allclose(matrix @ matrix.conj().T, np.eye(2**n))

    @pytest.mark.parametrize("n", [1, 2])
    @pytest.mark.parametrize("seed", [214, 2491, 8623])
    def test_special_unitary_matrix_random_broadcasted(self, n, seed):
        """Test that ``special_unitary_matrix`` returns a correctly-shaped
        unitary matrix for broadcasted random input parameters."""
        np.random.seed(seed)
        d = 4**n - 1
        theta = np.random.random((2, d))
        matrix = special_unitary_matrix(theta, n)
        assert matrix.shape == (2, 2**n, 2**n)
        assert all(np.allclose(m @ m.conj().T, np.eye(2**n)) for m in matrix)
        separate_matrices = [special_unitary_matrix(t, n) for t in theta]
        assert qml.math.allclose(separate_matrices, matrix)

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_special_unitary_matrix_single_param(self, n):
        """Test that ``special_unitary_matrix`` returns a Pauli rotation matrix for
        inputs with a single non-zero parameter, and that the parameter mapping
        matches the lexicographical ordering of ``pauli_words``."""
        d = 4**n - 1
        words = pauli_words(n)
        for word, theta in zip(words, np.eye(d)):
            x = 0.2142
            matrix = special_unitary_matrix(x * theta, n)
            paulirot_matrix = qml.PauliRot(-2 * x, word, wires=list(range(n))).matrix()
            assert np.allclose(matrix @ matrix.conj().T, np.eye(2**n))
            assert np.allclose(paulirot_matrix, matrix)


class TestQubitUnitary:
    """Tests for the QubitUnitary class."""

    def test_qubit_unitary_noninteger_pow(self):
        """Test QubitUnitary raised to a non-integer power raises an error."""
        U = np.array(
            [[0.98877108 + 0.0j, 0.0 - 0.14943813j], [0.0 - 0.14943813j, 0.98877108 + 0.0j]]
        )

        op = qml.QubitUnitary(U, wires="a")

        with pytest.raises(qml.operation.PowUndefinedError):
            op.pow(0.123)

    def test_qubit_unitary_noninteger_pow_broadcasted(self):
        """Test broadcasted QubitUnitary raised to a non-integer power raises an error."""
        U = np.array(
            [
                [[0.98877108 + 0.0j, 0.0 - 0.14943813j], [0.0 - 0.14943813j, 0.98877108 + 0.0j]],
                [[0.98877108 + 0.0j, 0.0 - 0.14943813j], [0.0 - 0.14943813j, 0.98877108 + 0.0j]],
            ]
        )

        op = qml.QubitUnitary(U, wires="a")

        with pytest.raises(qml.operation.PowUndefinedError):
            op.pow(0.123)

    @pytest.mark.parametrize("n", (1, 3, -1, -3))
    def test_qubit_unitary_pow(self, n):
        """Test qubit unitary raised to an integer power."""
        U = np.array(
            [[0.98877108 + 0.0j, 0.0 - 0.14943813j], [0.0 - 0.14943813j, 0.98877108 + 0.0j]]
        )

        op = qml.QubitUnitary(U, wires="a")
        new_ops = op.pow(n)

        assert len(new_ops) == 1
        assert new_ops[0].wires == op.wires

        mat_to_pow = qml.math.linalg.matrix_power(qml.matrix(op), n)
        new_mat = qml.matrix(new_ops[0])

        assert qml.math.allclose(mat_to_pow, new_mat)

    @pytest.mark.parametrize("n", (1, 3, -1, -3))
    def test_qubit_unitary_pow_broadcasted(self, n):
        """Test broadcasted qubit unitary raised to an integer power."""
        U = np.array(
            [
                [[0.98877108 + 0.0j, 0.0 - 0.14943813j], [0.0 - 0.14943813j, 0.98877108 + 0.0j]],
                [[0.4125124 + 0.0j, 0.0 - 0.91095199j], [0.0 - 0.91095199j, 0.4125124 + 0.0j]],
            ]
        )

        op = qml.QubitUnitary(U, wires="a")
        new_ops = op.pow(n)

        assert len(new_ops) == 1
        assert new_ops[0].wires == op.wires

        mat_to_pow = qml.math.linalg.matrix_power(qml.matrix(op), n)
        new_mat = qml.matrix(new_ops[0])

        assert qml.math.allclose(mat_to_pow, new_mat)

    @pytest.mark.autograd
    @pytest.mark.parametrize(
        "U,num_wires", [(H, 1), (np.kron(H, H), 2), (np.tensordot([1j, -1, 1], H, axes=0), 1)]
    )
    def test_qubit_unitary_autograd(self, U, num_wires):
        """Test that the unitary operator produces the correct output and
        catches incorrect input with autograd."""

        out = qml.QubitUnitary(U, wires=range(num_wires)).matrix()

        # verify output type
        assert isinstance(out, np.ndarray)

        # verify equivalent to input state
        assert qml.math.allclose(out, U)

        # test non-square matrix
        with pytest.raises(ValueError, match="must be of shape"):
            qml.QubitUnitary(U[:, 1:], wires=range(num_wires)).matrix()

        # test non-unitary matrix
        U3 = U.copy()
        U3[0, 0] += 0.5
        with pytest.warns(UserWarning, match="may not be unitary"):
            qml.QubitUnitary(U3, wires=range(num_wires), unitary_check=True).matrix()

        # test an error is thrown when constructed with incorrect number of wires
        with pytest.raises(ValueError, match="must be of shape"):
            qml.QubitUnitary(U, wires=range(num_wires + 1)).matrix()

    @pytest.mark.torch
    @pytest.mark.parametrize(
        "U,num_wires", [(H, 1), (np.kron(H, H), 2), (np.tensordot([1j, -1, 1], H, axes=0), 1)]
    )
    def test_qubit_unitary_torch(self, U, num_wires):
        """Test that the unitary operator produces the correct output and
        catches incorrect input with torch."""
        import torch

        U = torch.tensor(U)
        out = qml.QubitUnitary(U, wires=range(num_wires)).matrix()

        # verify output type
        assert isinstance(out, torch.Tensor)

        # verify equivalent to input state
        assert qml.math.allclose(out, U)

        # test non-square matrix
        with pytest.raises(ValueError, match="must be of shape"):
            qml.QubitUnitary(U[:, 1:], wires=range(num_wires)).matrix()

        # test non-unitary matrix
        U3 = U.detach().clone()
        U3[0, 0] += 0.5
        with pytest.warns(UserWarning, match="may not be unitary"):
            qml.QubitUnitary(U3, wires=range(num_wires), unitary_check=True).matrix()

        # test an error is thrown when constructed with incorrect number of wires
        with pytest.raises(ValueError, match="must be of shape"):
            qml.QubitUnitary(U, wires=range(num_wires + 1)).matrix()

    @pytest.mark.tf
    @pytest.mark.parametrize(
        "U,num_wires", [(H, 1), (np.kron(H, H), 2), (np.tensordot([1j, -1, 1], H, axes=0), 1)]
    )
    def test_qubit_unitary_tf(self, U, num_wires):
        """Test that the unitary operator produces the correct output and
        catches incorrect input with tensorflow."""
        import tensorflow as tf

        U = tf.Variable(U)
        out = qml.QubitUnitary(U, wires=range(num_wires)).matrix()

        # verify output type
        assert isinstance(out, tf.Variable)

        # verify equivalent to input state
        assert qml.math.allclose(out, U)

        # test non-square matrix
        with pytest.raises(ValueError, match="must be of shape"):
            qml.QubitUnitary(U[:, 1:], wires=range(num_wires)).matrix()

        # test non-unitary matrix
        U3 = tf.Variable(U + 0.5)
        with pytest.warns(UserWarning, match="may not be unitary"):
            qml.QubitUnitary(U3, wires=range(num_wires), unitary_check=True).matrix()

        # test an error is thrown when constructed with incorrect number of wires
        with pytest.raises(ValueError, match="must be of shape"):
            qml.QubitUnitary(U, wires=range(num_wires + 1)).matrix()

    @pytest.mark.jax
    @pytest.mark.parametrize(
        "U,num_wires", [(H, 1), (np.kron(H, H), 2), (np.tensordot([1j, -1, 1], H, axes=0), 1)]
    )
    def test_qubit_unitary_jax(self, U, num_wires):
        """Test that the unitary operator produces the correct output and
        catches incorrect input with jax."""
        from jax import numpy as jnp

        U = jnp.array(U)
        out = qml.QubitUnitary(U, wires=range(num_wires)).matrix()

        # verify output type
        assert isinstance(out, jnp.ndarray)

        # verify equivalent to input state
        assert qml.math.allclose(out, U)

        # test non-square matrix
        with pytest.raises(ValueError, match="must be of shape"):
            qml.QubitUnitary(U[:, 1:], wires=range(num_wires)).matrix()

        # test non-unitary matrix
        U3 = U + 0.5
        with pytest.warns(UserWarning, match="may not be unitary"):
            qml.QubitUnitary(U3, wires=range(num_wires), unitary_check=True).matrix()

        # test an error is thrown when constructed with incorrect number of wires
        with pytest.raises(ValueError, match="must be of shape"):
            qml.QubitUnitary(U, wires=range(num_wires + 1)).matrix()

    @pytest.mark.jax
    @pytest.mark.parametrize(
        "U,num_wires", [(H, 1), (np.kron(H, H), 2), (np.tensordot([1j, -1, 1], H, axes=0), 1)]
    )
    def test_qubit_unitary_jax_jit(self, U, num_wires):
        """Tests that QubitUnitary works with jitting."""
        import jax
        from jax import numpy as jnp

        U = jnp.array(U)
        f = lambda m: qml.QubitUnitary(m, wires=range(num_wires)).matrix()
        out = jax.jit(f)(U)
        assert qml.math.allclose(out, qml.QubitUnitary(U, wires=range(num_wires)).matrix())

    @pytest.mark.parametrize(
        "U,expected_gate,expected_params",
        [
            (I, qml.RZ, [0.0]),
            (Z, qml.RZ, [np.pi]),
            (S, qml.RZ, [np.pi / 2]),
            (T, qml.RZ, [np.pi / 4]),
            (qml.matrix(qml.RZ(0.3, wires=0)), qml.RZ, [0.3]),
            (qml.matrix(qml.RZ(-0.5, wires=0)), qml.RZ, [-0.5]),
            (
                np.array(
                    [
                        [0, -9.831019270939975e-01 + 0.1830590094588862j],
                        [9.831019270939975e-01 + 0.1830590094588862j, 0],
                    ]
                ),
                qml.Rot,
                [-0.18409714468526372, np.pi, 0.18409714468526372],
            ),
            (H, qml.Rot, [np.pi, np.pi / 2, 0.0]),
            (X, qml.Rot, [np.pi / 2, np.pi, -np.pi / 2]),
            (qml.matrix(qml.Rot(0.2, 0.5, -0.3, wires=0)), qml.Rot, [0.2, 0.5, -0.3]),
            (
                np.exp(1j * 0.02) * qml.matrix(qml.Rot(-1.0, 2.0, -3.0, wires=0)),
                qml.Rot,
                [-1.0, 2.0, -3.0],
            ),
            # An instance of a broadcast unitary
            (
                np.exp(1j * 0.02)
                * qml.Rot(
                    np.array([1.2, 2.3]), np.array([0.12, 0.5]), np.array([0.98, 0.567]), wires=0
                ).matrix(),
                qml.Rot,
                [[1.2, 2.3], [0.12, 0.5], [0.98, 0.567]],
            ),
        ],
    )
    def test_qubit_unitary_decomposition(self, U, expected_gate, expected_params):
        """Tests that single-qubit QubitUnitary decompositions are performed."""
        decomp = qml.QubitUnitary.compute_decomposition(U, wires=0)
        decomp2 = qml.QubitUnitary(U, wires=0).decomposition()

        assert len(decomp) == 1 == len(decomp2)
        assert isinstance(decomp[0], expected_gate)
        assert np.allclose(decomp[0].parameters, expected_params, atol=1e-7)
        assert isinstance(decomp2[0], expected_gate)
        assert np.allclose(decomp2[0].parameters, expected_params, atol=1e-7)

    def test_broadcasted_two_qubit_qubit_unitary_decomposition_raises_error(self):
        """Tests that broadcasted QubitUnitary decompositions are not supported."""
        U = qml.IsingYY.compute_matrix(np.array([1.2, 2.3, 3.4]))

        with pytest.raises(DecompositionUndefinedError, match="QubitUnitary does not support"):
            qml.QubitUnitary.compute_decomposition(U, wires=[0, 1])
        with pytest.raises(DecompositionUndefinedError, match="QubitUnitary does not support"):
            qml.QubitUnitary(U, wires=[0, 1]).decomposition()

    def test_qubit_unitary_decomposition_multiqubit_invalid(self):
        """Test that QubitUnitary is not decomposed for more than two qubits."""
        U = qml.Toffoli(wires=[0, 1, 2]).matrix()

        with pytest.raises(qml.operation.DecompositionUndefinedError):
            qml.QubitUnitary.compute_decomposition(U, wires=[0, 1, 2])

    def test_matrix_representation(self, tol):
        """Test that the matrix representation is defined correctly"""
        U = np.array(
            [[0.98877108 + 0.0j, 0.0 - 0.14943813j], [0.0 - 0.14943813j, 0.98877108 + 0.0j]]
        )
        res_static = qml.QubitUnitary.compute_matrix(U)
        res_dynamic = qml.QubitUnitary(U, wires=0).matrix()
        expected = U
        assert np.allclose(res_static, expected, atol=tol)
        assert np.allclose(res_dynamic, expected, atol=tol)

    def test_matrix_representation_broadcasted(self, tol):
        """Test that the matrix representation is defined correctly"""
        U = np.array(
            [[0.98877108 + 0.0j, 0.0 - 0.14943813j], [0.0 - 0.14943813j, 0.98877108 + 0.0j]]
        )
        U = np.tensordot([1j, -1.0, (1 + 1j) / np.sqrt(2)], U, axes=0)
        res_static = qml.QubitUnitary.compute_matrix(U)
        res_dynamic = qml.QubitUnitary(U, wires=0).matrix()
        expected = U
        assert np.allclose(res_static, expected, atol=tol)
        assert np.allclose(res_dynamic, expected, atol=tol)

    def test_controlled(self):
        """Test QubitUnitary's controlled method."""
        U = qml.PauliX.compute_matrix()
        base = qml.QubitUnitary(U, wires=0)

        expected = qml.ControlledQubitUnitary(U, control_wires="a", wires=0)

        out = base._controlled("a")
        assert qml.equal(out, expected)


class TestDiagonalQubitUnitary:
    """Test the DiagonalQubitUnitary operation."""

    def test_decomposition(self):
        """Test that DiagonalQubitUnitary falls back to QubitUnitary."""
        D = np.array([1j, 1, 1, -1, -1j, 1j, 1, -1])

        decomp = qml.DiagonalQubitUnitary.compute_decomposition(D, [0, 1, 2])
        decomp2 = qml.DiagonalQubitUnitary(D, wires=[0, 1, 2]).decomposition()

        assert len(decomp) == 1 == len(decomp2)
        assert decomp[0].name == "QubitUnitary" == decomp2[0].name
        assert decomp[0].wires == Wires([0, 1, 2]) == decomp2[0].wires
        assert np.allclose(decomp[0].data[0], np.diag(D))
        assert np.allclose(decomp2[0].data[0], np.diag(D))

    def test_decomposition_broadcasted(self):
        """Test that the broadcasted DiagonalQubitUnitary falls back to QubitUnitary."""
        D = np.outer([1.0, -1.0], [1.0, -1.0, 1j, 1.0])

        decomp = qml.DiagonalQubitUnitary.compute_decomposition(D, [0, 1])
        decomp2 = qml.DiagonalQubitUnitary(D, wires=[0, 1]).decomposition()

        assert len(decomp) == 1 == len(decomp2)
        assert decomp[0].name == "QubitUnitary" == decomp2[0].name
        assert decomp[0].wires == Wires([0, 1]) == decomp2[0].wires

        expected = np.array([np.diag([1.0, -1.0, 1j, 1.0]), np.diag([-1.0, 1.0, -1j, -1.0])])
        assert np.allclose(decomp[0].data[0], expected)
        assert np.allclose(decomp2[0].data[0], expected)

    def test_controlled(self):
        """Test that the correct controlled operation is created when controlling a qml.DiagonalQubitUnitary."""
        D = np.array([1j, 1, 1, -1, -1j, 1j, 1, -1])
        op = qml.DiagonalQubitUnitary(D, wires=[1, 2, 3])
        with qml.queuing.AnnotatedQueue() as q:
            op._controlled(control=0)
        tape = qml.tape.QuantumScript.from_queue(q)
        mat = qml.matrix(tape)
        assert qml.math.allclose(
            mat, qml.math.diag(qml.math.append(qml.math.ones(8, dtype=complex), D))
        )

    def test_controlled_broadcasted(self):
        """Test that the correct controlled operation is created when
        controlling a qml.DiagonalQubitUnitary with a broadcasted diagonal."""
        D = np.array([[1j, 1, -1j, 1], [1, -1, 1j, -1]])
        op = qml.DiagonalQubitUnitary(D, wires=[1, 2])
        with qml.queuing.AnnotatedQueue() as q:
            op._controlled(control=0)
        tape = qml.tape.QuantumScript.from_queue(q)
        mat = qml.matrix(tape)
        expected = np.array(
            [np.diag([1, 1, 1, 1, 1j, 1, -1j, 1]), np.diag([1, 1, 1, 1, 1, -1, 1j, -1])]
        )
        assert qml.math.allclose(mat, expected)

    def test_matrix_representation(self, tol):
        """Test that the matrix representation is defined correctly"""
        diag = np.array([1, -1])
        res_static = qml.DiagonalQubitUnitary.compute_matrix(diag)
        res_dynamic = qml.DiagonalQubitUnitary(diag, wires=0).matrix()
        expected = np.array([[1, 0], [0, -1]])
        assert np.allclose(res_static, expected, atol=tol)
        assert np.allclose(res_dynamic, expected, atol=tol)

    def test_matrix_representation_broadcasted(self, tol):
        """Test that the matrix representation is defined correctly for a broadcasted diagonal."""
        diag = np.array([[1, -1], [1j, -1], [-1j, -1]])
        res_static = qml.DiagonalQubitUnitary.compute_matrix(diag)
        res_dynamic = qml.DiagonalQubitUnitary(diag, wires=0).matrix()
        expected = np.array([[[1, 0], [0, -1]], [[1j, 0], [0, -1]], [[-1j, 0], [0, -1]]])
        assert np.allclose(res_static, expected, atol=tol)
        assert np.allclose(res_dynamic, expected, atol=tol)

    @pytest.mark.parametrize("n", (2, -1, 0.12345))
    @pytest.mark.parametrize("diag", ([1.0, -1.0], np.array([1.0, -1.0])))
    def test_pow(self, n, diag):
        """Test pow method returns expected results."""
        op = qml.DiagonalQubitUnitary(diag, wires="b")
        pow_ops = op.pow(n)
        assert len(pow_ops) == 1

        for x_op, x_pow in zip(op.data[0], pow_ops[0].data[0]):
            assert (x_op + 0.0j) ** n == x_pow

    @pytest.mark.parametrize("n", (2, -1, 0.12345))
    @pytest.mark.parametrize(
        "diag", ([[1.0, -1.0]] * 5, np.array([[1.0, -1j], [1j, 1j], [-1j, 1]]))
    )
    def test_pow_broadcasted(self, n, diag):
        """Test pow method returns expected results for broadcasted diagonals."""
        op = qml.DiagonalQubitUnitary(diag, wires="b")
        pow_ops = op.pow(n)
        assert len(pow_ops) == 1

        qml.math.allclose(np.array(op.data[0], dtype=complex) ** n, pow_ops[0].data[0])

    @pytest.mark.parametrize("D", [[1, 2], [[0.2, 1.0, -1.0], [1.0, -1j, 1j]]])
    def test_error_matrix_not_unitary(self, D):
        """Tests that error is raised if diagonal by `compute_matrix` does not lead to a unitary"""
        with pytest.raises(ValueError, match="Operator must be unitary"):
            qml.DiagonalQubitUnitary.compute_matrix(np.array(D))
        with pytest.raises(ValueError, match="Operator must be unitary"):
            qml.DiagonalQubitUnitary(np.array(D), wires=1).matrix()

    @pytest.mark.parametrize("D", [[1, 2], [[0.2, 1.0, -1.0], [1.0, -1j, 1j]]])
    def test_error_eigvals_not_unitary(self, D):
        """Tests that error is raised if diagonal by `compute_matrix` does not lead to a unitary"""
        with pytest.raises(ValueError, match="Operator must be unitary"):
            qml.DiagonalQubitUnitary.compute_eigvals(np.array(D))
        with pytest.raises(ValueError, match="Operator must be unitary"):
            qml.DiagonalQubitUnitary(np.array(D), wires=0).eigvals()

    @pytest.mark.jax
    def test_jax_jit(self):
        """Test that the diagonal matrix unitary operation works
        within a QNode that uses the JAX JIT"""
        import jax

        jnp = jax.numpy

        dev = qml.device("default.qubit", wires=1, shots=None)

        @jax.jit
        @qml.qnode(dev, interface="jax")
        def circuit(x):
            diag = jnp.exp(1j * x * jnp.array([1, -1]) / 2)
            qml.Hadamard(wires=0)
            qml.DiagonalQubitUnitary(diag, wires=0)
            return qml.expval(qml.PauliX(0))

        x = 0.654
        grad = jax.grad(circuit)(x)
        expected = -jnp.sin(x)
        assert np.allclose(grad, expected)

    @pytest.mark.jax
    def test_jax_jit_broadcasted(self):
        """Test that the diagonal matrix unitary operation works
        within a QNode that uses the JAX JIT and broadcasting"""
        import jax

        jnp = jax.numpy

        dev = qml.device("default.qubit", wires=1, shots=None)

        @jax.jit
        @qml.qnode(dev, interface="jax")
        def circuit(x):
            diag = jnp.exp(1j * jnp.outer(x, jnp.array([1, -1])) / 2)
            qml.Hadamard(wires=0)
            qml.DiagonalQubitUnitary(diag, wires=0)
            return qml.expval(qml.PauliX(0))

        x = jnp.array([0.654, 0.321])
        jac = jax.jacobian(circuit)(x)
        expected = jnp.diag(-jnp.sin(x))
        assert np.allclose(jac, expected)

    @pytest.mark.tf
    @pytest.mark.slow  # test takes 12 seconds due to tf.function
    def test_tf_function(self):
        """Test that the diagonal matrix unitary operation works
        within a QNode that uses TensorFlow autograph"""
        import tensorflow as tf

        dev = qml.device("default.qubit", wires=1, shots=None)

        @tf.function
        @qml.qnode(dev, interface="tf")
        def circuit(x):
            x = tf.cast(x, tf.complex128)
            diag = tf.math.exp(1j * x * tf.constant([1.0 + 0j, -1.0 + 0j]) / 2)
            qml.Hadamard(wires=0)
            qml.DiagonalQubitUnitary(diag, wires=0)
            return qml.expval(qml.PauliX(0))

        x = tf.Variable(0.452)

        with tf.GradientTape() as tape:
            loss = circuit(x)

        grad = tape.gradient(loss, x)
        expected = -tf.math.sin(x)
        assert np.allclose(grad, expected)


theta_1 = np.array([0.4, 0.1, 0.1])
theta_2 = np.array([0.4, 0.1, 0.1, 0.6, 0.2, 0.3, 0.1, 0.2, 0, 0.2, 0.2, 0.2, 0.1, 0.5, 0.2])
theta_3 = np.ones(63)
n_and_theta = [(1, theta_1), (2, theta_2), (3, theta_3)]


class TestSpecialUnitary:
    """Tests for the Operation ``SpecialUnitary``."""

    @pytest.mark.parametrize("n, theta", n_and_theta)
    def test_decomposition(self, n, theta):
        """Test that SpecialUnitary falls back to QubitUnitary."""

        wires = list(range(n))
        decomp = qml.SpecialUnitary.compute_decomposition(theta, wires, n)
        decomp2 = qml.SpecialUnitary(theta, wires).decomposition()

        assert len(decomp) == 1 == len(decomp2)
        assert decomp[0].name == "QubitUnitary" == decomp2[0].name
        assert decomp[0].wires == Wires(wires) == decomp2[0].wires
        mat = special_unitary_matrix(theta, n)
        assert np.allclose(decomp[0].data[0], mat)
        assert np.allclose(decomp2[0].data[0], mat)

    @pytest.mark.parametrize("n, theta", n_and_theta)
    def test_decomposition_broadcasted(self, n, theta):
        """Test that the broadcasted SpecialUnitary falls back to QubitUnitary."""
        theta = np.outer([0.2, 1.0, -0.3], theta)
        wires = list(range(n))

        decomp = qml.SpecialUnitary.compute_decomposition(theta, wires, n)
        decomp2 = qml.SpecialUnitary(theta, wires).decomposition()

        assert len(decomp) == 1 == len(decomp2)
        assert decomp[0].name == "QubitUnitary" == decomp2[0].name
        assert decomp[0].wires == Wires(wires) == decomp2[0].wires

        mat = special_unitary_matrix(theta, n)
        assert np.allclose(decomp[0].data[0], mat)
        assert np.allclose(decomp2[0].data[0], mat)

    @pytest.mark.parametrize("n, theta", n_and_theta)
    def test_matrix_representation(self, n, theta, tol):
        """Test that the matrix representation is defined correctly"""
        wires = list(range(n))
        res_static = qml.SpecialUnitary.compute_matrix(theta, n)
        res_dynamic = qml.SpecialUnitary(theta, wires).matrix()
        expected = special_unitary_matrix(theta, n)
        assert np.allclose(res_static, expected, atol=tol)
        assert np.allclose(res_dynamic, expected, atol=tol)

    @pytest.mark.parametrize("n, theta", n_and_theta)
    def test_matrix_representation_broadcasted(self, n, theta, tol):
        """Test that the matrix representation is defined correctly for
        a broadcasted SpecialUnitary."""
        theta = np.outer([0.2, 1.0, -0.3], theta)
        wires = list(range(n))
        res_static = qml.SpecialUnitary.compute_matrix(theta, n)
        res_dynamic = qml.SpecialUnitary(theta, wires).matrix()
        expected = special_unitary_matrix(theta, n)
        assert np.allclose(res_static, expected, atol=tol)
        assert np.allclose(res_dynamic, expected, atol=tol)

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_matrix_unitarity(self, n):
        wires = list(range(n))
        d = 4**n - 1
        theta = np.random.random(d)
        U = qml.SpecialUnitary(theta, wires).matrix()
        assert qml.math.allclose(U.conj().T @ U, np.eye(2**n))

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_matrix_PauliRot(self, n):
        wires = list(range(n))
        d = 4**n - 1
        words = pauli_words(n)
        prefactors = np.random.random(d)
        thetas = prefactors * np.eye(d)
        for theta, pref, word in zip(thetas, prefactors, words):
            U = qml.SpecialUnitary(theta, wires)
            rot = qml.PauliRot(-2 * pref, word, wires)
            assert qml.math.allclose(U.matrix(), rot.matrix())

    @pytest.mark.parametrize("batch_size", [1, 3])
    @pytest.mark.parametrize("n, theta", n_and_theta)
    def test_matrix_broadcasting(self, theta, n, batch_size):
        wires = list(range(n))
        d = 4**n - 1
        theta = np.outer(np.arange(batch_size), theta)
        U = qml.SpecialUnitary(theta, wires).matrix()
        assert all(qml.math.allclose(_U, special_unitary_matrix(_t, n)) for _U, _t in zip(U, theta))

    @pytest.mark.parametrize("n, theta", n_and_theta)
    def test_adjoint(self, theta, n):
        wires = list(range(n))
        U = qml.SpecialUnitary(theta, wires)
        U_dagger = qml.adjoint(qml.SpecialUnitary)(theta, wires)
        U_dagger_inplace = qml.SpecialUnitary(theta, wires).adjoint()
        U_minustheta = qml.SpecialUnitary(-theta, wires)
        assert qml.math.allclose(U.matrix(), U_dagger.matrix().conj().T)
        assert qml.math.allclose(U.matrix(), U_dagger_inplace.matrix().conj().T)
        assert qml.math.allclose(U_minustheta.matrix(), U_dagger.matrix())

    @pytest.mark.parametrize(
        "theta, n", [(np.ones(4), 1), (9.421, 2), (np.ones((5, 2, 1)), 1), (np.ones((5, 16)), 2)]
    )
    def test_wrong_input_shape(self, theta, n):
        wires = list(range(n))
        with pytest.raises(ValueError, match="Expected the parameters to have"):
            U = qml.SpecialUnitary(theta, wires)

    @pytest.mark.jax
    def test_jax_jit(self):
        """Test that the SpecialUnitary operation works
        within a QNode that uses the JAX JIT"""
        import jax

        jax.config.update("jax_enable_x64", True)
        jnp = jax.numpy

        dev = qml.device("default.qubit", wires=1, shots=None)

        theta = jnp.array(theta_1)

        @jax.jit
        @qml.qnode(dev, interface="jax")
        def circuit(x):
            qml.SpecialUnitary(x, 0)
            return qml.probs(wires=[0])

        def comparison(x):
            state = special_unitary_matrix(x, 1) @ jnp.array([1, 0])
            return jnp.abs(state) ** 2

        jac = jax.jacobian(circuit)(theta)
        expected_jac = jax.jacobian(comparison)(theta)
        assert np.allclose(jac, expected_jac)

    # The JAX version of scipy.linalg.expm does not support broadcasting.
    @pytest.mark.xfail
    @pytest.mark.jax
    def test_jax_jit_broadcasted(self):
        """Test that the SpecialUnitary operation works
        within a QNode that uses the JAX JIT and broadcasting."""
        import jax

        jax.config.update("jax_enable_x64", True)
        jnp = jax.numpy

        dev = qml.device("default.qubit", wires=1, shots=None)

        theta = jnp.outer(jnp.array([-0.4, 0.1, 1.0]), theta_1)

        @jax.jit
        @qml.qnode(dev, interface="jax")
        def circuit(x):
            qml.SpecialUnitary(x, 0)
            return qml.probs(wires=[0])

        def comparison(x):
            state = special_unitary_matrix(x, 1) @ jnp.array([1, 0])
            return jnp.abs(state) ** 2

        jac = jax.jacobian(circuit)(theta)
        expected_jac = jax.jacobian(comparison)(theta)
        assert np.allclose(jac, expected_jac)

    @pytest.mark.tf
    @pytest.mark.slow
    def test_tf_function(self):
        """Test that the SpecialUnitary operation works
        within a QNode that uses TensorFlow autograph"""
        import tensorflow as tf

        dev = qml.device("default.qubit", wires=1, shots=None)

        @tf.function
        @qml.qnode(dev, interface="tf")
        def circuit(x):
            qml.SpecialUnitary(x, 0)
            return qml.expval(qml.PauliX(0))

        theta = tf.Variable(theta_1)

        with tf.GradientTape() as tape:
            loss = circuit(theta)

        jac = tape.jacobian(loss, theta)

        def comparison(x):
            state = qml.math.tensordot(
                special_unitary_matrix(x, 1),
                tf.constant([1, 0], dtype=tf.complex128),
                axes=[[1], [0]],
            )
            return qml.math.tensordot(
                qml.math.conj(state),
                qml.math.tensordot(qml.PauliX(0).matrix(), state, axes=[[1], [0]]),
                axes=[[0], [0]],
            )

        with tf.GradientTape() as tape:
            loss = comparison(theta)

        expected = tape.jacobian(loss, theta)
        assert np.allclose(jac, expected)


label_data = [
    (X, qml.QubitUnitary(X, wires=0)),
    (X, qml.ControlledQubitUnitary(X, control_wires=0, wires=1)),
    ([1, 1], qml.DiagonalQubitUnitary([1, 1], wires=0)),
]


@pytest.mark.parametrize("mat, op", label_data)
class TestUnitaryLabels:
    def test_no_cache(self, mat, op):
        """Test labels work without a provided cache."""
        assert op.label() == "U"

    def test_matrices_not_in_cache(self, mat, op):
        """Test provided cache doesn't have a 'matrices' keyword."""
        assert op.label(cache={}) == "U"

    def test_cache_matrices_not_list(self, mat, op):
        """Test 'matrices' key pair is not a list."""
        assert op.label(cache={"matrices": 0}) == "U"

    def test_empty_cache_list(self, mat, op):
        """Test matrices list is provided, but empty. Operation should have `0` label and matrix
        should be added to cache."""
        cache = {"matrices": []}
        assert op.label(cache=cache) == "U(M0)"
        assert qml.math.allclose(cache["matrices"][0], mat)

    def test_something_in_cache_list(self, mat, op):
        """If something exists in the matrix list, but parameter is not in the list, then parameter
        added to list and label given number of its position."""
        cache = {"matrices": [Z]}
        assert op.label(cache=cache) == "U(M1)"

        assert len(cache["matrices"]) == 2
        assert qml.math.allclose(cache["matrices"][1], mat)

    def test_matrix_already_in_cache_list(self, mat, op):
        """If the parameter already exists in the matrix cache, then the label uses that index and the
        matrix cache is unchanged."""
        cache = {"matrices": [Z, mat, S]}
        assert op.label(cache=cache) == "U(M1)"

        assert len(cache["matrices"]) == 3


class TestInterfaceMatricesLabel:
    """Test different interface matrices with qubit."""

    def check_interface(self, mat):
        """Interface independent helper method."""

        op = qml.QubitUnitary(mat, wires=0)

        cache = {"matrices": []}
        assert op.label(cache=cache) == "U(M0)"
        assert qml.math.allclose(cache["matrices"][0], mat)

        cache = {"matrices": [0, mat, 0]}
        assert op.label(cache=cache) == "U(M1)"
        assert len(cache["matrices"]) == 3

    @pytest.mark.torch
    def test_labelling_torch_tensor(self):
        """Test matrix cache labelling with torch interface."""

        import torch

        mat = torch.tensor([[1, 0], [0, -1]])
        self.check_interface(mat)

    @pytest.mark.tf
    def test_labelling_tf_variable(self):
        """Test matrix cache labelling with tf interface."""

        import tensorflow as tf

        mat = tf.Variable([[1, 0], [0, -1]])

        self.check_interface(mat)

    @pytest.mark.jax
    def test_labelling_jax_variable(self):
        """Test matrix cache labelling with jax interface."""

        import jax.numpy as jnp

        mat = jnp.array([[1, 0], [0, -1]])

        self.check_interface(mat)


control_data = [
    (qml.QubitUnitary(X, wires=0), Wires([])),
    (qml.DiagonalQubitUnitary([1, 1], wires=1), Wires([])),
    (qml.ControlledQubitUnitary(X, control_wires=0, wires=1), Wires([0])),
]


@pytest.mark.parametrize("op, control_wires", control_data)
def test_control_wires(op, control_wires):
    """Test ``control_wires`` attribute for matrix operations."""
    assert op.control_wires == control_wires
