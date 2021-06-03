"""
     esbmtk: A general purpose Earth Science box model toolkit
     Copyright (C), 2020-2021 Ulrich G. Wortmann

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

from numbers import Number
from nptyping import *
from typing import *
from numpy import array, set_printoptions, arange, zeros, interp, mean
from copy import deepcopy, copy
from time import process_time
from numba import njit
from numba.typed import List
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

import logging
import time
import builtins
from .esbmtk import esbmtkBase, Model, Reservoir, VirtualReservoir, ReservoirGroup

# define a transform function to display the Hplus concentration as pH
def phc(m: float) -> float:
    """the reservoir class accepts a plot transform. here we use this to
    display the H+ concentrations as pH. After import, you can use it
    with like this in the reservoir definition

     plot_transform_c=phc,

    """
    import numpy as np

    pH = -np.log10(m)
    return pH


class SeawaterConstants(esbmtkBase):
    """Provide basic seawater properties as a function of T and Salinity.
    Pressure may come at a later stage

    Example:

    Seawater(name="SW",
             model=,
             temperature = optional in C, defaults to 25,
             salinity  = optional in psu, defaults to 35,
             pressure = optional, defaults to 0 bars = 1atm,
             pH = optional, defaults to 8.1,
            )

    useful methods:

    SW.show() will list all known values

    After initialization this class provides access to each value the following way

    instance_name.variable_name

    """

    def __init__(self, **kwargs: Dict[str, str]):

        import math

        # dict of all known keywords and their type
        self.lkk: Dict[str, any] = {
            "name": str,
            "model": Model,
            "salinity": (int, float),
            "temperature": (int, float),
            "pH": (int, float),
            "pressure": Number,
            "register": any,
        }

        # provide a list of absolutely required keywords
        self.lrk: list = ["name"]
        # list of default values if none provided
        self.lod: Dict[str, any] = {
            "salinity": 35.0,
            "temperature": 25.0,
            "pH": 8.1,
            "pressure": 0,
            "register": "None",
        }

        # validate input and initialize instance variables
        self.__initerrormessages__()
        self.__validateandregister__(kwargs)  # initialize keyword values

        # legacy names
        self.n: str = self.name  # string =  name of this instance
        self.mo: Model = self.model
        self.hplus = 10 ** -self.pH
        self.constants: list = ["K0", "K1", "K2", "KW", "KB", "Ksp"]
        self.species: list = [
            "dic",
            "ta",
            "ca",
            "co2",
            "hco3",
            "co3",
            "boron",
            "boh4",
            "boh3",
            "oh",
        ]

        self.update()
        self.__register_name__()

    def update(self, **kwargs: dict) -> None:
        """Update values if necessary"""

        from math import log10

        if kwargs:
            self.lrk: list = []
            self.__validateandregister__(kwargs)

        # update K values and species concentrations according to P, S, and T
        self.__init_std_seawater__()
        self.__init_carbon__()
        self.__init_boron__()
        self.__init_water__()
        self.__init_gasexchange__()
        self.__init_calcite__()
        self.__init_c_fractionation_factors__()

        # get total alkalinity

        self.ca = self.hco3 + 2 * self.co3
        self.ta = self.ca + self.boh4 + self.oh - self.hplus

        # update pk values
        for n in self.constants:
            v = getattr(self, n)
            pk = f"p{n.lower()}"
            setattr(self, pk, -log10(v))

    def show(self) -> None:
        """Printout pK values. """

        from math import log10

        for n in self.species:
            v = getattr(self, n)
            print(f"{n} = {v * 1E6:.2f} nmol/l")

        print(f"pH = {-log10(self.hplus):.2f}\n")
        print(f"salinity = {self.salinity:.2f}")
        print(f"temperature = {self.temperature:.2f}\n")

        for n in self.constants:
            K = getattr(self, n)
            pk = getattr(self, f"p{n.lower()}")
            print(f"{n} = {K:.2e}, p{n} = {pk:.2f}")

    def __init_std_seawater__(self) -> None:
        """Provide values for standard seawater. Data after Zeebe and Gladrow
        all values in mol/kg. To convert to seawater these values need to be
        multiplied by sw

        """

        S = self.salinity
        swc = (1000 + S) / 1000
        self.dic = 0.00204 * swc
        self.boron = 0.00042 * swc
        self.oh = 0.00001 * swc

    def __init_gasexchange__(self) -> None:
        """Initialize constants for gas-exchange processes"""

        self.water_vapor_partial_pressure()
        self.co2_solubility_constant()

    def __init_carbon__(self) -> None:
        """Calculate the carbon equilibrium values as function of
        temperature T and salinity S

        """

        from math import exp, log, log10

        T = 273.15 + self.temperature
        S = self.salinity

        # After Weiss 1974
        lnK0: float = (
            93.4517 * 100 / T
            - 60.2409
            + 23.3585 * log(T / 100)
            + S * (0.023517 - 0.023656 * T / 100 + 0.0047036 * (T / 100) ** 2)
        )

        lnk1: float = (
            -2307.1266 / T
            + 2.83655
            - 1.5529413 * log(T)
            + S ** 0.5 * (-4.0484 / T - 0.20760841)
            + S * 0.08468345
            + S ** (3 / 2) * -0.00654208
            + log(1 - 0.001006 * S)
        )

        lnk2: float = (
            -9.226508
            - 3351.6106 / T
            - 0.2005743 * log(T)
            + (-0.106901773 - 23.9722 / T) * S ** 0.5
            + 0.1130822 * S
            - 0.00846934 * S ** 1.5
            + log(1 - 0.001006 * S)
        )

        self.K0: float = exp(lnK0)
        self.K1: float = exp(lnk1)
        self.K2: float = exp(lnk2)

        self.K1 = self.__pressure_correction__("K1", self.K1)
        self.K2 = self.__pressure_correction__("K2", self.K2)

        self.co2 = self.dic / (
            1 + self.K1 / self.hplus + self.K1 * self.K2 / self.hplus ** 2
        )
        self.hco3 = self.dic / (1 + self.hplus / self.K1 + self.K2 / self.hplus)
        self.co3 = self.dic / (
            1 + self.hplus / self.K2 + self.hplus ** 2 / (self.K1 * self.K2)
        )

    def __init_boron__(self) -> None:
        """Calculate the boron equilibrium values as function of
        temperature T and salinity S

        """

        from math import exp, log

        T = 273.15 + self.temperature
        S = self.salinity

        lnkb = (
            (
                -8966.9
                - 2890.53 * S ** 0.5
                - 77.942 * S
                + 1.728 * S ** 1.5
                - 0.0996 * S ** 2
            )
            / T
            + 148.0248
            + 137.1942 * S ** 0.5
            + 1.62142 * S
            - (24.4344 + 25.085 * S ** 0.5 + 0.2474 * S) * log(T)
            + 0.053105 * S ** 0.5 * T
        )

        self.KB = exp(lnkb)
        self.KB = self.__pressure_correction__("KB", self.KB)

        self.boh4 = self.boron * self.KB / (self.hplus + self.KB)
        self.boh3 = self.boron - self.boh4

    def __init_water__(self) -> None:
        """Calculate the water equilibrium values as function of
        temperature T and salinity S

        """

        from math import exp, log

        T = 273.15 + self.temperature
        S = self.salinity

        lnKW = (
            148.96502
            - 13847.27 / T
            - 23.6521 * log(T)
            + (118.67 / T - 5.977 + 1.0495 * log(T)) * S ** 0.5
            - 0.01615 * S
        )
        self.KW = exp(lnKW)
        self.KW = self.__pressure_correction__("KW", self.KW)
        self.oh = self.KW / self.hplus

    def __pressure_correction__(self, n: str, K: float) -> float:
        """Correct K-values for pressure. After Zeebe and Wolf Gladrow 2001

        name = name of K-value, i.e. "K1"
        K = uncorrected value
        T = temperature in Deg C
        P = pressure in atm
        """

        from math import exp, log

        R: float = 83.131
        Tc: float = self.temperature
        T: float = 273.15 + Tc
        P: float = self.pressure
        RT: float = R * T

        A: dict = {}
        A["K1"]: list = [25.50, 0.1271, 0.0, 3.08, 0.0877]
        A["K2"]: list = [15.82, -0.0219, 0.0, -1.13, -0.1475]
        A["KB"]: list = [29.48, 0.1622, -2.6080, 2.84, 0.0]
        A["KW"]: list = [25.60, 0.2324, -3.6246, 5.13, 0.0794]
        A["KS"]: list = [18.03, 0.0466, 0.3160, 4.53, 0.0900]
        A["KF"]: list = [9.780, -0.0090, -0.942, 3.91, 0.054]
        A["Kca"]: list = [48.76, 0.5304, 0.0, 11.76, 0.3692]
        A["Kar"]: list = [46.00, 0.5304, 0.0, 11.76, 0.3692]

        a: list = A[n]

        DV: float = -a[0] + (a[1] * Tc) + (a[2] / 1000 * Tc ** 2)
        DK: float = -a[3] / 1000 + (a[4] / 1000 * Tc) + (0 * Tc ** 2)

        # print(f"DV = {DV}")
        # print(f"DK = {DK}")
        # print(f"log k= {log(K)}")

        lnkp: float = -(DV / RT) * P + (0.5 * DK / RT) * P ** 2 + log(K)
        # print(lnkp)

        return exp(lnkp)

    def water_vapor_partial_pressure(self) -> None:
        """Calculate the water vapor partial pressure at sealevel (1 atm) as
        a function of temperature and salinity. Eq. Weiss and Price 1980
        doi:10.1016/0304-4203(80)90024-9

        Since we assume that we only use this expression at sealevel,
        we drop the pressure term

        """

        T = self.temperature + 273.15
        S = self.salinity

        self.p_H2O = np.exp(
            24.4543 - 67.4509 * (100 / T) - 4.8489 * np.log(T / 100) - 0.000544 * S
        )

    def co2_solubility_constant(self) -> None:
        """Calculate the solubility of CO2 at a given temperature and salinity. Coefficients
        after Sarmiento and Gruber 2006 which includes corrections for CO2 to correct for non
        ideal gas behavior

        Parameters Ai & Bi from Tab 3.2.2 in  Sarmiento and Gruber 2006
        """

        # Calculate the volumetric solubility function F_A in mol/l/m^3
        S = self.salinity
        T = 273.15 + self.temperature
        A1 = -160.7333
        A2 = 215.4152
        A3 = 89.892
        A4 = -1.47759
        B1 = 0.029941
        B2 = -0.027455
        B3 = 0.0053407
        ln_F = (
            A1
            + A2 * (100 / T)
            + A3 * np.log(T / 100)
            + A4 * (T / 100) ** 2
            + S * (B1 + B2 * (T / 100) + B3 * (T / 100) ** 2)
        )
        F = np.exp(ln_F) * 1e6

        # correct for water vapor partial pressure
        self.SA_co2 = F / (1 - self.p_H2O)

        # the above number is in mmol/m3 but esbmtk uses mol/l
        # self.SA_co2 = self.SA_co2

    def __init_calcite__(self) -> None:
        """Calculate Calcite solubility as a function of pressure following
        Fig 1 in in Boudreau et al, 2010, https://doi.org/10.1029/2009gl041847

        Note that this equation assumes an idealized ocean temperature profile.
        So it cannot be applied to a warm ocean

        """

        self.Ksp = 4.3513e-7 * np.exp(0.0019585 * self.pressure)

    def __init_c_fractionation_factors__(self):
        """Calculate the fractionation factors for the various carbon species transitions.
        After Zeebe and Gladrow, 2001, CHapter 3.2.3

        e = (a -1) * 1E3

        and

        a =  1 + e / 1E3

        where the subscripts denote:

        g = gaseous CO2
        d = dissolved CO2
        b = bicarbonate ion
        c = carbonate ion

        """

        T = 273.15 + self.temperature

        # CO2g versus HCO3
        self.e_gb: float = -9483 / T + 23.89
        self.a_gb: float = 1 + self.e_gb / 1000

        # CO2aq versus CO2g
        self.e_dg: float = -373 / T + 0.19
        self.a_dg: float = 1 + self.e_dg / 1000

        # CO2aq versus HCO3
        self.e_db: float = -9866 / T + 24.12
        self.a_db: float = 1 + self.e_db / 1000

        # CO32- versus HCO3
        self.e_cb: float = -867 / T + 2.52
        self.a_cb: float = 1 + self.e_cb / 1000


def carbonate_system_new(
    ca_con: float,
    hplus_con: float,
    volume: float,
    swc: SeawaterConstants,
    rg: ReservoirGroup = "None",
) -> tuple:

    """Setup the virtual reservoir which will calculate H+, CA, HCO3, CO3, CO2a

    You must provide
    ca_con: initial carbonate concentration. Must be a quantity
    hplus_con: initial H+ concentration. Must be a quantity
    volume: volume : Must be a quantity for reservoir definition but when  used
    as argumment to the functionn it muts be converted to magnitude

    swc : a seawater constants object
    rg: optional, must be a reservoir group. If present, the below reservoirs
        will be registered with this group.

    Returns the reservoir handles to VCA and VH

    All list type objects must be converted to numba Lists, if the function is to be used with
    the numba solver.

    """

    from esbmtk import VirtualReservoir_no_set, calc_carbonates

    print(f"using carbonate_system_new in carbonate_chemistry.py")

    VirtualReservoir_no_set(
        name="cs",
        species=CO2,
        function=calc_carbonates,
        # initialize 5 datafield and provide defaults for H+
        vr_datafields=[rg.swc.hplus, rg.swc.ca, rg.swc.hco3, rg.swc.co3, rg.swc.co2],
        function_input_data=List(rg.DIC.c, rg.TA.c),
        function_params=List(
            [rg.swc.K1, rg.swc.K2, rg.swc.KW, rg.swc.KB, rg.swc.boron, rg.swc.hplus]
        ),
        register=rg,
    )


# def calc_carbonates(input_data, vr_data, params, i)
@njit
def calc_carbonates(i: int, input_data: List, vr_data: List, params: List) -> None:
    """Calculates and returns the carbonate concentrations with the format of
    [d1, d2, d3, d4, d5] where each variable corresponds to
    [H+, CA, HCO3, CO3, CO2(aq)], respectively, at the ith time-step of the model.

    LIMITATIONS:
    - This in used in conjunction with Virtual_Reservoir_no_set objects!
    - Assumes all concentrations are in mol/L

    Calculations are based off equations from Follows, 2006.
    doi:10.1016/j.ocemod.2005.05.004

    Example:

    VirtualReservoir_no_set(
                name="cs",
                species=CO2,
                vr_datafields=List([self.swc.hplus, 0.0, 0.0, 0.0, 0.0]),
                function=calc_carbonates,
                function_input_data=List([self.DIC.c, self.TA.c]),
                function_params=List(
                    [
                        self.swc.K1,
                        self.swc.K2,
                        self.swc.KW,
                        self.swc.KB,
                        self.swc.boron,
                        self.swc.hplus,
                    ]
                ),
                register= # reservoir_handle to register with
            )

            # setup aliases
            self.cs.H = self.cs.vr_data[0]
            self.cs.CA = self.cs.vr_data[1]
            self.cs.HCO3 = self.cs.vr_data[2]
            self.cs.CO3 = self.cs.vr_data[3]
            self.cs.CO2aq = self.cs.vr_data[4]


    To plot the other species, please create DataField objects accordingly.

    Sample code for plotting CO3:
    > DataField(name = "pH",
          associated_with = Ocean.V_combo,
          y1_data = -np.log10(Ocean.V_combo.vr_data[0]),
          y1_label = "pH",
          y1_legend = "pH"
     )
    > Model_Name.plot([pH])


    Author: M. Niazi & T. Tsan, 2021

    """

    dic: float = input_data[0][i - 1]
    ta: float = input_data[1][i - 1]

    # calculates carbonate alkalinity (ca) based on H+ concentration from the
    # previous time-step
    # hplus: float = input_data[2][i - 1]
    hplus: float = vr_data[0][i - 1]

    k1 = params[0]
    k2 = params[1]
    KW = params[2]
    KB = params[3]
    boron = params[4]

    # ca
    oh: float = KW / hplus
    boh4: float = boron * KB / (hplus + KB)
    fg: float = hplus - oh - boh4
    ca: float = ta + fg
    # hplus
    gamm: float = dic / ca
    dummy: float = (1 - gamm) * (1 - gamm) * k1 * k1 - 4 * k1 * k2 * (1 - (2 * gamm))

    hplus: float = 0.5 * ((gamm - 1) * k1 + (dummy ** 0.5))
    # hco3 and co3
    """ Since CA = [hco3] + 2[co3], can the below expression can be simplified
    """
    co3: float = dic / (1 + (hplus / k2) + ((hplus ** 2) / (k1 * k2)))
    hco3: float = dic / (1 + (hplus / k1) + (k2 / hplus))
    # co2 (aq)
    """DIC = hco3 + co3 + co2 + H2CO3 The last term is however rather
    small, so it may be ok to simply write co2aq = dic - hco3 + co3.
    Let's test this once we have a case where pco2 is calculated from co2aq
    """

    co2aq: float = dic / (1 + (k1 / hplus) + (k1 * k2 / (hplus ** 2)))

    vr_data[0][i] = hplus
    vr_data[1][i] = ca
    vr_data[2][i] = hco3
    vr_data[3][i] = co3
    vr_data[4][i] = co2aq


def calc_pCO2(
    dic: Union[Reservoir, VirtualReservoir],
    hplus: Union[Reservoir, VirtualReservoir],
    SW: SeawaterConstants,
) -> Union[NDArray, Float]:

    """
    Calculate the concentration of pCO2 as a function of DIC,
    H+, K1 and k2 and returns a numpy array containing
    the pCO2 in uatm at each timestep. Calculations are based off
    equations from Follows, 2006. doi:10.1016/j.ocemod.2005.05.004
    dic: Reservoir  = DIC concentrations in mol/liter
    hplus: Reservoir = H+ concentrations in mol/liter
    SW: Seawater = Seawater object for the model
    it is typically used with a DataField object, e.g.
    pco2 = calc_pCO2(dic,h,SW)
     DataField(name = "SurfaceWaterpCO2",
                       associated_with = reservoir_handle,
                       y1_data = pco2,
                       y1_label = r"pCO_{2}",
                       y1_legend = r"pCO_{2}",
                       )
    Author: T. Tsan
    """

    dic_c: [NDArray, Float] = dic.c
    hplus_c: [NDArray, Float] = hplus.c

    k1: float = SW.K1
    k2: float = SW.K2

    co2: [NDArray, Float] = dic_c / (1 + (k1 / hplus_c) + (k1 * k2 / (hplus_c ** 2)))

    pco2: [NDArray, Float] = co2 / SW.K0 * 1e6

    return pco2


def calc_pCO2b(
    dic: Union[float, NDArray],
    hplus: Union[float, NDArray],
    SW: SeawaterConstants,
) -> Union[NDArray, Float]:

    """
    Same as calc_pCO2, but accepts values/arrays rather than Reservoirs.
    Calculate the concentration of pCO2 as a function of DIC,
    H+, K1 and k2 and returns a numpy array containing
    the pCO2 in uatm at each timestep. Calculations are based off
    equations from Follows, 2006. doi:10.1016/j.ocemod.2005.05.004
    dic:  = DIC concentrations in mol/liter
    hplus: = H+ concentrations in mol/liter
    SW: Seawater = Seawater object for the model
    it is typically used with a DataField object, e.g.
    pco2 = calc_pCO2b(dic,h,SW)
     DataField(name = "SurfaceWaterpCO2",
                       associated_with = reservoir_handle,
                       y1_data = pco2b,
                       y1_label = r"pCO_{2}",
                       y1_legend = r"pCO_{2}",
                       )
    """

    dic_c: [NDArray, Float] = dic

    hplus_c: [NDArray, Float] = hplus

    k1: float = SW.K1
    k2: float = SW.K2

    co2: [NDArray, Float] = dic_c / (1 + (k1 / hplus_c) + (k1 * k2 / (hplus_c ** 2)))

    pco2: [NDArray, Float] = co2 / SW.K0 * 1e6

    return pco2


def calc_horizon(i: int, input_data: List, vr_data: List, params: List) -> None:
    """ Calculates related carbonate dissolution values and stores them
     in their respective arrays in vr_data of the VirtualReservoir_no_set object.
     This function calculates saturation depth (z_sat), carbonate compensation
     depth (zcc), snowline depth (z_snow), and the saturation state (omega value).

    Calculations from the following papers:
        (1) Boudreau et al., 2010. doi:10.1029/2009GB003654
        (2) Boudreau et al., 2010. doi:10.1029/2009GL041847
        (3) Zeebe, R.E., & Westbroek, P., 2003. doi:10.1029/2003GC000538

    Preconditions: Assumes that users provide all VirtualReservoir data and
        constants in the same order as well as the units indicated below. Function
        is used in conjunction with VirtualReservoir_no_set objects!

    Parameters:
    > input_data = List containing the following:
        deep_ocean.DIC.m
        deep_ocean.DIC.c
        deep_ocean.TA.m
        deep_ocean.TA.c
        [CO3 2- concentrations]
        [Model.hyp.get_lookup_table(min depth, max depth)]
        ])
    > vr_data = [zsat, zcc, zsnow, omega] in meters
    > params = list of Constants in the following order:
        sa = surface area of model (m^2)
        AD = total ocean area (m^2)
        time_step = time-step of Model as a float (yrs)
        volume = reservoir group volume (L)
        ksp = solubility product of calcite in the deep ocean box (mol^2/kg^2)
        Ca 2+ = calcium ion concentration (mol/kg)
        ksp0 = solubility product of calcite at air-water interface (mol^2/kg^2)
        zsat0 = characteristic depth (m)
        kc = heterogeneous rate constant/mass transfer coefficient for calcite dissolution (kg m^-2 yr^-1)
        B = export of calcite into deep ocean box (mol/yr)
        pc = characteristic pressure (atm)
        pg = density of water * acceleration due to gravity (atm/m)
        I_caco3 = inventory of dissolvable CaCO3 (mol/m^2)
    """
    import numpy as np

    #----------------------Model Parameters-------------------------------------
    co3d: float = input_data[0][i - 1]
    depth_areas: float = input_data[1]

    sa: float = params[0] #surface area
    AD: float = params[1] #total ocean area
    dt: float = params[2] #time-step
    reservoir_vol: float = params[3] #reservoir volume
    ksp: float = params[4] #ksp value for deep ocean box
    ca: float = params[5] #calcium ion concentration
    ksp0: float = params[6] #ksp at ocean surface interface
    zsat0: float = params[7] #characteristic depth
    kc: float = params[8] #rate constant
    B: float = params[9] #calcite flux
    pc: float = params[10] #characteristic pressure
    pg: float = params[11] #seawater density and gravity due to acceleration (atm/m)
    I_caco3: float = params[12] #dissolvable CaCO3 inventory

    #---------------------Calculate omega---------------------------------------
    # Equation (1) from paper (3) Zeebe & Westbroek (2003)
    # omega = [Ca2+]sw * [CO3 2-]sw / Ksp*
    omega: float = (ca * co3d) / ksp

    # ---------------------Calculate zsat---------------------------------------
    # Equation (2) from paper (1) Boudreau (2010)
    # zsat = zsat0 * ln([Ca2+][CO3 2-]D / Ksp0)
    zsat: float = zsat0 * np.log(ca * co3d / ksp0)

    #------------------------Calculate zcc--------------------------------------
    # Equation (3) from paper (1) Boudreau (2010)
    # zsat = zsat0 * ln((B * [Ca2+] / Ksp0 * AD * kc) + ([Ca2+][CO3 2-]D / Ksp0))
    term1: float = (B * ca) / (ksp0 * AD * kc)
    term2: float = ca * co3d / ksp0
    zcc: float = zsat0 * np.log(term1 + (term2))

    #------------------------Calculate zsnow------------------------------------
    #---Calculating Csat at depths zcc and zsnow---
    # Equation (1) from paper (2) Boudreau (2010)
    # Csat = Ksp0 / [Ca] * exp(p(z) / pc)
    prev_zcc: float = vr_data[1][i - 1] #zcc from previous timestep
    pz_zcc: float = pg * prev_zcc #gauge pressure (atm) at depth zcc (m)
    Csat_zcc: float = (ksp0 / ca) * np.exp(pz_zcc/pc)

    prev_zsnow: float = vr_data[2][i-1] #zsnow from previous timestep
    pz_zsnow: float = pg * prev_zsnow #gauge pressure (atm) at depth zsnow (m)
    Csat_zsnow: float = (ksp0 / ca) * np.exp(pz_zsnow/pc)

    #---Calculating BPDC---
    # Equation (10) from paper (1) Boudreau (2010)
    # BPDC = kc * (integral of (Csat(z,t) - [CO3]D(t)) dz from zsnow(t) to zcc(t))
    BPDC: float = kc * ((sa * depth_areas[int(prev_zcc)] * (Csat_zcc - co3d)) -
                          (sa * depth_areas[int(prev_zsnow)] * (Csat_zsnow - co3d)))

    #---Calculating zsnow---
    # Equation (4) from paper (1) Boudreau (2010)
    # dzsnow/dt = Bpdc(t) / (a'(zsnow(t)) * ICaCO3
    # Note that we use equation (1) from paper (1) Boudreau (2010) as well:
    # where a'(z) is the differential bathymetric curve: A(z2, z1) = a'(z2) - a'(z1)
    zsnow_dt: float = BPDC / (sa * depth_areas[int(prev_zsnow)] * I_caco3) #movement of snowline
    #multiplying change in snowline by the timestep to get the current snowline depth
    zsnow: float = prev_zsnow + (zsnow_dt * dt)

    #------------Adding CaCO3 flux back into DIC and Total Alkalinity-----------
    co3_mass: float = BPDC * dt
    # add/subtract to DIC reservoir mass (moles)
    # dic mass = non-updated DIC mass + dissolved co3 mass
    input_data[4][i] = input_data[4][i] + co3_mass

    # update DIC concentration (mol/L)
    # [dic] = dic mass / reservoir volume
    input_data[2][i] = input_data[4][i] / reservoir_vol

    # update TA mass (mol)
    # 1:2 mole ratio for changes in DIC to TA
    # TA mass = non-updated TA mass + 2 * dissolved co3 mass
    input_data[5][i] = input_data[5][i] + (2 * co3_mass)

    # update TA concentration (mol/L)
    # [TA] = TA mass / reservoir volume
    input_data[3][i] = input_data[5][i] / reservoir_vol

    # -------------Updating values stored in vr_data of the Reservoir-----------
    vr_data[0][i] = zsat
    vr_data[1][i] = zcc
    vr_data[2][i] = zsnow
    vr_data[3][i] = omega
