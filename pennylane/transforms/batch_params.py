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
Contains the batch dimension transform.
"""
# pylint: disable=import-outside-toplevel
import pennylane as qml


from .batch_transform import batch_transform


def _nested_stack(res):
    """
    Given a list of identical nested tuple structures, stack the arrays at the leaves
    """
    # for some reason pylint thinks qml.numpy.builtins is a dict
    # pylint: disable=no-member
    if not isinstance(res[0], (tuple, qml.numpy.builtins.SequenceBox)):
        return qml.math.stack(res)

    stacked_results = []
    for i in range(len(res[0])):
        stacked_results.append(_nested_stack([r[i] for r in res]))

    return tuple(stacked_results)


@batch_transform
def batch_params(tape, all_operations=False):
    """Transform a QNode to support an initial batch dimension
    for operation parameters.

    .. note::

        This transform will create multiple circuits inside the QNode, one per batch dimension.
        As a result, it is both simulator and hardware compatible. When using
        a simulator device, however, this means that a separate simulation
        will be performed per batch dimension.

    .. warning::

        Currently, not all templates have been updated to support a batch
        dimension. If you run into an error attempting to use a template
        with this transform, please open a GitHub issue detailing
        the error.

    Args:
        qnode (pennylane.QNode or .QuantumTape): quantum tape or QNode to add a batch dimension to
        all_operations (bool): If ``True``, a batch dimension will be added to *all* operations
            in the QNode, rather than just trainable QNode parameters.

    Returns:
        func: Function which accepts the same arguments as the QNode, however the
        first dimension of each argument will be treated as a batch dimension.
        The function output will also contain an initial batch dimension.

    **Example**

    Consider the following circuit:

    .. code-block:: python

        dev = qml.device("default.qubit", wires=3)

        @qml.batch_params
        @qml.qnode(dev)
        def circuit(x, weights):
            qml.RX(x, wires=0)
            qml.RY(0.2, wires=1)
            qml.templates.StronglyEntanglingLayers(weights, wires=[0, 1, 2])
            return qml.expval(qml.Hadamard(0))

    The ``qml.batch_params`` decorator allows us to pass arguments ``x`` and ``weights``
    that have a batch dimension. For example,

    >>> batch_size = 3
    >>> x = np.linspace(0.1, 0.5, batch_size)
    >>> rng = np.random.default_rng(seed=1234)
    >>> weights = rng.random((batch_size, 10, 3, 3), requires_grad=True)

    If we evaluate the QNode with these inputs, we will get an output
    of shape ``(batch_size,)``:

    >>> circuit(x, weights)
    tensor([ 0.00800498,  0.2735391 , -0.24395442], requires_grad=True)

    QNodes with a batch dimension remain fully differentiable:

    >>> cost_fn = lambda x, weights: np.sum(circuit(x, weights))
    >>> cost_fn(x, weights)
    tensor(0.03758966, requires_grad=True)
    >>> qml.grad(cost_fn)(x, weights)[0]
    array([-0.30262974,  0.06320878,  0.00811555])

    If we pass the ``all_operations`` argument, we can specify that
    *all* operation parameters in the transformed QNode, regardless of whether they
    are QNode input parameters, have a batch dimension:

    .. code-block:: python

        @qml.batch_params(all_operations=True)
        @qml.qnode(dev)
        def circuit(x, weights):
            qml.RX(x, wires=0)
            qml.RY([0.2, 0.2, 0.2], wires=1)
            qml.templates.StronglyEntanglingLayers(weights, wires=[0, 1, 2])
            return qml.expval(qml.Hadamard(0))

    >>> cost_fn = lambda x, weights: np.sum(circuit(x, weights))
    >>> weights.requires_grad = False
    >>> cost_fn(x, weights)
    tensor(0.03758966, requires_grad=True)
    >>> qml.grad(cost_fn)(x, weights)[0]
    -0.30262974103192636
    """
    # pylint: disable=too-many-branches, no-member

    params = tape.get_parameters(trainable_only=False)
    indices = list(range(len(params))) if all_operations else list(tape.trainable_params)

    if not indices:
        raise ValueError(
            "There are no operations to transform. Either add trainable parameters, "
            "or specify `all_operations=True`."
        )

    try:
        batch_dim = qml.math.shape(params[indices[0]])[0]
    except IndexError:
        raise ValueError(f"Parameter {params[0]} does not contain a batch dimension.") from None

    for i in indices:
        shape = qml.math.shape(params[i])
        if len(shape) == 0 or shape[0] != batch_dim:
            raise ValueError(
                f"Parameter {params[i]} has incorrect batch dimension. Expecting "
                f"first dimension of length {batch_dim}."
            )

    new_preps = [[] for _ in range(batch_dim)]
    new_ops = [[] for _ in range(batch_dim)]

    idx = 0
    for prep in tape.prep:
        # determine if any parameters of the operator are batched
        if any(i in indices for i in range(idx, idx + len(prep.data))):
            for b in range(batch_dim):
                new_params = tuple(
                    params[i][b] if i in indices else params[i]
                    for i in range(idx, idx + len(prep.data))
                )
                new_prep = qml.ops.functions.bind_new_parameters(prep, new_params)
                new_preps[b].append(new_prep)
        else:
            # no batching in the operator; don't copy
            for b in range(batch_dim):
                new_preps[b].append(prep)

        idx += len(prep.data)

    ops = [op for op in tape.operations if op not in tape.prep]
    for op in ops:
        # determine if any parameters of the operator are batched
        if any(i in indices for i in range(idx, idx + len(op.data))):
            for b in range(batch_dim):
                new_params = tuple(
                    params[i][b] if i in indices else params[i]
                    for i in range(idx, idx + len(op.data))
                )
                new_op = qml.ops.functions.bind_new_parameters(op, new_params)
                new_ops[b].append(new_op)
        else:
            # no batching in the operator; don't copy
            for b in range(batch_dim):
                new_ops[b].append(op)

        idx += len(op.data)

    output_tapes = []
    for prep, ops in zip(new_preps, new_ops):
        new_tape = qml.tape.QuantumScript(ops, tape.measurements, prep, shots=tape.shots)
        new_tape.trainable_params = tape.trainable_params
        output_tapes.append(new_tape)

    def processing_fn(res):
        if qml.active_return():
            return _nested_stack(res)

        return qml.math.squeeze(qml.math.stack(res))

    return output_tapes, processing_fn
