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
Tests for the ``DatasetMolecule`` attribute type.
"""


import numpy as np
import pytest

from pennylane.data.attributes.molecule import DatasetMolecule
from pennylane.data.base.typing_util import get_type_str
from pennylane.qchem import Molecule


@pytest.mark.parametrize(
    ("symbols", "coordinates"),
    [
        (["H", "F"], np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]])),
    ],
)
class TestDatasetMolecule:
    """Test that ``DatasetMolecule`` is correctly bind and value
    initialized."""

    def test_value_init(self, symbols, coordinates):
        """Test that a DatasetMolecule can be value-initialized
        from a Molecule."""
        mol_in = Molecule(symbols, coordinates)

        dset_mol = DatasetMolecule(mol_in)

        assert dset_mol.info["type_id"] == "molecule"
        assert dset_mol.info["py_type"] == get_type_str(Molecule)

        mol_out = dset_mol.get_value()

        assert repr(mol_out) == repr(mol_in)
        assert (mol_out.alpha == mol_in.alpha).all()
        assert mol_out.basis_name == mol_in.basis_name
        assert (mol_out.coeff == mol_in.coeff).all()
        assert mol_out.symbols == mol_in.symbols
        assert (mol_out.coordinates == mol_in.coordinates).all()
        assert (mol_out.l == mol_in.l).all()
        assert mol_out.mult == mol_in.mult

    def test_bind_init(self, symbols, coordinates):
        """Test that a DatasetMolecule is correctly bind-initialized."""
        mol_in = Molecule(symbols, coordinates)

        bind = DatasetMolecule(mol_in).bind

        dset_mol = DatasetMolecule(bind=bind)
        assert dset_mol.info["type_id"] == "molecule"
        assert dset_mol.info["py_type"] == get_type_str(Molecule)

        mol_out = dset_mol.get_value()

        assert repr(mol_out) == repr(mol_in)
        assert (mol_out.alpha == mol_in.alpha).all()
        assert mol_out.basis_name == mol_in.basis_name
        assert (mol_out.coeff == mol_in.coeff).all()
        assert mol_out.symbols == mol_in.symbols
        assert (mol_out.coordinates == mol_in.coordinates).all()
        assert (mol_out.l == mol_in.l).all()
        assert mol_out.mult == mol_in.mult
