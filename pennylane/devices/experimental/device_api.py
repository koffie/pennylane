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
This module contains the Abstract Base Class for the next generation of devices.
"""
# pylint: disable=comparison-with-callable
import abc

from numbers import Number
from typing import Callable, Union, Sequence, Tuple, Optional

from pennylane.tape import QuantumTape, QuantumScript
from pennylane.typing import Result, ResultBatch
from pennylane import Tracker

from .execution_config import ExecutionConfig, DefaultExecutionConfig

Result_or_ResultBatch = Union[Result, ResultBatch]
QuantumTapeBatch = Sequence[QuantumTape]
QuantumTape_or_Batch = Union[QuantumTape, QuantumTapeBatch]
PostprocessingFn = Callable[[ResultBatch], Result_or_ResultBatch]


# pylint: disable=unused-argument, no-self-use
class Device(abc.ABC):
    """A device driver that can control one or more backends. A backend can be either a physical
    Quantum Processing Unit or a virtual one such as a simulator.

    .. warning::

        This interface is **experimental** and not yet integrated with the rest of PennyLane.

    Device drivers should be configured to run under :func:`~.enable_return`, the newer
    return shape specification.

    Only the ``execute`` method must be defined to construct a device driver.

    .. details::
        :title: Design Motivation

        **Streamlined interface:** Only methods that are required to interact with the rest of PennyLane will be placed in the
        interface. Developers will be able to clearly see what they can change while still having a fully functional device.

        **Reduction of duplicate methods:** Methods that solve similar problems are combined together. Only one place will have
        to solve each individual problem.

        **Support for dynamic execution configurations:** Properties such as shots belong to specific executions.

        **Greater coverage for differentiation methods:** Devices can define any order of derivative, the vector jacobian product,
        or the jacobian vector product.  Calculation of derivatives can be done at the same time as execution to allow reuse of intermediate
        results.

    .. details::
        :title: Porting from the old interface

        :meth:`pennylane.Device.batch_execute` and :meth:`~pennylane.Device.execute` are now a single method, :meth:`~.Device.execute`

        :meth:`~.Device.batch_transform` and :meth:`~.Device.expand_fn` are now a single method, :meth:`~.Device.preprocess`

        Shot information is no longer stored on the device, but instead specified on individual input :class:`~.QuantumTape`.

        The old devices defined a :meth:`~.Device.capabilities` dictionary that defined characteristics of the devices and controlled various
        preprocessing and validation steps, such as ``"supports_broadcasting"``.  These capabilites should now be handled by the
        :meth:`~.Device.preprocess` method. For example, if a device does not support broadcasting, ``preprocess`` should
        split a quantum script with broadcasted parameters into a batch of quantum scripts. If the device does not support mid circuit
        measurements, then ``preprocess`` should apply :func:`~.defer_measurements`.  A set of default preprocessing steps will be available
        to make a seamless transition to the new interface.

        A class will be provided to easily construct default preprocessing steps from supported operations, supported observables,
        supported measurement processes, and various capabilities.

        Utility functions will be added to the ``devices`` module to query whether or not the device driver can do certain things, such
        as ``devices.supports_operator(op, dev, native=True)``. These functions will work by checking the behaviour of :meth:`~.Device.preprocess`
        to certain inputs.

        Versioning should be specified by the package containing the device. If an external package includes a PennyLane device,
        then the package requirements should specify the minimium PennyLane version required to work with the device.


    .. details::
        :title: Execution Configuration

        Execution config properties related to configuring a device include:

        * ``device_options``: A dictionary of device specific options. For example, the python device may have ``multiprocessing_mode``
          as a key. These should be documented in the class docstring.

        * ``gradient_method``: A device can choose to have native support for any type of gradient method. If the method
          :meth:`~.supports_derivatives` returns ``True`` for a particular gradient method, it will be treated as a device
          derivative and not handled by pennylane core code.

        * ``gradient_keyword_arguments``: Options for the gradient method.

        * ``derivative_order``: Relevant for requested device derivatives.

    """

    @property
    def name(self) -> str:
        """The name of the device or set of devices.

        This property can either be the name of the class, or an alias to be used in the :func:`~.device` constructor,
        such as ``"default.qubit"`` or ``"lightning.qubit"``.

        """
        return type(self).__name__

    tracker: Tracker = Tracker()
    """A :class:`~.Tracker` that can store information about device executions, shots, batches,
    intermediate results, or any additional device dependent information.

    A plugin developer can store information in the tracker by:

    .. code-block:: python

        # querying if the tracker is active
        if self.tracker.active:

            # store any keyword: value pairs of information
            self.tracker.update(executions=1, shots=self._shots, results=results)

            # Calling a user-provided callback function
            self.tracker.record()
    """

    def __init__(self) -> None:
        # each instance should have its own Tracker.
        self.tracker = Tracker()

    def preprocess(
        self,
        circuits: QuantumTape_or_Batch,
        execution_config: ExecutionConfig = DefaultExecutionConfig,
    ) -> Tuple[QuantumTapeBatch, PostprocessingFn]:
        """Device preprocessing function.

        .. warning::

            This function is tracked by machine learning interfaces and should be fully differentiable.
            The ``pennylane.math`` module can be used to construct fully differntiable transformations.

            Additional preprocessing independent of machine learning interfaces can be done inside of
            the :meth:`~.execute` metod.

        Args:
            circuits (Union[QuantumTape, Sequence[QuantumTape]]): The circuit or a batch of circuits to preprocess
                before execution on the device
            execution_config (ExecutionConfig): A datastructure describing the parameters needed to fully describe
                the execution.

            Tuple[QuantumTape], Callable, ExecutionConfig: QuantumTapes that the device can natively execute,
            a postprocessing function to be called after execution, and a configuration with unset specifications filled in.

        Raises:
            Exception: An exception is raised if the input cannot be converted into a form supported by the device.

        Preprocessing steps may include:

        * expansion to :class:`~.Operator`'s and :class:`~.MeasurementProcess` objects supported by the device.
        * splitting a circuit with the measurement of non-commuting observables or Hamiltonians into multiple executions
        * splitting circuits with batched parameters into multiple executions
        * gradient specific preprocessing, such as making sure trainable operators have generators
        * validation of configuration parameters
        * choosing a best gradient method and ``grad_on_execution`` value.

        """

        def blank_postprocessing_fn(res: ResultBatch) -> ResultBatch:
            """Identity postprocessing function created in Device preprocessing.

            Args:
                res (tensor-like): A result object

            Returns:
                tensor-like: The function input.

            """
            return res

        circuit_batch = (circuits,) if isinstance(circuits, QuantumScript) else circuits
        return circuit_batch, blank_postprocessing_fn

    def setup_configuration(
        self,
        circuits: QuantumTape_or_Batch,
        execution_config: ExecutionConfig = DefaultExecutionConfig,
    ) -> ExecutionConfig:
        return execution_config

    @abc.abstractmethod
    def execute(
        self,
        circuits: QuantumTape_or_Batch,
        execution_config: ExecutionConfig = DefaultExecutionConfig,
    ) -> Result_or_ResultBatch:
        """Execute a circuit or a batch of circuits and turn it into results.

        Args:
            circuits (Union[QuantumTape, Sequence[QuantumTape]]): the quantum circuits to be executed
            execution_config (ExecutionConfig): a datastructure with additional information required for execution

        Returns:
            TensorLike, tuple[TensorLike], tuple[tuple[TensorLike]]: A numeric result of the computation.

        **Interface parameters:**

        Note that the parameters contained within the quantum script may contain interface-specific data types, such as
        ``torch.Tensor`` or ``jax.Array``. If the device does not wish to handle interface-specific parameters, they
        can implement an optional "internal preprocessing" step that converts all parameters to vanilla numpy. A convenience
        transform implementing this will be provided. This step allows device to be transparent to things like jitting if they
        so choose.

        .. details::
            :title: Return Shape

            The result for each :class:`~.QuantumTape` must match the shape specified by :class:`~.QuantumTape.shape`.

            The level of priority for dimensions from outer dimension to inner dimension is:

            1. Quantum Script in batch
            2. Shot choice in a shot vector
            3. Measurement in the quantum script
            4. Parameter broadcasting
            5. Measurement shape for array-valued measurements like probabilities

            For a batch of quantum scripts with multiple measurements, a shot vector, and parameter broadcasting:

            * ``result[0]``: the results for the first script
            * ``result[0][0]``: the first shot number in the shot vector
            * ``result[0][0][0]``: the first measurement in the quantum script
            * ``result[0][0][0][0]``: the first parameter broadcasting choice
            * ``result[0][0][0][0][0]``: the first value for an array-valued measurement

            With the exception of quantum script batches, dimensions with only a single component should be eliminated.

            For example:

            With a single script and a single measurement process, execute should return just the
            measurement value in a numpy array. ``shape`` currently accepts a device, as historically devices
            stored shot information. In the future, this method will accept an ``ExecutionConfig`` instead.

            >>> tape = qml.tape.QuantumTape(measurements=qml.expval(qml.PauliZ(0))])
            >>> tape.shape(dev)
            ()
            >>> dev.execute(tape)
            array(1.0)

            If execute recieves a batch of scripts, then it should return a tuple of results:

            >>> dev.execute([tape, tape])
            (array(1.0), array(1.0))
            >>> dev.execute([tape])
            (array(1.0),)

            If the script has multiple measurments, then the device should return a tuple of measurements.

            >>> tape = qml.tape.QuantumTape(measurements=[qml.expval(qml.PauliZ(0)), qml.probs(wires=(0,1))])
            >>> tape.shape(dev)
            ((), (4,))
            >>> dev.execute(tape)
            (array(1.0), array([1., 0., 0., 0.]))

        """
        raise NotImplementedError

    def supports_derivatives(
        self,
        execution_config: Optional[ExecutionConfig] = None,
        circuit: Optional[QuantumTape] = None,
    ) -> bool:
        """Determine whether or not a device provided derivative is potentially available.

        Default behaviour assumes first order device derivatives for all circuits exist if :meth:`~.compute_derivatives` is overriden.

        Args:
            execution_config (ExecutionConfig): A description of the hyperparameters for the desired computation.
            circuit (None, QuantumTape): A specific circuit to check differentation for.

        Returns:
            Bool

        The device can support multiple different types of "device derivatives", chosen via ``execution_config.gradient_method``.
        For example, a device can natively calculate ``"parameter-shift"`` derivatives, in which case :meth:`~.compute_derivatives`
        will be called for the derivative instead of :meth:`~.execute` with a batch of circuits.

        >>> config = ExecutionConfig(gradient_method="parameter-shift")
        >>> custom_device.supports_derivatives(config)
        True

        In this case, :meth:`~.compute_derivatives` or :meth:`~.execute_and_compute_derivatives` will be called instead of :meth:`~.execute` with
        a batch of circuits.

        If ``circuit`` is not provided, then the method should return whether or not device derivatives exist for **any** circuit.

        **Example:**

        For example, the Python device will support device differentiation via the adjoint differentiation algorithm
        if the order is ``1`` and the execution occurs with no shots (``shots=None``).

        >>> config = ExecutionConfig(derivative_order=1, shots=None, gradient_method="adjoint")
        >>> dev.supports_derivatives(config)
        True
        >>> config = ExecutionConfig(derivative_order=1, shots=10, gradient_method="adjoint")
        >>> dev.supports_derivatives(config)
        False
        >>> config = ExecutionConfig(derivative_order=2, shots=None, gradient_method="adjoint")
        >>> dev.supports_derivatives(config)
        False

        Adjoint differentiation will only be supported for circuits with expectation value measurements.
        If a circuit is provided and it cannot be converted to a form supported by differentiation method by
        :meth:`~.Device.preprocess`, then ``supports_derivatives`` should return False.

        >>> config = ExecutionConfig(derivative_order=1, shots=None, gradient_method="adjoint")
        >>> circuit = qml.tape.QuantumScript([qml.RX(2.0, wires=0)], [qml.probs(wires=(0,1))])
        >>> dev.supports_derivatives(config, circuit=circuit)
        False

        If the circuit is not natively supported by the differentiation method but can be converted into a form
        that is supported, it should still return ``True``.  For example, :class:`~.Rot` gates are not natively
        supported by adjoint differentation, as they do not have a generator, but they can be compiled into
        operations supported by adjoint differentiation. Therefore this method may reproduce compilation
        and validation steps performed by :meth:`~.Device.preprocess`.

        >>> config = ExecutionConfig(derivative_order=1, shots=None, gradient_method="adjoint")
        >>> circuit = qml.tape.QuantumScript([qml.Rot(1.2, 2.3, 3.4, wires=0)], [qml.expval(qml.PauliZ(0))])
        >>> dev.supports_derivatives(config, circuit=circuit)
        True

        **Backpropagation:**

        This method is also used be to validate support for backpropagation derivatives. Backpropagation
        is only supported if the device is transparent to the machine learning framework from start to finish.

        >>> config = ExecutionConfig(gradient_method="backprop", framework="torch")
        >>> python_device.supports_derivatives(config)
        True
        >>> cpp_device.supports_derivatives(config)
        False

        """
        if execution_config is None:
            return type(self).compute_derivatives != Device.compute_derivatives

        if execution_config.gradient_method != "device" or execution_config.derivative_order != 1:
            return False

        return type(self).compute_derivatives != Device.compute_derivatives

    def compute_derivatives(
        self,
        circuits: QuantumTape_or_Batch,
        execution_config: ExecutionConfig = DefaultExecutionConfig,
    ):
        """Calculate the jacobian of either a single or a batch of circuits on the device.

        Args:
            circuits (Union[QuantumTape, Sequence[QuantumTape]]): the circuits to calculate derivatives for
            execution_config (ExecutionConfig): a datastructure with all additional information required for execution

        Returns:
            Tuple: The jacobian for each trainable parameter

        .. seealso:: :meth:`~.supports_derivatives` and :meth:`~.execute_and_compute_derivatives`.

        **Execution Config:**

        The execution config has ``gradient_method`` and ``order`` property that describes the order of differentiation requested. If the requested
        method or order of gradient is not provided, the device should raise a ``NotImplementedError``. The :meth:`~.supports_derivatives`
        method can pre-validate supported orders and gradient methods.

        **Return Shape:**

        If a batch of quantum scripts is provided, this method should return a tuple with each entry being the gradient of
        each individual quantum script. If the batch is of length 1, then the return tuple should still be of length 1, not squeezed.

        """
        raise NotImplementedError

    def execute_and_compute_derivatives(
        self,
        circuits: QuantumTape_or_Batch,
        execution_config: ExecutionConfig = DefaultExecutionConfig,
    ):
        """Compute the results and jacobians of circuits at the same time.

        Args:
            circuits (Union[QuantumTape, Sequence[QuantumTape]]): the circuits or batch of circuits
            execution_config (ExecutionConfig): a datastructure with all additional information required for execution

        Returns:
            tuple: A numeric result of the computation and the gradient.

        See :meth:`~.execute` and :meth:`~.compute_derivatives` for more information about return shapes and behaviour.
        If :meth:`~.compute_derivatives` is defined, this method should be as well.

        This method can be used when the result and execution need to be computed at the same time, such as
        during a forward mode calculation of gradients. For certain gradient methods, such as adjoint
        diff gradients, calculating the result and gradient at the same can save computational work.

        """
        return self.execute(circuits, execution_config), self.compute_derivatives(
            circuits, execution_config
        )

    def compute_jvp(
        self,
        circuits: QuantumTape_or_Batch,
        tangents: Tuple[Number],
        execution_config: ExecutionConfig = DefaultExecutionConfig,
    ):
        r"""The jacobian vector product used in forward mode calculation of derivatives.

        Args:
            circuits (Union[QuantumTape, Sequence[QuantumTape]]): the circuit or batch of circuits
            tangents (tensor-like): Gradient vector for input parameters.
            execution_config (ExecutionConfig): a datastructure with all additional information required for execution

        Returns:
            Tuple: A numeric result of computing the jacobian vector product

        **Definition of jvp:**

        If we have a function with jacobian:

        .. math::

            \vec{y} = f(\vec{x}) \qquad J_{i,j} = \frac{\partial y_i}{\partial x_j}

        The Jacobian vector product is the inner product with the derivatives of :math:`x`, yielding
        only the derivatives of the output :math:`y`:

        .. math::

            \text{d}y_i = \Sigma_{j} J_{i,j} \text{d}x_j

        **Shape of tangents:**

        The ``tangents`` tuple should be the same length as ``circuit.get_parameters()`` and have a single number per
        parameter. If a number is zero, then the gradient with respect to that parameter does not need to be computed.

        """
        raise NotImplementedError

    def execute_and_compute_jvp(
        self,
        circuits: QuantumTape_or_Batch,
        tangents: Tuple[Number],
        execution_config: ExecutionConfig = DefaultExecutionConfig,
    ):
        """Execute a batch of circuits and compute their jacobian vector products.

        Args:
            circuits (Union[QuantumTape, Sequence[QuantumTape]]): circuit or batch of circuits
            tangents (tensor-like): Gradient vector for input parameters.
            execution_config (ExecutionConfig): a datastructure with all additional information required for execution

        Returns:
            Tuple, Tuple: A numeric result of execution and of computing the jacobian vector product

        .. seealso:: :meth:`~.Device.execute` and :meth:`~.Device.compute_jvp`
        """
        return self.execute(circuits, execution_config), self.compute_jvp(
            circuits, tangents, execution_config
        )

    def supports_jvp(
        self,
        execution_config: Optional[ExecutionConfig] = None,
        circuit: Optional[QuantumTape] = None,
    ) -> bool:
        """Whether or not a given device defines a custom jacobian vector product.

        Args:
            execution_config (ExecutionConfig): A description of the hyperparameters for the desired computation.
            circuit (None, QuantumTape): A specific circuit to check differentation for.

        Default behaviour assumes this to be ``True`` if :meth:`~.compute_jvp` is overridden.

        """
        return type(self).compute_jvp != Device.compute_jvp

    def compute_vjp(
        self,
        circuits: QuantumTape_or_Batch,
        cotangents: Tuple[Number],
        execution_config: ExecutionConfig = DefaultExecutionConfig,
    ):
        r"""The vector jacobian product used in reverse-mode differentiation.

        Args:
            circuits (Union[QuantumTape, Sequence[QuantumTape]]): the circuit or batch of circuits
            cotangents (Tuple[Number]): Gradient-output vector. Must have shape matching the output shape of the
                corresponding circuit
            execution_config (ExecutionConfig): a datastructure with all additional information required for execution

        Returns:
            tensor-like: A numeric result of computing the vector jacobian product

        **Definition of vjp:**

        If we have a function with jacobian:

        .. math::

            \vec{y} = f(\vec{x}) \qquad J_{i,j} = \frac{\partial y_i}{\partial x_j}

        The vector jacobian product is the inner product of the derivatives of the output ``y`` with the
        Jacobian matrix. The derivatives of the output vector are sometimes called the **cotangents**.

        .. math::

            \text{d}x_i = \Sigma_{i} \text{d}y_i J_{i,j}

        **Shape of cotangents:**

        The value provided to ``cotangents`` should match the output of :meth:`~.execute`.

        """
        raise NotImplementedError

    def execute_and_compute_vjp(
        self,
        circuits: QuantumTape_or_Batch,
        cotangents: Tuple[Number],
        execution_config: ExecutionConfig = DefaultExecutionConfig,
    ):
        r"""Calculate both the results and the vector jacobian product used in reverse-mode differentiation.

        Args:
            circuits (Union[QuantumTape, Sequence[QuantumTape]]): the circuit or batch of circuits to be executed
            cotangents Tuple[Number]: Gradient-output vector. Must have shape matching the output shape of the
                corresponding circuit
            execution_config (ExecutionConfig): a datastructure with all additional information required for execution

        Returns:
            Tuple, Tuple: the result of executing the scripts and the numeric result of computing the vector jacobian product

        .. seealso:: :meth:`~.Device.execute` and :meth:`~.Device.compute_vjp`
        """
        return self.execute(circuits, execution_config), self.compute_vjp(
            circuits, cotangents, execution_config
        )

    def supports_vjp(
        self,
        execution_config: Optional[ExecutionConfig] = None,
        circuit: Optional[QuantumTape] = None,
    ) -> bool:
        """Whether or not a given device defines a custom vector jacobian product.

        Args:
            execution_config (ExecutionConfig): A description of the hyperparameters for the desired computation.
            circuit (None, QuantumTape): A specific circuit to check differentation for.

        Default behaviour assumes this to be ``True`` if :meth:`~.compute_vjp` is overridden.
        """
        return type(self).compute_vjp != Device.compute_vjp
