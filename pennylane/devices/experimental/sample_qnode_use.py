import pennylane as qml
from pennylane.devices.experimental import *
from pennylane.runtime.runtime_config import *

dev_dq = qml.device("default.qubit", wires=1)
dev = custom_device_3_numpydev.TestDevicePythonSim()

###########################################################
#### To be removed with updates to QNode & execute pipeline

def tmp_expand_fn(cirq, max_expansion):
    return dev.preprocess(cirq)

def batch_tform(circ):
    return [circ], lambda x: x

dev.batch_execute = dev.execute
dev.batch_transform = batch_tform #dev.preprocess
dev.expand_fn = tmp_expand_fn
dev.shots = None
dev._shot_vector = []

###########################################################

params = qml.numpy.random.rand(1)

#ec = ExecutionConfig(diff_method=None)

@qml.qnode_std_22(dev)
def circ(p):
   qml.RX(p[0], 0)
   return qml.expval(qml.PauliZ(0))

@qml.qnode(dev_dq)
def circ_dq(p):
   qml.RX(p[0], 0)
   return qml.expval(qml.PauliZ(0))

circ(params), circ_dq(params)
