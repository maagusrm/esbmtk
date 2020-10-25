
# Table of Contents

1.  [ESBMTK - An Earth-sciences box modeling toolkit](#org373a2a8)
2.  [News](#org3df6763)
3.  [Installation](#orgf1a1a4f)
4.  [Documentation](#org32d5f79)
5.  [License](#orgc1b3613)


<a id="org373a2a8"></a>

# ESBMTK - An Earth-sciences box modeling toolkit

ESBMTK is python library which aims to simplify typical box modeling
projects the in Earth-Sciences. The focus of this project is to make
box modeling more approachable for classroom teaching. So performance
and scalability are not great.

At present, it will calculate masses/concentrations in reservoirs and
fluxes including isotope ratios. It provides a variety of classes
which allow the creation and manipulation of input signals, and the
generation of graphical result. There is however no support for
chemical reactions (including equilibrium reactions).


<a id="org3df6763"></a>

# News

-   Oct. 25<sup>th</sup>, Initial release on github.


<a id="orgf1a1a4f"></a>

# Installation

ESBMTK relies on the following python versions and libraries

-   python > 3.5
-   matplotlib
-   numpy
-   pandas
-   logging
-   nptyping

please install the above with pip or conda etc. 

At present, there is no ready made installation routine. Rather
download the `esbmtk.py` library into your local working library using
one of the following commands

-   <https://github.com/uliw/esbmtk/archive/main.zip>
-   <https://github.com/uliw/esbmtk.git>
-   git@github.com:uliw/esbmtk.git


<a id="org32d5f79"></a>

# Documentation

See the documentation folder, [specifically the quickstart guide.](esbmtk::Documentation/ESBMTK-Quick-Start_Guide.org::c394)


<a id="orgc1b3613"></a>

# License

ESBMTK: A general purpose Earth Science box model toolkit
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

