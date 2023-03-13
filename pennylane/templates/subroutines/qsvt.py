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
Contains the QSVT template and qsvt wrapper function.
"""
import numpy as np
from pennylane.ops.op_math import adjoint
from pennylane.operation import AnyWires, Operation
from pennylane import BlockEncode, PCPhase

def qsvt(A, phi_vect, wires):
    """Executes the operations to perform the qsvt protocol"""
    d = len(phi_vect)
    c, r = A.shape
    phi_vect = np.flip(phi_vect)

    lst_operations = []

    if d % 2 == 0:
        for i in range(1, d//2 + 1):
            lst_operations.append(BlockEncode(A, wires=wires))
            lst_operations.append(PCPhase(phi_vect[2 * i - 1], r, wires=wires))
            lst_operations.append(adjoint(BlockEncode(A, wires=wires)))
            lst_operations.append(PCPhase(phi_vect[2*i - 2], c, wires=wires))

    else:
        for i in range(1, (d-1) // 2 + 1):
            lst_operations.append(BlockEncode(A, wires=wires))
            lst_operations.append(PCPhase(phi_vect[2 * i], r, wires=wires))
            lst_operations.append(adjoint(BlockEncode(A, wires=wires)))
            lst_operations.append(PCPhase(phi_vect[2*i - 1], c, wires=wires))

        lst_operations.append(BlockEncode(A, wires=wires))
        lst_operations.append(PCPhase(phi_vect[0], r, wires=wires))

class QSVT(Operation):
    r"""Performs the 
    `quantum singular value transformation <https://arxiv.org/abs/1806.01838>`__ circuit.

    Given a circuit :math:`U(A)`, which block encodes the matrix :math:`A`, and a list of projector-controlled
    phase shifts, this template applies the circuit for quantum singular value transformation.

    .. math::

        \begin{align}
             U_{qsvt}(A, \phi) &=
             \begin{bmatrix}
                Poly^{SV}(A) & \cdot \\
                \cdot & \cdot
            \end{bmatrix}.
        \end{align}

    This circuit can be used to perform the standard quantum singular value transformation algorithm, consisting
    of alternating block encoding and controlled phase shift operations.

    Args:
        U_A (Operator or Callable): the block encoding circuit, specified as a :class:`~.Operator` 
            or quantum function.
        lst_projectors (list[Operator] or list[Callable]): a list of projector-controlled phase
            shifts that implement the desired polynomial.
        wires (Iterable): the wires the template acts on.

    Raises:
        QuantumFunctionError: if the ``target_wires`` and ``estimation_wires`` share a common
            element, or if ``target_wires`` are specified for an operator unitary.

    .. details::
        :title: Usage Details

        Consider the matrix corresponding to a rotation from an :class:`~.RX` gate:

        .. code-block:: python

            import pennylane as qml
            
        Continue any explanation here.
    """

    num_params = 2
    """int: Number of trainable parameters that the operator depends on."""

    num_wires = AnyWires
    """int: Number of wires that the operator acts on."""

    ndim_params = (0, 2,)
    """tuple[int]: Number of dimensions per trainable parameter that the operator depends on."""

    grad_method = None
    """Gradient computation method."""
    
    def __init__(self, U_A, lst_projectors, wires, do_queue=True, id=None):
        super().__init__(U_A, lst_projectors, wires=wires, do_queue=do_queue, id=id)

    @staticmethod
    def compute_decomposition(self, U_A, lst_projectors, wires):
        r"""Representation of the operator as a product of other operators.

        .. math:: O = O_1 O_2 \dots O_n.


        .. seealso:: :meth:`~.QSVT.decomposition`.

        Args:
            U_A (Operator or Callable): the block encoding circuit, specified as a :class:`~.Operator` 
                or quantum function.
            lst_projectors (list[Operator] or list[Callable]): a list of projector-controlled phase
                shift circuits that implement the desired polynomial.
            wires (Iterable): wires that the template acts on

        Returns:
            list[.Operator]: decomposition of the operator
        """

        op_list = []
        #check 
        #different if len(lst_projectrs) is odd or even:

        if len(lst_projectors)%2 ==0:
            for idx, op in enumerate(lst_projectors):
                if idx%2 == 0:
                    op_list.append(U_A)
                else:
                    op_list.append(adjoint(U_A))
                op_list.append(op)

        else:
            for idx, op in enumerate(lst_projectors[:-1]):
                if idx%2 == 0:
                    op_list.append(U_A)
                else:
                    op_list.append(adjoint(U_A))
                op_list.append(op)

            op_list.append(U_A)
            op_list.append(lst_projectors[-1])


        return op_list

