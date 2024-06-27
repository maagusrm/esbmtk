"""
     esbmtk: A general purpose Earth Science box model toolkit
     Copyright (C), 2020 Ulrich G. Wortmann

     This program is free software: you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation, either version 3 of the License, or
     (at your option) any later version.

     This program is distributed in the hope that it will be useful,
     but WITHOUT ANY WARRANTY; without even the implied warranty of
     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
     GNU General Public License for more details.

     You should have received a copy of the GNU General Public License
     along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import esbmtk

from esbmtk import (
    Model,
    Reservoir,
    ConnectionProperties,
    SourceProperties,
    SinkProperties,
    Q_,
)


def calculate_burial(po4_export_flux: float, o2_con: float) -> float:
    """#add an empty tuple
    Calculate burial as a function of productivity and oxygen concentration.

    :param po4_export_flux: Surface ocean productivity in umol/L
    :type po4_export_flux: float
    :param o2_con: Oxygen concentration in the deep box in umol/L
    :type o2_con: float
    :return: Burial flux in mol/year
    :rtype: float
    """
    # burial fraction to [oxygen] approximation of relationship from 0.01 to 0.1
    min_burial_fraction = 0.01
    max_burial_fraction = 0.1
    burial_fraction = min_burial_fraction + (
        max_burial_fraction - min_burial_fraction
    ) * (o2_con / 100)

    deep_ocean_v = 1e18  # in litres

    # productivity in mol/year
    productivity_mol_year = (
        po4_export_flux * deep_ocean_v * 1e-6
    )  # Convert umol/L to mol

    burial_flux = productivity_mol_year * burial_fraction

    return burial_flux


from esbmtk import ExternalCode


def add_my_burial(
    source, sink, species, po4_export_flux: float, o2_con: float, scale
) -> None:
    """This function initializes a user supplied function
    so that it can be used within the ESBMTK ecosystem.

    Parameters
    ----------
    source : Source | Species | Reservoir
        A source
    sink : Sink | Species | Reservoir
        A sink
    species : SpeciesProperties
        A model species
    po4_export_flux : float
        PO4 export flux in umol/L
    o2_con : float
        Oxygen concentration in umol/L
    scale : float
        A scaling factor
    """
    p = (scale,)  # float into tuple
    ec = ExternalCode(
        name="calculate_burial",
        species=species,
        function=calculate_burial,
        fname="calculate_burial",
        function_input_data=[po4_export_flux, F_b],
        function_params=p,
        return_values=[
            {f"F_{sink}.{M.PO4}": "po4_burial"},
        ],
    )
