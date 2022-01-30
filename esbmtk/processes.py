from numbers import Number
from nptyping import *
from typing import *
from numpy import array, set_printoptions, arange, zeros, interp, mean
from pandas import DataFrame
from copy import deepcopy, copy
from time import process_time
from numba import njit, jit
from numba.typed import List

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

import logging
import time
import builtins

set_printoptions(precision=4)
# from .utility_functions import *
from .esbmtk import esbmtkBase, Reservoir, Flux, Signal, Source, Sink
from .utility_functions import sort_by_type
from .solver import get_imass, get_frac, get_delta, get_flux_data
from . import ureg, Q_

# from .connections import ConnnectionGroup


class Process(esbmtkBase):
    """This class defines template for process which acts on one or more
    reservoir flux combinations. To use it, you need to create an
    subclass which defines the actual process implementation in their
    call method. See 'PassiveFlux as example'

    """

    __slots__ = ("reservoir", "r", "flux", "r", "mo", "direction", "scale")

    def __init__(self, **kwargs: Dict[str, any]) -> None:
        """
        Create a new process object with a given process type and options
        """

        self.__defaultnames__()  # default kwargs names
        self.__initerrormessages__()  # default error messages
        self.bem.update({"rate": "a string"})
        self.bem.update({"scale": "Number or quantity"})
        self.__validateandregister__(kwargs)  # initialize keyword values

        self.__postinit__()  # do some housekeeping
        self.__register_name__()

    def __postinit__(self) -> None:
        """Do some housekeeping for the process class"""

        # legacy name aliases
        self.n: str = self.name  # display name of species
        if "reserevoir" in self.kwargs:
            self.r: Reservoir = self.reservoir
            self.m: Model = self.r.sp.mo
        else:
            self.m: Model = self.flux.mo  # the model handle

        self.mo: Model = self.m
        self.f: Flux = self.flux
        self.mo: Model = self.m

        # self.rm0: float = self.r.m[0]  # the initial reservoir mass

        if "reserevoir" in self.kwargs:
            if isinstance(self.r, Reservoir):
                self.direction: Dict[Flux, int] = self.r.lio[self.f]

        self.__misc_init__()

    def __delayed_init__(self) -> None:
        """
        Initialize stuff which is only known after the entire model has been defined.
        This will be executed just before running the model. You need to add the following
        two lines somewhere in the init procedure (preferably by redefining __misc_init__)
        and redefine __delayed_init__ to actually execute any code below

        # this process requires delayed init
        self.mo.lto.append(self)

        """

        pass

    def __misc_init__(self) -> None:
        """This is just a place holder method which will be called by default
        in __post_init__() This can be overloaded to add additional
        code to the init procedure without the need to redefine
        init. This useful for processes which only define a call method.

        """

        pass

    def __defaultnames__(self) -> None:
        """Set up the default names and dicts for the process class. This
        allows us to extend these values without modifying the entire init process

        """

        from .connections import ConnectionGroup
        from esbmtk import Reservoir, ReservoirGroup, Flux, GasReservoir

        # provide a dict of known keywords and types
        self.lkk: Dict[str, any] = {
            "name": str,
            "reservoir": (Reservoir, Source, Sink, GasReservoir),
            "flux": Flux,
            "rate": (Number, np.float64),
            "delta": (Number, np.float64),
            "lt": Flux,
            "alpha": (Number, np.float64),
            "scale": (Number, np.float64),
            "ref_reservoirs": (Flux, Reservoir, GasReservoir, list, str),
            "register": (
                str,
                ConnectionGroup,
                Reservoir,
                ReservoirGroup,
                GasReservoir,
                Flux,
            ),
        }

        # provide a list of absolutely required keywords
        self.lrk: list[str] = ["name"]

        # list of default values if none provided
        self.lod: Dict[str, any] = {"scale": 1}

    def __register__(self, reservoir: Reservoir, flux: Flux) -> None:
        """Register the flux/reservoir pair we are acting upon, and register
        the process with the reservoir

        """

        # register the reservoir flux combination we are acting on
        self.f: Flux = flux
        self.r: Reservoir = reservoir
        # add this process to the list of processes acting on this reservoir
        reservoir.lop.append(self)
        flux.lop.append(self)
        # Add to model flux list
        reservoir.mo.lop.append(self)

    def show_figure(self, x, y) -> None:
        """Apply the current process to the vector x, and show the result as y.
        The resulting figure will be automatically saved.

        Example::
             process_name.show_figure(x,y)

        """
        pass


class GenericFunction(Process):
    """This Process class creates a GenericFunction instance which is
    typically used with the VirtualReservoir, and
    ExternalCode classes. This class is not user facing,
    please see the ExternalCode class docstring for the
    function template of a user provided function.

    see calc_carbonates in the carbonate chemistry for an example how
    to write a function for this class.

    """

    __slots__ = ("function", "input_data", "vr_data", "params")

    def __init__(self, **kwargs: Dict[str, any]) -> None:
        """
        Create a new process object with a given process type and options

        """

        from . import Reservoir_no_set

        self.__defaultnames__()  # default kwargs names

        # list of allowed keywords
        self.lkk: Dict[str, any] = {
            "name": str,
            "function": any,
            "input_data": (List, str),
            "vr_data": (List, str),
            "function_params": (List, str),
            "model": any,
        }

        # required arguments
        self.lrk: list = ["name", "input_data", "vr_data", "function_params", "model"]

        # list of default values if none provided
        self.lod: Dict[any, any] = {}

        self.__initerrormessages__()  # default error messages
        self.bem.update(
            {
                "function": "a function",
                "input_data": "list of one or more numpy arrays",
                "vr_data": "list of one or more numpy arrays",
                "function_params": "a list of float values",
            }
        )
        self.__validateandregister__(kwargs)  # initialize keyword values
        self.mo = self.model

        if not callable(self.function):
            raise ValueError("function must be defined before it can be used here")

        self.__postinit__()  # do some housekeeping

        if self.mo.register == "local" and self.register == "None":
            self.register = self.mo

        self.__register_name__()  #

    def __call__(self, i: int) -> None:
        """Here we execute the user supplied function
        Where i = index of the current timestep

        """

        self.function(i, self.input_data, self.vr_data, self.function_params)

    # redefine post init
    def __postinit__(self) -> None:
        """Do some housekeeping for the process class"""

        self.__misc_init__()

    def get_process_args(self) -> tuple:
        """return the data associated with this object"""

        self.func_name: function = self.function

        return (
            self.func_name,
            self.input_data,
            self.vr_data,
            self.function_params,
        )


class AddSignal(Process):
    """This process adds values to the current flux based on the values provided by the signal object.
    This class is typically invoked through the connector object

     Example::

     AddSignal(name = "name",
               reservoir = upstream_reservoir_handle,
               flux = flux_to_act_upon,
               lt = flux with lookup values)

     where - the upstream reservoir is the reservoir the process belongs too
             the flux is the flux to act upon
             lt= contains the flux object we lookup from

    """

    def __init__(self, **kwargs: Dict[str, any]) -> None:
        """
        Create a new process object with a given process type and options
        """

        # get default names and update list for this Process
        self.__defaultnames__()  # default kwargs names
        self.lrk.extend(["lt", "flux", "reservoir"])  # new required keywords

        self.__initerrormessages__()
        # self.bem.update({"rate": "a string"})
        self.__validateandregister__(kwargs)  # initialize keyword values

        # legacy variables
        self.mo = self.reservoir.mo
        self.__postinit__()  # do some housekeeping
        self.__register_name__()

        # defaults
        self.__execute__ = self.__add_with_fi__
        self.__get_process_args__ = self.__get_process_args_fi__

    # setup a placeholder call function
    def __call__(self, i: int):
        return self.__execute__(i)

    # use this when we do isotopes
    def __add_with_fi__(self, i) -> None:
        """Each process is associated with a flux (self.f). Here we replace
        the flux value with the value from the signal object which
        we use as a lookup-table (self.lt)

        Note that the signal may also specify a delta value. Thus we
        need to
        1) get the mass of flux + signal
        2) add the delta of flux and signal
        3) calculate the new li and hi

        """

        # add signal mass to flux mass
        r = self.f.species.r
        fm = self.f.m[i]  # flux rate
        fl = self.f.l[i]  # flux rate light isotope
        sm = self.lt.m[i]  # signal mass
        sl = self.lt.l[i]  # signal li

        # get signal delta
        if sm > 0:
            sd = 1000 * ((sm - sl) / sl - r) / r
        else:
            sd = 0
        # print(f"Signal delta = {sd}")

        if fm > 0:  # get flux delta
            fd = 1000 * ((fm - fl) / fl - r) / r + sd
        else:
            fd = sd

        fm += sm  # add signal mass
        fl = 1000.0 * fm / ((fd + 1000.0) * r + 1000.0)

        self.f.fa = np.array([fm, fl])
        # print(f"fa = {self.f.fa}\n")

    def __add_with_fa__(self, i) -> None:
        """same as above but use fa instead of flux data"""

        # add signal mass to flux mass
        r = self.f.species.r
        fm = self.f.fa[0]  # flux rate
        fl = self.f.fa[1]  # flux rate light isotope
        sm = self.lt.m[i]  # signal mass
        sl = self.lt.l[i]  # signal li

        # get signal delta
        sd = 1000 * ((sm - sl) / sl - r) / r

        if fm > 0:  # get flux delta
            fd = 1000 * ((fm - fl) / fl - r) / r + sd
        else:
            fd = sd

        # set new flux rate
        fm += sm  # add signal mass
        fl = 1000.0 * fm / ((fd + 1000.0) * r + 1000.0)

        self.f.fa = np.array([fm, fl])

    def get_process_args(self):
        return self.__get_process_args__()

    def __get_process_args_fi__(self):

        func_name: function = self.p_add_signal_fi

        print(f"flux_name = {self.flux.full_name}")

        data = List(
            [
                self.flux.m,  # 0
                self.flux.l,  # 1
                self.lt.m,  # 2
                self.lt.l,  # 3
                self.flux.fa,  # 4
            ]
        )

        params = List([float(self.reservoir.species.element.r)])

        return func_name, data, params

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_add_signal_fi(data, params, i) -> None:

        r: float = params[0]
        fm: float = data[0][i]  # fm
        fl: float = data[1][i]  # fl
        sm: float = data[2][i]  # sm
        sl: float = data[3][i]  # sd

        # get signal delta
        if sm > 0:
            sd = 1000 * ((sm - sl) / sl - r) / r
        else:
            sd = 0

        if fm > 0:  # get flux delta
            fd = 1000 * ((fm - fl) / fl - r) / r + sd
        else:
            fd = sd

        # set new flux rate
        fm += sm  # add signal mass
        fl = 1000.0 * fm / ((fd + 1000.0) * r + 1000.0)

        data[4][:] = [fm, fl]

    def __get_process_args_fa__(self):

        func_name: function = self.p_add_signal_fa

        print(f"flux_name = {self.flux.full_name}")

        data = List(
            [
                self.lt.m,  # 0
                self.lt.l,  # 1
                self.flux.fa,  #  2
            ]
        )

        params = List([float(self.reservoir.species.element.r)])

        return func_name, data, params

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_add_signal_fa(data, params, i) -> None:

        r: float = params[0]
        fm: float = data[2][0]
        fl: float = data[2][1]
        sm: float = data[0][i]
        sl: float = data[1][i]

        # get signal delta
        if sm > 0:
            sd = 1000 * ((sm - sl) / sl - r) / r
        else:
            sd = 0

        if fm > 0:  # get flux delta
            fd = 1000 * ((fm - fl) / fl - r) / r + sd
        else:
            fd = sd

        fm += sm  # add signal mass
        fl = 1000.0 * fm / ((fd + 1000.0) * r + 1000.0)
        data[2][:] = [fm, fl]


class SaveFluxData(Process):
    """
    This process stores the flux data from each iteration into a vector
    Example::

         SaveFluxData(name = "Name",
                   flux = Flux Handle
    )

    """

    __slots__ = "flux"

    def __init__(self, **kwargs: Dict[str, any]) -> None:
        """Initialize this Process"""
        # get default names and update list for this Process
        self.__defaultnames__()  # default kwargs names
        self.lrk.extend(["flux"])  # new required keywords

        self.__validateandregister__(kwargs)  # initialize keyword values

        # legacy variables
        self.__postinit__()  # do some housekeeping
        self.__register_name__()

    # setup a placeholder call function
    def __call__(self, i: int):

        self.f[i] = self.f.fa

    def get_process_args(self):
        """"""

        func_name: function = self.p_save_flux

        data = List(
            [
                self.flux.m,  # 0
                self.flux.l,  # 1
                # self.flux.h,  # 2
                # self.flux.d,  # 3
                self.flux.fa,  # 4 2
            ]
        )

        params = List([0.0, 0.0, 0.0])

        return func_name, data, params

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_save_flux(data, params, i) -> None:

        data[0][i] = data[2][0]
        data[1][i] = data[2][1]


class ScaleFlux(Process):
    """This process scales the mass of a flux (m,l,h) relative to another
    flux but does not affect delta. The scale factor "scale" and flux
    reference must be present when the object is being initalized

    Example::
         ScaleFlux(name = "Name",
                   reservoir = reservoir_handle (upstream or downstream)
                   scale = 1
                   ref_flux = flux we use for scale
                   )

    """

    __slots__ = ("rate", "scale", "ref_reservoirs", "reservoir", "flux")

    def __init__(self, **kwargs: Dict[str, any]) -> None:
        """Initialize this Process"""
        # get default names and update list for this Process
        self.__defaultnames__()  # default kwargs names
        self.lrk.extend(["reservoir", "flux", "scale"])  # new required keywords

        self.__validateandregister__(kwargs)  # initialize keyword values

        if "ref_reservoirs" in kwargs:
            self.ref_flux = kwargs["ref_reservoirs"]
        elif "ref_flux" in kwargs:
            pass
        else:
            raise ValueError("You need to specify a value for ref_flux")

        # legacy variables
        self.mo = self.reservoir.mo
        self.__postinit__()  # do some housekeeping
        self.__register_name__()

        # decide which call function to use
        # if self.mo.m_type == "both":
        if self.reservoir.isotopes:
            self.__execute__ = self.__with_isotopes__
        else:
            self.__execute__ = self.__without_isotopes__

    # setup a placeholder call function
    def __call__(self, i: int):
        return self.__execute__(i)

    def __with_isotopes__(self, i: int) -> None:
        """Apply the scale factor. This is typically done through the the
        model execute method.
        Note that this will use the mass of the flux we use for scaling, but that we will set the
        delta according to reservoir this flux derives from

        """

        # get reference flux
        m: float = self.ref_flux.fa[0] * self.scale
        r: float = self.reservoir.species.element.r

        # get the target isotope ratio based on upstream delta
        c = self.reservoir.l[i - 1] / (
            self.reservoir.m[i - 1] - self.reservoir.l[i - 1]
        )

        l: float = m * c / (c + 1)
        # h: float = m - l
        # d: float = self.reservoir.d[i - 1]

        # old self.flux[i]: np.array = [m, l, h, d]
        self.flux.fa = [m, l]

    def __without_isotopes__(self, i: int) -> None:
        """Apply the scale factor. This is typically done through the the
        model execute method.
        Note that this will use the mass of the reference object, but that we will set the
        delta according to the reservoir (or the flux?)

        """

        self.f.fa = np.array(
            [
                self.ref_flux.fa[0] * self.scale,
                0,
            ]
        )

    def get_process_args(self):
        """"""

        func_name: function = self.p_scale_flux

        data = List(
            [
                self.flux.m,  # 0
                self.flux.l,  # 1
                # self.flux.h,  # 2
                # self.flux.d,  # 3
                self.ref_flux.m,  # 4 2 Reference Flux
                self.reservoir.m,  # 5 3 Upstream reservoir
                self.reservoir.l,  # 6 4 Upstream reservoir li
                # self.reservoir.d,  # 7  Upstream reservoir d
                self.flux.fa,  # 8 5
                self.ref_flux.fa,  # 9 6
            ]
        )

        params = List([float(self.reservoir.species.element.r), float(self.scale)])

        return func_name, data, params

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_scale_flux(data, params, i) -> None:

        # params
        r: float = params[0]  # r value
        s: float = params[1]  # scale

        # data
        mf: float = data[6][0] * s  # mass of reference flux
        mr: float = data[3][i - 1]  # mass upstream reserevoir
        lr: float = data[4][i - 1]  # li upstream reserevoir

        # get the target isotope ratio based on upstream delta
        c = lr / (mr - lr)
        l = mf * c / (c + 1)

        # data[0][i] = mf
        # data[1][i] = l
        # data[2][i] = mf - l
        # data[3][i] = d
        data[5][:] = [mf, l]


class Fractionation(Process):
    """This process offsets the isotopic ratio of the flux by a given
       delta value. In other words, we add a fractionation factor

    Example::
         Fractionation(name = "Name",
                       reservoir = upstream_reservoir_handle,
                       flux = flux handle
                       alpha = 12 in permil (e.f)

    """

    __slots__ = ("flux", "reservoir")

    def __init__(self, **kwargs: Dict[str, any]) -> None:
        """Initialize this Process"""
        # get default names and update list for this Process
        self.__defaultnames__()  # default kwargs names
        self.lrk.extend(["reservoir", "flux", "alpha"])  # new required keywords

        self.__validateandregister__(kwargs)  # initialize keyword values
        self.__postinit__()  # do some housekeeping

        # alpha is given in permil, but the fractionation routine expects
        # it as 1 + permil, i.e., 70 permil would 1.007

        self.alp = 1 + self.alpha / 1000
        self.mo = self.reservoir.mo
        self.__register_name__()

    def __call__(self, i: int) -> None:
        """
        Set flux isotope masses based on fractionation factor
        relative to reserevoir

        """

        # print(f"self.f.m[i] =  {self.f.m[i]}")
        r = self.reservoir.species.element.r
        m = self.f.fa[0]
        if m != 0:
            # get target ratio based on reservoir ratio
            c = (
                self.reservoir.l[i - 1]
                / (self.reservoir.m[i - 1] - self.reservoir.l[i - 1])
            ) / self.alp

            l = m * c / (c + 1)
            # h = m - l
            # d = 1000 * (h / l - r) / r

            self.f.fa = [m, l]
        else:
            self.f.fa = [
                0,
                0,
            ]

        return

    def get_process_args(self):

        func_name: function = self.p_fractionation

        data = List(
            [
                self.flux.m,  # 0
                self.flux.l,  # 1
                # self.flux.h,  # 2
                # self.flux.d,  # 3
                self.reservoir.m,  # 4 2
                self.reservoir.l,  # 5 3
                self.flux.fa,  # 6 4
            ]
        )
        params = List([float(self.reservoir.species.element.r), float(self.alp)])

        return func_name, data, params

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_fractionation(data, params, i) -> None:
        # params
        r: float = params[0]  # rvalue
        a: float = params[1]  # alpha

        # data
        fm: float = data[4][0]  # flux mass
        rm: float = data[2][i - 1]  # 4 reservoir mass
        rl: float = data[3][i - 1]  # 4 reservoir light isotope

        c = (rl / (rm - rl)) / a
        fl = fm * c / (c + 1)  # flux li
        # fh = fm - fl  # flux hi
        # fd = 1000 * (fh / fl - r) / r  # flux d

        data[4][:] = [fm, fl]


class RateConstant(Process):
    """This is a wrapper for a variety of processes which depend on rate constants
    Please see the below class definitions for details on how to call them
    At present, the following processes are defined



    """

    __slots__ = ("scale", "ref_value", "k_value", "flux", "reservoir")

    def __init__(self, **kwargs: Dict[str, any]) -> None:
        """Initialize this Process"""

        from . import ureg, Q_
        from .connections import SourceGroup, SinkGroup, ReservoirGroup
        from .connections import ConnectionGroup, GasReservoir
        from esbmtk import Flux

        # Note that self.lkk values also need to be added to the lkk
        # list of the connector object.

        # get default names and update list for this Process
        self.__defaultnames__()  # default kwargs names

        # update the allowed keywords
        self.lkk: dict = {
            "scale": (Number, np.float64),
            "k_value": (Number, np.float64),
            "name": str,
            "reservoir": (Reservoir, Source, Sink, GasReservoir, np.ndarray),
            "flux": Flux,
            "ref_reservoirs": list,
            "reservoir_ref": (Reservoir, GasReservoir),
            "left": (list, Reservoir, Number, np.float64, np.ndarray),
            "right": (list, Reservoir, Number, np.ndarray),
            "register": (
                SourceGroup,
                SinkGroup,
                ReservoirGroup,
                ConnectionGroup,
                Flux,
                str,
            ),
            "gas": (Reservoir, GasReservoir, Source, Sink, np.ndarray),
            "liquid": (Reservoir, Source, Sink),
            "solubility": (Number, np.float64),
            "piston_velocity": (Number, np.float64),
            "water_vapor_pressure": (Number, np.float64),
            "ref_species": np.ndarray,
            "seawaterconstants": any,
            "isotopes": bool,
            "function_reference": any,
            "f_0": (str),
            "pco2_0": (str),
            "ex": Number,
        }

        # new required keywords
        self.lrk.extend([["reservoir", "atmosphere"], ["scale", "k_value"]])

        # dict with default values if none provided
        # self.lod = {r
        self.lod: dict = {"isotopes": False, "function_reference": "None"}

        self.__initerrormessages__()

        # add these terms to the known error messages
        self.bem.update(
            {
                "scale": "a number",
                "reservoir": "Reservoir handle",
                "ref_reservoirs": "List of Reservoir handle(s)",
                "ref_value": "a number or flux quantity",
                "name": "a string value",
                "flux": "a flux handle",
                "left": "list, reservoir or number",
                "right": "list, reservoir or number",
                "function_reference": "A function reference",
            }
        )

        # initialize keyword values
        self.__validateandregister__(kwargs)
        if "reservoir" in kwargs:
            self.mo = self.reservoir.mo
        elif "gas_reservoir" in kwargs:
            self.mo = self.gas_reservoir

        self.__misc_init__()
        self.__postinit__()  # do some housekeeping
        # legacy variables

        self.__register_name__()

        if self.reservoir.isotopes or self.isotopes:
            self.__execute__ = self.__with_isotopes__
        else:
            self.__execute__ = self.__without_isotopes__

    def __postinit__(self) -> "None":
        self.mo = self.reservoir.mo

    # setup a placeholder call function
    def __call__(self, i: int):
        return self.__execute__(i)


class weathering(RateConstant):
    """This process calculates the flux as a function of the upstream
     reservoir concentration C and a constant which describes thet
     strength of relation between the reservoir concentration and
     the flux scaling

     F = f_0 * (scale * C/pco2_0)**ncc

     where C denotes the concentration in the ustream reservoir, k is a
     constant. This process is typically called by the connector
     instance. However you can instantiate it manually as

     weathering(
                       name = "Name",
                       reservoir = upstream_reservoir_handle,
                       reservoir_ref = reference_reservoir (Atmosphere)
                       flux = flux handle,
                       ex = exponent
                       pco2_0 = 280,
                       f_0 = 12 / 17e12
                       Scale =  1000,
    )

    """

    def __misc_init__(self):
        """
        Scale the reference flux into the model flux units
        """

        self.f_0: float = Q_(self.f_0).to(self.mo.f_unit).magnitude
        self.pco2_0 = Q_(self.pco2_0).to("ppm").magnitude * 1e-6

    def __without_isotopes__(self, i: int) -> None:

        f = (
            self.f_0
            * (self.scale * self.reservoir_ref.c[i - 1] / self.pco2_0) ** self.ex
        )
        self.flux.fa = [f, 0]

    def __with_isotopes__(self, i: int) -> None:
        """
        C = M/V so we express this as relative to mass which allows us to
        use the isotope data.

        The below calculates the flux as function of reservoir concentration,
        rather than scaling the flux.
        """

        raise NotImplementedError("weathering has currently no isotope method")
        # c: float = self.reservoir.c[i - 1]
        # if c > 0:  # otherwise there is no flux
        #     m = c * self.scale
        #     r: float = reservoir.species.element.r
        #     d: float = reservoir.d[i - 1]
        #     l: float = (1000.0 * m) / ((d + 1000.0) * r + 1000.0)
        #     self.flux[i]: np.array = [m, l, m - l, d]

    def get_process_args(self):

        func_name: function = self.p_weathering

        data = List(
            [
                self.flux.m,  # 0
                self.flux.l,  # 1
                # self.flux.h,  # 2
                # self.flux.d,  # 3
                # self.reservoir_ref.d,  # 4
                self.reservoir_ref.c,  # 5 2
                self.reservoir_ref.m,  # 6 3
                self.flux.fa,  # 7 4
            ]
        )
        params = List(
            [
                float(self.reservoir.species.element.r),  # 0
                float(self.scale),  # 1
                float(self.f_0),  # 2
                float(self.pco2_0),  # 3
                float(self.ex),  # 4
            ]
        )

        return func_name, data, params

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_weathering(data, params, i) -> None:
        # concentration times scale factor
        s: float = params[1]
        f_0: float = params[2]
        pco2_0: float = params[3]
        ex: float = params[4]

        c: float = data[2][i - 1]
        f: float = f_0 * (c * s / pco2_0) ** ex
        data[4][:] = [f, 0]


class ScaleRelativeToConcentration(RateConstant):
    """This process calculates the flux as a function of the upstream
     reservoir concentration C and a constant which describes thet
     strength of relation between the reservoir concentration and
     the flux scaling

     F = C * k

     where C denotes the concentration in the ustream reservoir, k is a
     constant. This process is typically called by the connector
     instance. However you can instantiate it manually as

     ScaleRelativeToConcentration(
                       name = "Name",
                       reservoir= upstream_reservoir_handle,
                       flux = flux handle,
                       Scale =  1000,
    )

    """

    def __without_isotopes__(self, i: int) -> None:
        m: float = self.reservoir.m[i - 1]
        if m > 0:  # otherwise there is no flux
            # convert to concentration
            c = m / self.reservoir.volume
            f = c * self.scale
            self.flux.fa = [
                f,
                0,
            ]

    def __with_isotopes__(self, i: int) -> None:
        """
        C = M/V so we express this as relative to mass which allows us to
        use the isotope data.

        The below calculates the flux as function of self.reservoir concentration,
        rather than scaling the flux.
        """

        rc: float = self.reservoir.c[i - 1]
        if rc > 0:  # otherwise there is no flux
            r: float = self.reservoir.species.element.r
            c = self.reservoir.l[i - 1] / (
                self.reservoir.m[i - 1] - self.reservoir.l[i - 1]
            )
            m = rc * self.scale
            l = m * c / (c + 1)
            # d = self.reservoir.d[i - 1]
            self.f.fa = [m, l]

    def get_process_args(self):

        func_name: function = self.p_scale_relative_to_concentration

        data = List(
            [
                self.flux.m,  # 0
                self.flux.l,  # 1
                # self.flux.h,  # 2
                # self.flux.d,  # 3
                # self.reservoir.d,  # 4
                self.reservoir.c,  # 5 2
                self.reservoir.m,  # 6 3
                self.reservoir.l,  # 7 4
                self.flux.fa,  # 8 5
            ]
        )
        params = List(
            [
                float(self.reservoir.species.element.r),
                float(self.scale),
                float(self.reservoir.volume),
            ]
        )

        return func_name, data, params

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_scale_relative_to_concentration(data, params, i) -> None:

        # params
        r: float = params[0]  # r
        s: float = params[1]  # scale factor
        v: float = params[2]  # res volume

        # # data 0 to 3 = flux data
        # rd: float = data[4][i - 1]  # res delta
        rc: float = data[2][i - 1]  # res concentration
        rm: float = data[3][i - 1]  # res mass
        rl: float = data[4][i - 1]  # res li

        if rc > 0:
            m: float = rc * s
            c: float = rl / (rm - rl)
            l: float = m * c / (c + 1)
            data[5][:] = [m, l]

        else:
            data[5][:] = [0.0, 0.0]


class ScaleRelativeToMass(RateConstant):
    """This process scales the flux as a function of the upstream
     reservoir Mass M and a constant which describes the
     strength of relation between the reservoir mass and
     the flux scaling

     F = F0 *  M * k

     where M denotes the mass in the ustream reservoir, k is a
     constant and F0 is the initial unscaled flux. This process is
     typically called by the connector instance. However you can
     instantiate it manually as

     Note that we scale the flux, rather than compute the flux!

     This is faster than setting a new flux, computing the isotope
     ratio and setting delta. So you either have to set the initial
     flux F0 to 1, or calculate the scale accordingly

     ScaleRelativeToMass(
                       name = "Name",
                       reservoir= upstream_reservoir_handle,
                       flux = flux handle,
                       Scale =  1000,
    )

    """

    def __without_isotopes__(self, i: int) -> None:
        m: float = self.reservoir.m[i - 1] * self.scale
        self.flux.fa = [m, 0, 0, 0]

    def __with_isotopes__(self, i: int) -> None:
        """
        this will be called by the Model.run() method

        """
        m: float = self.reservoir.m[i - 1] * self.scale
        r: float = self.reservoir.species.element.r
        # d: float = self.reservoir.d[i - 1]
        c = self.reservoir.l[i - 1] / (
            self.reservoir.m[i - 1] - self.reservoir.l[i - 1]
        )
        l = m * c / (c + 1)
        self.flux.fa = [m, l]

    def get_process_args(self):
        """return the data associated with this object"""

        func_name: function = self.p_scale_relative_to_mass

        data = List(
            [
                self.flux.m,  # 0
                self.flux.l,  # 1
                # self.flux.h,  # 2
                # self.flux.d,  # 3
                self.reservoir.m,  # 4 2
                self.reservoir.l,  # 5 3
                # self.reservoir.d,  # 6
                self.flux.fa,  # 7 4
            ]
        )

        params = List([float(self.reservoir.species.element.r), float(self.scale)])

        return func_name, data, params

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_scale_relative_to_mass(data, params, i) -> None:
        # concentration times scale factor

        # params
        r: float = params[0]  # r values
        s: float = params[1]  # scale factor

        # data
        rm = data[2][i - 1]
        rl = data[3][i - 1]
        # rd = data[6][i - 1]

        m: float = rm * s  # new flux
        c: float = rl / (rm - rl)
        l: float = m * c / (c + 1)
        # d: float = data[1][i - 1]  # flux delta

        data[4][:] = [m, l]


# class ScaleRelative2otherReservoir(RateConstant):
#     """This process scales the flux as a function one or more reservoirs
#     constant which describes the
#     strength of relation between the reservoir concentration and
#     the flux scaling

#     F = C1 * C1 * k

#     where Mi denotes the concentration in one  or more reservoirs, k is one
#     or more constant(s). This process is typically called by the connector
#     instance when you specify the connection as

#     Connect(source =  upstream reservoir,
#               sink = downstream reservoir,
#               ctype = "scale_relative_to_multiple_reservoirs"
#               ref_reservoirs = [r1, r2, k etc] # you must provide at least one
#                                                # reservoir or constant
#               scale = a overall scaling factor
#            )
#     """

#     def __misc_init__(self) -> None:
#         """Test that self.reservoir only contains numbers and reservoirs"""

#         self.rs: list = []
#         self.constant: Number = 1

#         for r in self.ref_reservoirs:
#             if isinstance(r, (Reservoir)):
#                 self.rs.append(r)
#             elif isinstance(r, (Number)):
#                 self.constant = self.constant * r
#             else:
#                 raise ValueError(f"{r} must be reservoir or number, not {type(r)}")

#     def __without_isotopes__(self, i: int) -> None:
#         c: float = 1
#         for r in self.rs:
#             c = c * r.c[i - 1]

#         scale: float = c * self.scale * self.constant

#         # scale = scale * (scale >= 0)  # prevent negative fluxes.
#         self.f[i] = [scale, scale, scale, 1]

#     def __with_isotopes__(self, i: int) -> None:
#         """
#         not sure that this correct WRT isotopes

#         """

#         raise NotImplementedError(
#             "Scale relative to multiple reservoirs is undefined for isotope calculations"
#         )

#         # c: float = 1
#         # for r in self.rs:
#         #     c = c * r.c[i - 1]

#         # scale: float = c * self.scale * self.constant

#         # # scale = scale * (scale >= 0)  # prevent negative fluxes.
#         # self.f[i] = [scale, scale, scale, 1]


class GasExchange(RateConstant):
    """

    GasExchange(
          gas =GasReservoir, #
          liquid = Reservoir, #,
          ref_species = array of concentrations #
          solubility=Atmosphere.swc.SA_co2 [mol/(m^3 atm)],
          area = area, # m^2
          piston_velocity = m/year
          seawaterconstants = Ocean.swc
          water_vapor_pressure=Ocean.swc.p_H2O,
    )


    """

    # redefine misc_init which is being called by post-init
    def __misc_init__(self):
        """Set up input variables"""

        self.p_H2O = self.seawaterconstants.p_H2O
        self.a_dg = self.seawaterconstants.a_dg
        self.a_db = self.seawaterconstants.a_db
        self.a_u = self.seawaterconstants.a_u
        self.rvalue = self.liquid.sp.r
        self.volume = self.gas.volume

    def __without_isotopes__(self, i: int) -> None:

        # set flux
        # note that the sink delta is co2aq as returned by the carbonate VR
        # this equation is for mmol but esbmtk uses mol, so we need to
        # multiply by 1E3

        a = self.scale * (  # area in m^2
            self.gas.c[i - 1]  #  Atmosphere
            * (1 - self.p_H2O)  # p_H2O
            * self.solubility  # SA_co2 = mol/(m^3 atm)
            - self.ref_species[i - 1] * 1000  # [CO2]aq mol
        )
        # print(self.gas.c[i - 1])

        # changes in the mass of CO2 also affect changes in the total mass
        # of the atmosphere. So we need to update the reservoir volume
        # variable which we use the store the total atmospheric mass
        reservoir.v[i] = reservoir.v[i] + a * reservoir.mo.dt
        # self.flux[i] = [a, 1, 1, 1]
        self.flux.fa = [a, 1]

    def __with_isotopes__(self, i: int) -> None:
        """
        In the following I assume near neutral pH between 7 and 9, so that
        the isotopic composition of HCO3- is approximately equal to the isotopic
        ratio of DIC. The isotopic ratio of [CO2]aq can then be obtained from DIC via
        swc.e_db (swc.a_db)

        The fractionation factor subscripts denote the following:

        g = gaseous
        d = dissolved
        b = bicarbonate ion
        c = carbonate ion

        a_db is thus the fractionation factor between dissolved CO2aq and HCO3-
        and a_gb between CO2g HCO3-
        """

        f = self.scale * (
            self.gas.c[i - 1]  # p Atmosphere
            * (1 - self.p_H2O)  # p_H2O
            * self.solubility  # SA_co2
            - self.ref_species[i - 1] * 1000  # [CO2]aq
        )

        # this seems backward, -> fix
        co2aq_c13 = (
            self.ref_species[i - 1] * self.r.m[i - 1]
            - self.r.l[i - 1] / self.r.m[i - 1]
        )
        gh = self.gas.m[i - 1] - self.gas.l[i - 1]
        co2at_c13 = self.gas.m[i - 1] - gh / self.gas.volume

        f13 = (
            self.scale
            * self.a_u
            * (
                self.a_dg
                * co2at_c13
                * (1 - self.p_H2O)  # p_H2O
                * self.solubility  # SA_co2
                - self.a_db * co2aq_c13 * 1000
            )
        )

        # h = flux!
        f12 = f - f13
        # d = (f13 / f12 / self.rvalue - 1) * 1000

        # print(f"f={f:.2e}")
        # print(f"P: f={f:.2e}, f12={f12:.2e}, f13={f13:.2e}, d={d:.2f}")
        self.flux.fa[0:2] = [f, f12]
        self.reservoir.v[i] = self.reservoir.v[i] + f * self.reservoir.mo.dt

    def __postinit__(self) -> None:
        """Do some housekeeping for the process class"""

        # legacy name aliases
        self.n: str = self.name  # display name of species
        self.r = self.liquid
        self.reservoir = self.liquid

    def get_process_args(self):
        """return the data associated with this object"""

        func_name: function = self.p_gas_exchange

        data = List(
            [
                self.flux.fa,  # 0
                self.liquid.m,  # 1
                self.liquid.l,  # 2
                self.gas.m,  # 3
                self.gas.l,  # 4
                self.gas.c,  # 5
                self.gas.v,  # 6
                self.r.m,  # 7
                self.r.l,  # 8
                self.ref_species,  # 9
            ]
        )

        params = List(
            [
                float(self.scale),  # 0
                float(self.solubility * (1 - self.p_H2O)),  # 1
                float(self.rvalue),  # 2
                float(self.gas.volume),  # 3
                float(self.a_u),  # 4
                float(self.a_dg),  # 5
                float(self.a_db),  # 6
                float(self.reservoir.mo.dt),  # 7
                float(self.p_H2O),  # 8
                float(self.solubility),  # 9
            ]
        )

        self.params = params
        return func_name, data, params

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_gas_exchange(data, params, i) -> None:
        """the below equation moved as many constants as possible outside of
        the function compared to the __with/without_isotopes__ method(s). See the
        __get_process_args__ method for details

        """

        scale: float = params[0]  # scale
        SA: float = params[1]  # solubility
        r: float = params[2]  # r value
        gv: float = params[3]  # gas volume
        au: float = params[4]  #
        dg: float = params[5]  #
        db: float = params[6]  #
        dt: float = params[7]  # dt
        pH2O: float = params[8]  # p_H2O
        solubility: float = params[9]  # solubility

        lm = data[1][i - 1]
        ll = data[2][i - 1]
        gm = data[3][i - 1]
        gl = data[4][i - 1]
        gc = data[5][i - 1]
        gv = data[6][i - 1]
        rm = data[7][i - 1]
        rl = data[8][i - 1]
        rs = data[9][i - 1]
        gh = gm - gl  # gas.h
        rh = rm - rl

        f = scale * (gc * (1 - pH2O) * solubility - rs * 1000)
        co2aq_c13 = rs * rh / rm  #
        co2at_c13 = gh / gv

        f13 = (
            scale
            * au
            * (dg * co2at_c13 * (1 - pH2O) * solubility - db * co2aq_c13 * 1000)
        )
        f12 = f - f13
        data[0][:] = [f, f12]  # fa
        # fix: verifyf that this works?
        # data[6][i] = data[6][i - 1] + f * dt  # gas volume


class VarDeltaOut(Process):
    """Unlike a passive flux, this process sets the flux istope ratio
    equal to the isotopic ratio of the reservoir. The
    init and register methods are inherited from the process
    class.
    VarDeltaOut(name = "name",
                reservoir = upstream_reservoir_handle,
                flux = flux handle,
                rate = rate,)
    """

    __slots__ = ("rate", "flux", "reservoir")

    def __init__(self, **kwargs: Dict[str, any]) -> None:
        """Initialize this Process"""

        from . import ureg, Q_
        from .connections import ConnectionGroup
        from esbmtk import Flux, Reservoir, ReservoirGroup

        # get default names and update list for this Process
        self.__defaultnames__()
        self.lkk: Dict[str, any] = {
            "name": str,
            "reservoir": (Reservoir, Source, Sink),
            "flux": Flux,
            "rate": (str, Q_),
            "register": (ConnectionGroup, ReservoirGroup, Reservoir, Flux, str),
            "scale": (Number, np.float64, str),
        }
        self.lrk.extend(["reservoir", "flux"])  # new required keywords
        self.__initerrormessages__()
        self.__validateandregister__(kwargs)  # initialize keyword values
        self.mo = self.reservoir.mo
        self.__postinit__()  # do some housekeeping
        self.__register_name__()

        # decide which call function to use
        # if self.mo.m_type == "both":
        if self.reservoir.isotopes:
            # print(
            #    f"vardeltaout with isotopes for {self.reservoir.register.name}.{self.reservoir.name}"
            # )
            if isinstance(self.reservoir, Reservoir):
                # print("Using reservoir")
                self.__execute__ = self.__with_isotopes_reservoir__
            elif isinstance(self.reservoir, Source):
                # print("Using Source")
                self.__execute__ = self.__with_isotopes_source__
            else:
                raise ValueError(
                    f"{self.name}, reservoir must be of type Source or Reservoir, not {type(self.reservoir)}"
                )
        else:
            self.__execute__ = self.__without_isotopes__

    # setup a placeholder call function
    def __call__(self, i: int):
        return self.__execute__(i)

    def __with_isotopes_reservoir__(self, i: int) -> None:
        """Here we re-balance the flux. This code will be called by the
        apply_flux_modifier method of a reservoir which itself is
        called by the model execute method
        """

        m: float = self.flux.m[i]
        if m != 0:
            c = self.reservoir.l[i - 1] / (
                self.reservoir.m[i - 1] - self.reservoir.l[i - 1]
            )
            self.flux.fa = [m, m * c]

    def get_process_args(self):
        """Provide the data structure which needs to be passed to the numba solver"""

        # if upstream is a source, we only have a single delta value
        # so we need to patch this. Maybe this should move to source?

        func_name: function = self.p_vardeltaout

        data = List(
            [
                self.flux.m,  # 0
                # self.flux.l,  # 1
                # self.flux.h,  # 2
                # self.flux.d,  # 3
                # delta,  # 4
                self.reservoir.m,  # 1
                self.reservoir.l,  # 2
                self.flux.fa,  # 5 3
            ]
        )

        params = List([float(reservoir.species.element.r)])

        return func_name, data, params

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_vardeltaout(data, params, i) -> None:
        # concentration times scale factor

        mf: float = data[0][i - 1]  # flux mass
        mr: float = data[1][i - 1]  # reservoir mass
        lr: float = data[2][i - 1]  # reservoir l

        c = lr / (mr - lr)
        data[3][:] = [mf, mf * c]

    def __with_isotopes_source__(self, i: int) -> None:
        """If the source of the flux is a source, there is only a single delta value.
        Changes to the flux delta are applied through the Signal class.
        """

        m: float = self.flux.m[i]
        if m != 0:
            c = self.reservoir.l[i - 1] / (
                self.reservoir.m[i - 1] - self.reservoir.l[i - 1]
            )
            self.flux.fa = [m, m * c]

    def __without_isotopes__(self, i: int) -> None:
        """Here we re-balance the flux. This code will be called by the
        apply_flux_modifier method of a reservoir which itself is
        called by the model execute method
        """

        raise NotImplementedError("vardeltaout w/o isotopes is not defined")


class MultiplySignal(Process):
    """This process mulitplies a given flux with the the data in the
    signal.  This class is typically invoked through the connector
    object: Note that this process will not modify the delta value of
    a given flux.  If you needto vary the delta value it is best to
    add a second signal which uses the add signal type.

     Example::
     MultiplySignal(name = "name",
               reservoir = upstream_reservoir_handle,
               flux = flux_to_act_upon,
               lt = flux with lookup values)

     where the upstream reservoir is the reservoir the process belongs
             too the flux is the flux to act upon lt= contains the
             flux object we lookup from

    """

    def __init__(self, **kwargs: Dict[str, any]) -> None:
        """
        Create a new process object with a given process type and options
        """

        # get default names and update list for this Process
        self.__defaultnames__()  # default kwargs names
        self.lrk.extend(["lt", "flux", "reservoir"])  # new required keywords

        self.__initerrormessages__()
        # self.bem.update({"rate": "a string"})
        self.__validateandregister__(kwargs)  # initialize keyword values

        # legacy variables
        self.mo = self.reservoir.mo
        self.__postinit__()  # do some housekeeping
        self.__register_name__()

        # decide whichh call function to use
        # if self.mo.m_type == "both":

        # default
        self.__execute__ = self.__multiply_with_flux_fi__
        self.__get_process_args__ = self.__get_process_args_fi__

    # setup a placeholder call function
    def __call__(self, i: int):
        return self.__execute__(i)

    # use this when we do isotopes
    def __multiply_with_flux_fi__(self, i) -> None:
        """Each process is associated with a flux (self.f). Here we replace
        the flux value with the value from the signal object which
        we use as a lookup-table (self.lt)
        """

        # multiply flux mass with signal
        c = self.lt.m[i]
        m = self.f.m[i] * c
        l = self.f.l[i] * c
        # h = self.f.h[i] * c
        # d = self.f.d[i]
        self.flux.fa = np.array([m, l])
        print(f"multiply fa {self.flux.fa}, f. = {self.f.m[i]}, c = {c} ")

    def __multiply_with_flux_fa__(self, i) -> None:
        """Each process is associated with a flux (self.f). Here we replace
        the flux value with the value from the signal object which
        we use as a lookup-table (self.lt)
        """

        # multiply flux mass with signal
        c = self.lt.m[i]
        m = self.f.fa[0] * c
        l = self.f.fa[1] * c
        self.flux.fa = np.array([m, l])

    def __get_process_args_fi__(self):
        func_name: function = self.p_multiply_signal_fi
        data = List(
            [
                self.flux.m,  # 0
                self.flux.l,  # 1
                # self.lt.l,  # 2
                # self.flux.d,  # 3
                self.lt.m,  # 2
                self.flux.fa,  # 3
            ]
        )
        params = List([float(self.reservoir.species.element.r)])

        return func_name, data, params

    def __get_process_args_fa__(self):
        func_name: function = self.p_multiply_signal_fa
        data = List(
            [
                self.lt.m,  # 0
                self.flux.fa,  # 1
            ]
        )
        params = List([float(self.reservoir.species.element.r)])

        return func_name, data, params

    def get_process_args(self):

        return self.__get_process_args__()

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_multiply_signal_fi(data, params, i) -> None:

        r = params[0]

        c = data[2][i]
        m = data[0][i] * c
        l = data[1][i] * c

        data[3][:] = [m, l]

    @staticmethod
    @njit(fastmath=True, error_model="numpy")
    def p_multiply_signal_fa(data, params, i) -> None:

        r = params[0]

        c = data[0][i]
        m = data[1][0] * c  # m
        l = data[1][1] * c  # l

        data[1][:] = [m, l]
