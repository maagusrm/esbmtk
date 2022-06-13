from __future__ import annotations
import typing as tp

if tp.TYPE_CHECKING:
    from esbmtk import Flux, Reservoir, Model, Connection, Connect


def get_initial_conditions(M: Model) -> tuple[list, list, list, list]:
    """get list of initial conditions. THis list needs to match
    the number of equations. We need to consider 3 types reservoirs:

    1) Reservoirs that change as a result of physical fluxes
       i.e. r.lof > 0. These require a flux statements and a
       reservoir equation.

    2) Reservoirs that do not have active fluxes but are computed
       as a tracer, i.e.. HCO3. These only require a reservoir
       equation

    3) Reservoirs that do not change but are used as input. Those
       should not happen in a well formed model, but we cannot
       exclude the possibility. In this case, there is no flux
       equation, and we state that dR/dt = 0

    """

    R = []  # list of initial conditions
    icl: list = []  # list of reservoirs that depend on fluxes
    cpl: list = []  # list of reservoirs that are computed
    ipl: list = []  # list of static reservoirs that serve as input

    for r in M.lic:
        # print(f"R={r.full_name} lof = {len(r.lof)}")
        if len(r.lof) > 0:  # list of reservoirs that depend on fluxes
            R.append(r.c[0])
            icl.append(r)
            # print(f"adding {r.full_name} to icl")
        else:  # list of reservoirs that are computed
            cpl.append(r)
            # if r.name == "H":
            #     icl.append(r)
            #     R.append(r.c[0])
            # print(f"adding {r.full_name} to cpl")

    ipl = list(set(M.lic).difference(M.lor))

    if len(ipl) > 0:
        icl.append(ipl)
        M.lic.append(ipl)

    return R, icl, cpl, ipl


def write_equations_2(
    M: Model, R: list[float], icl: list, cpl: list, ipl: list
) -> list:
    """Write file that contains the ode-equations for M
    Returns the list R that contains the initial condition
    for each reservoir

    icl: list of reservoirs that have actual fluxes
    cpl: list of reservoirs that hjave no fluxes but are computed based on other R's
    ipl: list of reserevoir that do not change in concentration

    """
    from esbmtk import Model, ReservoirGroup
    import pathlib as pl

    # get pathlib object
    fn: str = "equations.py"  # file name
    cwd: pl.Path = pl.Path.cwd()  # get the current working directory
    fqfn: pl.Path = pl.Path(f"{cwd}/{fn}")  # fully qualified file name

    # construct header and static code:
    header = """from __future__ import annotations\n\n
import typing as tp

if tp.TYPE_CHECKING:
    from esbmtk import Model


class setup_ode():
    '''Class stub to enable state in the equation system passed to ODEINT
    '''

    from esbmtk import Model, ReservoirGroup

    def __init__(self, M: Model)->None:
        ''' Use this method to initialize all variables that require the state
            t-1
        '''
        import numpy as np

        self.i = 0
        self.last_t = 0
        self.hplus = 10**-8.1

    def eqs(self, t, R: list, M: Model) -> list:
        '''Auto generated esbmtk equations do not edit
        '''

        from esbmtk import carbonate_system_1_ode, carbonate_system_2_ode
    
        # flux equations
"""

    # """
    # write file
    with open(fqfn, "w", encoding="utf-8") as eqs:

        rel = ""  # list of return values
        ind1 = 4 * " "
        ind2 = 8 * " "  # indention
        ind3 = 12 * " "  # indention

        eqs.write(header)

        eqs.write(f"{ind2}{M.name} = M\n")

        flist = list()

        sep = "# ---------------- write all flux equations ------------------- #"
        eqs.write(f"\n{sep}\n")

        for flux in M.lof:  # loop over fluxes

            # fluces blong to at least 2 reservoirs, so we need to avoid duplication
            # we cannot use a set, since we need to preserv order
            if flux not in flist:
                fex = ""
                fex = get_flux(flux, M, R, icl)
                fn = flux.full_name.replace(".", "_")
                eqs.write(f"{ind2}{fn} = {fex}\n")
                flist.append(flux)

        sep = "# ---------------- write input only reservoir equations -------- #"
        eqs.write(f"\n{sep}\n")

        for r in ipl:
            rname = r.full_name.replace(".", "_")
            eqs.write(f"{ind2}{rname} = 0.0")

        sep = "# ---------------- write regular reservoir equations ------------ #"
        eqs.write(f"\n{sep}\n")

        for r in M.lor:  # loop over reservoirs

            # create unique variable name. Reservoirs are typiclally called
            # M.rg.r so we replace all dots with underscore
            name = r.full_name.replace(".", "_")
            fex = ""
            for flux in r.lof:
                if flux.parent.source == r:
                    sign = "-"
                elif flux.parent.sink == r:
                    sign = "+"
                fex = fex + f"{ind3}{sign} {flux.full_name.replace('.', '_')}\n"

            # check if reservoir requires carbonate burial fluxes
            if isinstance(r.parent, ReservoirGroup):
                if r.parent.has_cs2:
                    if r.species.name == "DIC" or r.species.name == "TA":
                        fn = f"{r.full_name}.burial".replace(".", "_")
                        fex = f"{fex}{ind3}- {fn}\n"

            # avoid reservoirs without active fluxes
            if len(r.lof) > 0:
                eqs.write(f"{ind2}{name} = (\n{fex}{ind2})/{r.full_name}.volume\n\n")
                rel = rel + f"{name}, "

        sep = "# ---------------- write computed reservoir equations -------- #"
        eqs.write(f"\n{sep}\n")

        for r in M.lpc_r:  # All virtual reservoirs need to be in this list

            if r.ftype == "cs1":
                # carbonate_system_1_ode(rg: Reservoir
                eqs.write(
                    f"{ind2}self.hplus = "
                    f"carbonate_system_1_ode({r.parent.full_name}, "
                    f"R[{icl.index(r.parent.DIC)}], "
                    f"R[{icl.index(r.parent.TA)}], "
                    f"self.hplus, self.i) # cs 1\n"
                )

                # # write hplus in differential form
                # fname = f"{r.parent.full_name}.H".replace(".", "_")
                # eqs.write(
                #     f"{ind2}{fname}_cv = "
                #     f"carbonate_system_1_ode({r.parent.full_name}, "
                #     f"R[{icl.index(r.parent.DIC)}], "
                #     f"R[{icl.index(r.parent.TA)}], "
                #     f"R[{icl.index(r.parent.H)}])  # cs1\n"
                # )

                # # eqs.write(f"{ind2}R[{icl.index(r.parent.H)}] = {fname}_cv\n")
                # eqs.write(f"{ind2}{fname} = -(R[{icl.index(r.parent.H)}] - {fname}_cv) "
                #           f"/ {r.parent.full_name}.H.volume\n")
                # rel = rel + f"{fname}, "

            elif r.ftype == "cs2":
                fn_dic = f"{r.register.DIC.full_name}.burial".replace(".", "_")
                fn_ta = f"{r.register.TA.full_name}.burial".replace(".", "_")
                influx = r.parent.cs.ref_flux[0].full_name.replace(".", "_")
                eqs.write(
                    f"{ind2}{fn_dic} = carbonate_system_2_ode(t, {r.parent.full_name}, {influx}, "
                    f"R[{icl.index(r.parent.DIC)}], "
                    f"R[{icl.index(r.parent.TA)}])  # cs2 \n"
                )
                eqs.write(f"{ind2}{fn_ta} = {fn_dic} * 2  # cs2\n")
            else:
                raise ValueError(f"{r.ftype} is undefined")

        sep = "# ---------------- bits and pieces --------------------------- #"
        eqs.write(f"\n{sep}\n")

        eqs.write(f"{ind2}self.i += 1\n")
        eqs.write(f"{ind2}self.last_t = t\n")
        eqs.write(f"{ind2}return [{rel}]\n")

        if len(R) != len(rel.split(",")) - 1:
            raise ValueError(
                f"number of initial conditions ({len(R)})"
                f"does not match number of return values ({len(rel.split(','))-1}')\n\n"
                f"R = {R}\n"
                f"rv = {rel}\n"
            )

    return R


def get_flux(flux: Flux, M: Model, R: list[float], icl: list) -> str:
    """Create formula expression that describes the flux f
    returns ex as string
    """

    ex = ""
    c = flux.parent  # shorthand for the connection object
    cfn = flux.parent.full_name

    if c.ctype.casefold() == "regular":
        ex = f"{flux.full_name}.rate"
        ex = check_signal_2(ex, c)
        ex = ex + "  # fixed rate"

    elif c.ctype == "scale_with_concentration":
        ici = icl.index(c.source)  # index into initial conditions
        ex = (
            f"{cfn}.scale * R[{ici}]"  # {c.id} scale with conc in {c.source.full_name}"
        )
        ex = check_signal_2(ex, c)
        ex = ex + "  # scale with concentration"

    elif c.ctype == "scale_with_mass":
        ici = icl.index(c.source)  # index into initial conditions
        ex = f"{cfn}.scale * {c.source.full_name}.volume * R[{ici}]"
        ex = check_signal_2(ex, c)
        ex = ex + "  # scale with mass"

    elif c.ctype == "scale_with_flux":
        p = flux.parent.ref_flux.parent
        ex = f"{cfn}.scale * {p.full_name.replace('.', '_')}__F"
        ex = check_signal_2(ex, c)
        ex = ex + "  # scale with flux"

    elif c.ctype == "weathering":
        # c.reservoir_ref.full_name needs to be replaced with stateful reference or initial conditions?
        # how do we fine the correct R[] ?
        ici = icl.index(c.reservoir_ref)
        # ex = f"{cfn}.rate * {cfn}.scale * (R[{ici}]/{cfn}.pco2_0) **  {c.ex}"
        ex = f"{cfn}.rate * {cfn}.scale * (R[{ici}]/{cfn}.pco2_0) **  {cfn}.ex"
        ex = check_signal_2(ex, c)
        ex = ex + "  # weathering"

    elif c.ctype == "gas_exchange":  # Gasexchange
        ex = f"{flux.full_name}._PGex.ode()"
        ex = check_signal_2(ex, c)
        ex = ex + "  # gas_exchange"

    else:
        pass
        raise ValueError(f"{c.ctype} is not implmented")

    return ex


def check_signal_2(ex: str, c: tp.union(Connection, Connect)) -> str:
    """Test if connection requires a signal"""

    sign = ""
    ind3 = 12 * " "  # indentation
    if c.signal != "None":
        # get signal type
        if c.signal.stype == "addition":
            sign = "+"
        else:
            raise ValueError(f"stype={c.signal.stype} not implemented")

        ex = ex + f" {sign} {c.signal.full_name}(t)[0]  # Signal"

    return ex
