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

     This module defines some shared methods

"""
from __future__ import annotations
import time
import numpy as np

# import typing as tp

# if tp.TYPE_CHECKING:
#     from .esbmtk import Model


class input_parsing(object):
    """Provides various routines to parse and process keyword
    arguments.  All derived classes need to declare the allowed
    keyword arguments, their defualt values and the type in the
    following format:

    defaults = {"key": [value, (allowed instances)]

    the recommended sequence is to first set default values via
    __register_variable_names__()

    __update_dict_entries__(defaults,kwargs) will  compare the provided kwargs against
    this data, and upon succesful parsing update the default dict
    with the new values
    """

    def __init__(self):
        raise NotImplementedError("input parsing has no instance!")

    def __initialize_keyword_variables__(self, kwargs) -> None:
        """check, register and update keyword variables"""

        self.update = False
        self.__check_mandatory_keywords__(self.lrk, kwargs)
        self.__register_variable_names__(self.defaults, kwargs)
        self.__update_dict_entries__(self.defaults, kwargs)
        self.update = True

    def __check_mandatory_keywords__(self, lrk: list, kwargs: dict) -> None:
        """Verify that all elements of lrk have a corresponding key in
        kwargs.  If not, print error message"""

        for key in lrk:
            if isinstance(key, list):
                has_key = 0
                for k in key:
                    if k in kwargs and kwargs[k] != "None":
                        has_key += 1
                if has_key != 1:
                    raise ValueError(f"give only one of {key}")
            else:
                if key not in kwargs:
                    raise ValueError(f"{key} is a mandatory keyword")

    def __register_variable_names__(
        self,
        defaults: dict[str, list[any, tuple]],
        kwargs: dict,
    ) -> None:
        """Register the key value[0] pairs as local instance variables.
        We register them with their actual variable name and as _variable_name
        in case we use setter and getter methods.
        to avoid name conflicts.
        """
        for key, value in defaults.items():
            setattr(self, "_" + key, value[0])
            setattr(self, key, value[0])

        # save kwargs dict
        self.kwargs: dict = kwargs

    def __update_dict_entries__(
        self,
        defaults: dict[str, list[any, tuple]],
        kwargs: dict[str, list],
    ) -> None:
        """This function compares the kwargs dictionary with the defaults
        dictionary. If the kwargs key cannot be found, raise an
        error. Otherwise test that the value is of the correct type. If
        yes, update the defaults dictionary with the new value.

        defaults = {"key": [value, (allowed instances)]
        kwargs = {"key": value

        Note that this function assumes that all defaults have been registered
        with the instance via __register_variable_names__()
        """
        for key, value in kwargs.items():
            if key not in defaults:
                raise ValueError(f"{key} is not a valid key")

            if not isinstance(value, defaults[key][1]):
                raise TypeError(
                    f"{value} for {key} must be of type {defaults[key][1]}, not {type(value)}"
                )

            defaults[key][0] = value  # update defaults dictionary
            setattr(self, key, value)  # update instance variables
            setattr(self, "_" + key, value)  # and their property shadows

    def __register_name_new__(self) -> None:
        """if self.parent is set, register self as attribute of self.parent,
        and set full name to parent.full-name + self.name
        if self.parent == "None", full_name = name
        """

        if self.parent == "None":
            self.full_name = self.name
            reg = self
        else:
            self.full_name = self.parent.full_name + "." + self.name
            reg = self.parent.model
            # check for naming conflicts
            if self.full_name in reg.lmo:
                raise NameError(f"{self.full_name} is a duplicate name in reg.lmo")
            else:
                # register with model
                reg.lmo.append(self.full_name)
                reg.lmo2.append(self)
                reg.dmo.update({self.full_name: self})
                setattr(self.parent, self.name, self)
                self.kwargs["full_name"] = self.full_name
        self.reg_time = time.monotonic()


class esbmtkBase(input_parsing):
    """The esbmtk base class template. This class handles keyword
    arguments, name registration and other common tasks

    Useful methods in this class:

    define required keywords in lrk dict:
       self.lrk: list = ["name"]

    define allowed type per keyword in lkk dict:
       self.defaults: dict[str, list[any, tuple]] = {
                                  "name": ["None", (str)],
                                  "model": ["None",(str, Model)],
                                  "salinity": [35, (int, float)], # int or float
                                  }

    parse and register all keywords with the instance
    self.__initialize_keyword_variables__(kwargs)

    register the instance
    self.__register_name_new__ ()

    """

    def __init__(self) -> None:
        raise NotImplementedError

    def __repr__(self, log=0) -> str:
        """Print the basic parameters for this class when called via the print method"""
        from esbmtk import Q_

        m: str = ""

        # suppress output during object initialization
        tdiff = time.monotonic() - self.reg_time

        # do not echo input unless explicitly requestted

        m = f"{self.__class__.__name__}(\n"
        for k, v in self.kwargs.items():
            if not isinstance({k}, esbmtkBase):
                # check if this is not another esbmtk object
                if "esbmtk" in str(type(v)):
                    m = m + f"    {k} = {v.name},\n"
                # if this is a string
                elif isinstance(v, str):
                    m = m + f"    {k} = '{v}',\n"
                # if this is a quantity
                elif isinstance(v, Q_):
                    m = m + f"    {k} = '{v}',\n"
                # if this is a list
                elif isinstance(v, (list, np.ndarray)):
                    m = m + f"    {k} = '{v[0:3]}',\n"
                # all other cases
                else:
                    m = m + f"    {k} = {v},\n"

        m = m + ")"

        if log == 0 and tdiff < 1:
            m = ""

        return m

    def __str__(self, kwargs={}):
        """Print the basic parameters for this class when called via the print method
        Optional arguments

        indent :int = 0 printing offset

        """
        from esbmtk import Q_

        m: str = ""
        off: str = "  "

        if "indent" in kwargs:
            ind: str = kwargs["indent"] * " "
        else:
            ind: str = ""

        if "index" in kwargs:
            index = int(kwargs["index"])
        else:
            index = -2

        m = f"{ind}{self.name} ({self.__class__.__name__})\n"
        for k, v in self.kwargs.items():
            if not isinstance({k}, esbmtkBase):
                # check if this is not another esbmtk object
                if "esbmtk" in str(type(v)):
                    pass
                elif isinstance(v, str) and not (k == "name"):
                    m = m + f"{ind}{off}{k} = {v}\n"
                elif isinstance(v, Q_):
                    m = m + f"{ind}{off}{k} = {v}\n"
                elif isinstance(v, np.ndarray):
                    m = m + f"{ind}{off}{k}[{index}] = {v[index]:.2e}\n"
                elif k != "name":
                    m = m + f"{ind}{off}{k} = {v}\n"

        return m

    def __lt__(self, other) -> None:
        """This is needed for sorting with sorted()"""

        return self.n < other.n

    def __gt__(self, other) -> None:
        """This is needed for sorting with sorted()"""

        return self.n > other.n

    def info(self, **kwargs) -> None:
        """Show an overview of the object properties.
        Optional arguments are

        indent :int = 0 indentation

        """

        if "indent" not in kwargs:
            indent = 0
            ind = ""
        else:
            indent = kwargs["indent"]
            ind = " " * indent

        # print basic data bout this object
        print(f"{ind}{self.__str__(kwargs)}")

    def __aux_inits__(self) -> None:
        """Aux initialization code. Not normally used"""

        pass
