"""
esbmtk: A general purpose Earth Science box model toolkit Copyright
(C), 2020 Ulrich G.  Wortmann

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or (at
your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
from __future__ import annotations

import typing as tp
from esbmtk import Q_, register_return_values

if tp.TYPE_CHECKING:
    from esbmtk import Flux, Model, ReservoirGroup


def photosynthesis(
    o2,
    ta,
    dic,
    dic_l,
    po4,
    so4,
    h2s,
    productivity,  # actually P flux
    volume,
    PC_ratio,
    NC_ratio,
    O2C_ratio,
    PUE,
    rain_rate,
    om_fractionation_factor,
    VPDB_r0,  # reference ratio
) -> tuple:
    """Calculate the effects of photosynthesis in the surface boxes"""
    """O2 in surface box as result of photosynthesis equals the primary
    productivity export flux of organic C times the O2:C ratio
    TA increases because of nitrate uptake during photosynthesis

    Note that this functions returns fluxes, so we need to calculate
    dMdt, not dCdt
    """
    from esbmtk import get_new_ratio_from_alpha

    # OM formation
    dMdt_po4 = -productivity * PUE  # remove PO4 into OM
    dMdt_OM = -dMdt_po4 * PC_ratio  # mass of newly formed OM
    r = get_new_ratio_from_alpha(dic, dic_l, om_fractionation_factor)
    dMdt_OM_l = dMdt_OM * r  # mass of OM_l
    dMdt_dic = -dMdt_OM  # remove DIC by OM formation
    dMdt_dic_l = -dMdt_OM_l
    dMdt_ta = -dMdt_OM * NC_ratio  # add TA from nitrate uptake into OM

    # CaCO3 formation
    CaCO3 = dMdt_OM / rain_rate  # newly formed CaCO3
    dMdt_dic += -CaCO3  # dic removed
    dMdt_dic_l += -CaCO3 * dic_l / dic
    dMdt_ta += 2 * -CaCO3  # TA removed

    # sulfur reactions, assuming that there is alwways enough O2
    dMdt_h2s = -h2s * volume  # H2S oxidation
    dCdt_so4 = dMdt_h2s  # add S to the sulfate pool
    dMdt_ta += dMdt_ta - 2 * dCdt_so4  # adjust Alkalinity

    # add O2 from photosynthesis - h2s oxidation
    dCdt_o = dMdt_OM * O2C_ratio - 2 * h2s * volume

    # note that these are returned as fluxes
    return (
        dCdt_o,
        dMdt_ta,
        dMdt_po4,
        dCdt_so4,
        dMdt_h2s,
        dMdt_dic,
        dMdt_dic_l,
        dMdt_OM,
        dMdt_OM_l,
    )


def init_photosynthesis(rg, productivity):
    """Setup photosynthesis instances"""
    from esbmtk import ExternalCode

    M = rg.mo

    ec = ExternalCode(
        name="ps",
        species=rg.mo.Oxygen.O2,
        fname="photosynthesis",
        ftype="cs2",  # cs1 is independent of fluxes, cs2 is not
        vr_datafields={"OM": 0, "OM_l": 0},
        function_input_data=[
            rg.O2,
            rg.TA,
            rg.DIC,
            rg.PO4,
            rg.SO4,
            rg.H2S,
            productivity,
            rg.volume.magnitude,
            M.PC_ratio,
            M.NC_ratio,
            M.O2C_ratio,
            M.PUE,
            M.rain_rate,
            M.OM_frac / 1000 + 1,  # convert to actual ratio
            M.C.r,  # VDPB reference ratio
        ],
        register=rg,
        return_values=[
            {"F_rg.O2": "photosynthesis"},
            {"F_rg.TA": "photosynthesis"},
            {"F_rg.PO4": "photosynthesis"},
            {"F_rg.SO4": "photosynthesis"},
            {"F_rg.H2S": "photosynthesis"},
            {"F_rg.DIC": "photosynthesis"},
            {"F_rg.OM": "photosynthesis"},
        ],
    )
    rg.mo.lpc_f.append(ec.fname)

    return ec


def add_photosynthesis(rgs: list[ReservoirGroup], p_fluxes: list[Flux | Q_]):
    """Add process to ReservoirGroup(s) in rgs. pfluxes must be list of Flux
    objects or float values that correspond to the rgs list
    """
    from esbmtk import register_return_values

    M = rgs[0].mo
    for i, r in enumerate(rgs):
        if isinstance(p_fluxes[i], Q_):
            p_fluxes[i] = p_fluxes[i].to(M.f_unit).magnitude

        ec = init_photosynthesis(r, p_fluxes[i])
        register_return_values(ec, r)
        r.has_cs1 = True


def remineralization(
    om_fluxes: list,  # OM export fluxes
    om_fluxes_l: list,  # OM_l export fluxes
    dic_fluxes: list,
    dic_fluxes_l: list,
    om_remin_fraction: list,  # list of remineralization fractions
    alpha: float,
    h2s: float,  # concentration
    so4: float,  # concentration
    o2: float,  # o2 concentration
    po4: float,  # po4 concentration
    volume: float,  # box volume
    PC_ratio: float,
    NC_ratio: float,
    O2C_ratio: float,
    CaCO3_reactions=True,
    # burial: float,
) -> float:
    """Reservoirs can have multiple sources of OM with different
    remineralization efficiencies, e.g., low latidtude OM flux, vs
    high latitude OM flux. We only add the part that is remineralized.
    Note: The CaCO3 fluxes are handled below
    """
    OM_flux = 0
    OM_flux_l = 0
    # sum all OM and dic fluxes
    for i, f in enumerate(om_fluxes):
        OM_flux += f * om_remin_fraction[i]
        OM_flux_l += om_fluxes_l[i] * om_remin_fraction[i]

    # remove Alkalinity and add dic and po4 from OM remineralization
    # this happens irrespective of oxygen levels
    dMdt_po4 = OM_flux / PC_ratio  # return PO4
    dMdt_ta = -OM_flux * NC_ratio  # remove Alkalinity from NO3
    dMdt_dic = OM_flux  # add DIC from OM
    dMdt_dic_l = OM_flux_l

    print(f"OM_flux = {OM_flux:2e}")
    print(f"dMdt_po4 = {dMdt_po4:2e}")
    print(f"dMdt_ta = {dMdt_ta:2e}")
    print(f"dMdt_dic = {dMdt_dic:2e}")
    print(f"dMdt_dic_l = {dMdt_dic_l:2e}")

    m_h2s = h2s * volume
    m_o2 = o2 * volume
    # how much O2 is needed to oxidize all OM and H2S
    m_o2_eq = OM_flux * O2C_ratio + 2 * m_h2s

    if m_o2 > m_o2_eq:  # box has enough oxygen
        dMdt_o2 = -m_o2_eq  # consume O2
        dMdt_h2s = -m_h2s  # consume all h2s
        dMdt_so4 = -m_h2s  # add sulfate
        print("oxic remin")
        print(f"dMdt_o2 = {dMdt_o2:2e}")
        print(f"dMdt_h2s = {dMdt_h2s:2e}")
        print(f"dMdt_so4 = {dMdt_so4:2e}")

    else:  # box has not enough oxygen
        dMdt_o2 = -m_o2  # remove all available oxygen
        # calculate how much OM is left to oxidize
        OM_flux = OM_flux - m_o2 / O2C_ratio
        # oxidize the remaining OM via sulfate reduction
        dMdt_so4 = -OM_flux / 2  # one SO4 oxidizes 2 carbon, and add 2 mol to TA
        dMdt_h2s = -dMdt_so4  # move S to reduced reservoir
        dMdt_ta += 2 * -dMdt_so4  # adjust Alkalinity for changes in sulfate
        print("anoxic remin")
        print(f"dMdt_o2 = {dMdt_o2:2e}")
        print(f"dMdt_h2s = {dMdt_h2s:2e}")
        print(f"dMdt_so4 = {dMdt_so4:2e}")
        print(f"dMdt_ta = {dMdt_ta:2e}")

    if CaCO3_reactions:
        dic_flux = 0
        dic_flux_l = 0
        for i, f in enumerate(dic_fluxes):
            dic_flux += f * alpha[i]
            dic_flux_l += dic_fluxes_l[i] * alpha[i]

        breakpoint()
        # add Alkalinity and DIC from CaCO3 dissolution
        dMdt_dic += dic_flux
        dMdt_dic_l += dic_flux_l
        dMdt_ta += 2 * dic_flux

    # note, these are returned as fluxes
    return [dMdt_ta, dMdt_h2s, dMdt_so4, dMdt_o2, dMdt_po4]


def init_remineralization(
    rg: ReservoirGroup,
    om_fluxes: list[Flux],
    om_fluxes_l: list[Flux],
    om_remin_fractions: list[float],
    CaCO3_fluxes: list[Flux],
    CaCO3_fluxes_l: list[Flux],
    CaCO3_remin_fractions: list[float],
    CaCO3_reactions: bool,
):
    """ """
    from esbmtk import ExternalCode

    M = rg.mo
    ec = ExternalCode(
        name="rm",
        species=rg.mo.Carbon.CO2,
        function=remineralization,
        fname="remineralization",
        ftype="cs2",  # cs1 is independent of fluxes, cs2 is not
        # hplus is not used but needed in post processing
        vr_datafields={"Hplus": rg.swc.hplus},
        function_input_data=[
            om_fluxes,
            om_fluxes_l,
            CaCO3_fluxes,
            CaCO3_fluxes_l,
            om_remin_fractions,
            CaCO3_remin_fractions,
            rg.H2S,
            rg.SO4,
            rg.O2,
            rg.PO4,
            rg.volume.magnitude,
            M.PC_ratio,
            M.NC_ratio,
            M.O2C_ratio,
            CaCO3_reactions,
        ],
        register=rg,
        return_values=[
            {"F_rg.TA": "remineralization"},
            {"F_rg.H2S": "remineralization"},
            {"F_rg.SO4": "remineralization"},
            {"F_rg.O2": "remineralization"},
            {"F_rg.PO4": "remineralization"},
        ],
    )
    rg.mo.lpc_f.append(ec.fname)
    return ec


def add_remineralization(M: Model, f_map: dict) -> None:
    """
    Add remineralization fluxes to the model.

    Parameters:
    M (Model): The model object t
    f_map (dict): A dictionary that maps sink names to source dictionaries. The
    source dictionary should contain the source species and a list of type
    and remineralization values. For example, {M.A_ib: {M.H_sb: ["OM", 0.3]}}.

    Raises:
    ValueError: If an invalid type is specified in the source dictionary.

    Returns:
    None
    """
    # get sink name (e.g., M.A_ib) and source dict e.g. {M.H_sb: {"OM": 0.3}}
    for sink, source_dict in f_map.items():
        om_fluxes = list()
        om_fluxes_l = list()
        om_remin = list()
        CaCO3_fluxes = list()
        CaCO3_fluxes_l = list()
        CaCO3_remin = list()

        # create flux lists for OM and possibly CaCO3
        for source, type_dict in source_dict.items():
            # get matching fluxes for e.g., M.A_sb, and OM
            if "OM" in type_dict:
                fl = M.flux_summary(
                    filter_by=f"photosynthesis {source.name} OM",
                    return_list=True,
                )
                for f in fl:
                    om_remin.append(type_dict["OM"])
                    if f.name[-3:] == "F_l":
                        om_fluxes_l.append(f)
                    else:
                        om_fluxes.append(f)

            if "DIC" in type_dict:
                fl = M.flux_summary(
                    filter_by=f"photosynthesis {source.name} DIC",
                    return_list=True,
                )
                for f in fl:
                    CaCO3_remin.append(type_dict["DIC"])
                    if f.name[-3:] == "F_l":
                        CaCO3_fluxes_l.append(f)
                    else:
                        CaCO3_fluxes.append(f)

        #print(f"CaCO3 fluxes {sink.full_name} {CaCO3_fluxes}")
        #print(f"OM fluxes {sink.full_name} {om_fluxes}")
        if len(CaCO3_fluxes) > 0:
            ec = init_remineralization(
                sink,
                om_fluxes,
                om_fluxes_l,
                om_remin,
                CaCO3_fluxes,
                CaCO3_fluxes_l,
                CaCO3_remin,
                True,
            )
        else:
            ec = init_remineralization(
                sink,
                om_fluxes,
                om_fluxes_l,
                om_remin,
                CaCO3_fluxes,
                CaCO3_fluxes_l,
                CaCO3_remin,
                False,
            )
        register_return_values(ec, sink)
        sink.has_cs2 = True
