import numpy as np
from collections import namedtuple
from collections.abc import Iterable
from copy import deepcopy
from scipy.constants import value as const


Wells = namedtuple("Wells",
                   "name,z,width,dphidx,dphidy,dphidz,rx_axial,ry_axial,"
                   "phi_radial,d2phidaxial2,d3phidz3,d2phidradial_h2")
Wells.__doc__ = """Represents a snapshot of the parameters of potential wells

all parameters are tuples with 'length = <number of potential wells>'
:param name: label for each potential well
:param z: well centre position. Entries are sorted by position.
... respective parameters of the desired potential well"""

Waveform = namedtuple("Waveform",
                      "voltage_vec_list,el_vec,"
                      "fixed_wells,wells_idx")
Waveform.__doc__ = """Represents the electrode voltage evolution

:param voltage_vec_list: time ordered list of electrode voltages
:param el_vec: vector matching electrode names to voltages
:param fixed_wells: time ordered list of specified target `Wells`
:param wells_idx: list relating voltage_list indices to fixed_wells"""


class SURFMediator:
    """A high level interface to calculate electrode voltages for ion dynamics.

    The bare bones interface of the SURF driver is abstracted to simplify
    creating and chaining common operations.
    """
    def __init__(self, dmgr, device,
                 default_electrode_override=None,
                 default_z_grid_override=None,
                 default_f_axial=1e6,
                 default_f_rad_x=5e6,
                 default_split_start_curvature=1.e7,
                 default_split_end_curvature=-1.e7,
                 default_split_well_seperation=140e-6,
                 default_split_positions=np.array([0.]),
                 charge=1, mass=43):
        """
        :param dmgr: device maneger
        :param device: name of SURF driver
        :param default_electrode_override: If `None` SURF will default to
            using all trap_model electrodes.
        :param default_z_grid_override: If `None` SURF will default to
            using the `zs` vector provided in the trap model.
         :param default_f_axial: default axial trap frequency in Hz
         :param default_f_rad_x: default horizontal radial mode trap frequency
            in Hz
         :param default_split_start_curvature: transition from interpolation to
            split solver. Not included with the trap model as this is likely
            to require experimental optimisation. [in V m^-2]
         :param default_split_end_curvature: transition from split solver to
            interpolation. not included with the trap model as this is likely
            to require experimental optimisation. [in V m^-2]
        :param default_split_well_seperation: The default separation between
            wells after splitting. This should be ~2 electrode widths. [in m]
        :param default_split_position: By default wells are moved to the
            nearest of these positions for splitting/merging. Empirically,
            good positions for splitting/merging are at the centre of an
            electrode pair. [in m]
        :param charge: this must match the value of SURF.Constants.q
        :param mass: mass of ion in atomic mass units."""
        self.driver = dmgr.get(device)
        if default_electrode_override is None:
            self.default_electrodes = self.get_all_electrode_names()
        else:
            self.default_electrodes = default_electrode_override

        self.default_z_grid = default_z_grid_override
        self.default_f_axial = default_f_axial
        self.default_f_rad_x = default_f_rad_x
        self.default_split_start = default_split_start_curvature
        self.default_split_end = default_split_end_curvature
        self.default_split_end = default_split_end_curvature
        self.default_split_well_seperation = default_split_well_seperation
        self.default_split_positions = default_split_positions
        self.charge, self.mass = charge, mass

    def _mk_waveform(self, volt_vec, el_vec, wells):
        """Create a new waveform object

        The waveform will start at the specified voltages and well parameters

        electrodes and voltages are matched by index"""
        el_vec = tuple(el for el in el_vec)  # unpack into tuple
        wave = Waveform(voltage_vec_list=[volt_vec],
                        el_vec=el_vec, fixed_wells=[wells], wells_idx=[0])
        return wave

    def _volt_from_wells(self, wells, electrodes=None, z_grid=None,
                         static_settings=None):
        """Find the voltage-sets to produce specified potential wells

        :param wells: Wells object
        :param electrodes: Name electrodes that may be used. if `None` the
            default electrodes are used.
        :param z_grid: vector of z-axis grid points to use for optimisation.
            `None` defaults to the default grid supplied with the trap model.
        :param static_settings: settings for the static solver. User beware!"""
        if electrodes is None:
            electrodes = self.default_electrodes
        el_names = self.get_all_electrode_names()

        assert set(electrodes).issubset(set(el_names)), \
            "\n{}\n{}".format(set(electrodes), set(el_names))

        if z_grid is None:
            z_grid = self.default_z_grid

        param = {
            "zs": z_grid,
            "electrodes": electrodes,
            "wells": wells._asdict(),
            "static_settings": static_settings}

        v_vec, el_vec = self.driver.static(**param)
        return v_vec[:, 0], el_vec

    def get_all_electrode_names(self):
        """Return a list of all electrode names defined in the trap model"""
        return self.driver.get_all_electrode_names()

    def get_default_electrode_names(self):
        """Return the electrodes used by default"""
        if self.default_electrodes is None:
            return self.get_all_electrode_names()
        else:
            return self.default_electrodes

    def get_sum_square_freq(self, z):
        """Return the single ion sum of square mode frequencies of the model

        The correct model RF amplitude can be selected by scaling the RF
        amplitude such that the sum of square frequencies matches those
        measured experimentally

        :param z: position where the sum of square frequencies is found [in m]
        """
        return self.field_to_f(self.driver.get_div_grad_phi(z))**2

    def reload_trap_model(self, trap_model_path=None, cache_path=None,
                          omega_rf=None, mass=None, v_rf=None):
        """Reload the trap model caching and trap parameters

        All parameters have sane defaults.

        :param trap_model_path: path to the SURF trap model file.
            If `None` the most recently loaded file is used.
        :param cache_path: path on which to cache results.  Be sure to
            update/purge the cache if you change the trap model!
            `None` disables the cache.
        :param omega_rf: angular frequency of trap-RF [in rad/s]
            Default is given in trap model
        :param mass: mass of ion in atomic mass units
            Defaults to the most recently specified mass
        :param v_rf: RF voltage amplitude.
            Default is given in trap model"""
        if mass is not None:
            self.mass = mass
        return self.driver.load_config(trap_model_path, cache_path,
                                       omega_rf, self.mass, v_rf)

    def get_new_waveform(self, z, f_axial=None, f_rad_x=None, width=5e-6,
                         dphidx=0., dphidy=0., dphidz=0., rx_axial=0.,
                         ry_axial=0., phi_radial=0., d3phidz3=0., name=None,
                         *, electrodes=None, z_grid=None):
        """Start a new Waveform with given potential wells

        Each well is identified by its index within parameter lists. An
        optional more user-friendly name may also be specified for later
        convenience.

        :param z: iterable of well centre positions in m.
        :param f_axial: list of well axial frequencies in Hz. Scalars are
            broadcast. If `None` `self.default_f_axial` is used.
        :param f_rad_x: list of radial frequencies in Hz. For a non-rotated
            well this mode is on the x-axis. Scalars are broadcast.
            If `None` `self.default_f_rad_x` is used.
        :param width: characteristic size over which the well is produced in m.
            Scalars are broadcast. Default: 5e-6
        :param dphidx: x-compensation in V/m. Scalars are broadcast. Default: 0
        :param dphidy: y-compensation in V/m. Scalars are broadcast. Default: 0
        :param dphidz: z-compensation in V/m. Scalars are broadcast. Default: 0
        :param rx_axial: x-rotation angle of the axial mode from the z-axis in
            radians. Scalars are broadcast. Default: 0.
        :param ry_axial: y-rotation angle of the axial mode from the z-axis in
            radians. Scalars are broadcast. Default: 0.
        :param phi_radial: Rotation of the radial mode axes from the coordinate
            axes in radians. To be precise, the coordinate axes are transformed
            to the well principal axes by the following steps:
                1.  A rotation around the z-axis by phi_radial
                2.  A rotation around the y-axis by ry_axial
                3.  A rotation around the x-axis by rx_axial
            Default: 0.
        :param d3phidz3: cubic electric potential term in V*m^-3. Scalars are
            broadcast. Default: 0.
        :param name: List of string names for wells. Elements set to None will
            use the well index as a name. If unspecified, all names are the
            well index.

        :param electrodes: list naming electrodes to be used in the waveform.
            If `None` the default electrodes are used.
        :param z_grid: z-grid on which to perform optimisation. If `None` SURF
            will use the default grid."""
        well = self._mk_wells(z, f_axial, f_rad_x, width, dphidx, dphidy,
                              dphidz, rx_axial, ry_axial, phi_radial, d3phidz3,
                              name)
        volt, el = self._volt_from_wells(well, electrodes, z_grid)
        wave = self._mk_waveform(volt, el, well)
        return wave

    def modify(self, change_dict, wave, n_step=55, *,
               electrodes=None, z_grid=None,
               static_settings=None, dynamic_settings=None):
        """Calculate evolution to modified parameters

        :param change_dict: dictionary of changes to last Wells in wave
            change_dict should encode changes as:
            new_value = change_dict[<well_name>][<parameter>]
        :param wave: waveform to modify. In place!
        :param n_step: Number of DAC steps over which to evolve traps
        :param electrodes: Name electrodes that may be used in the new wells.
            If `None` the all electrodes in `wave` are used.
        :param z_grid: vector of z-axis grid points to use for optimisation.
            `None` defaults to the default grid supplied with the trap model.
        :param static_settings: settings for the static solver. User beware!
        :param dynamic_settings: settings for the dynamic solver. User beware!

        :return: updated waveform"""
        if electrodes is None:
            electrodes = wave.el_vec
        el_names = wave.el_vec

        assert set(electrodes).issubset(set(el_names)), \
            "\n{}\n{}".format(set(electrodes), set(el_names))

        if z_grid is None:
            z_grid = self.default_z_grid

        new_wells = deepcopy(wave.fixed_wells[-1])
        for name, param_dict in change_dict.items():
            idx = new_wells.name.index(name)
            for param, value in param_dict.items():
                # exploit mutability of list
                new_wells._asdict()[param][idx] = value

        new_volt, new_el = self._volt_from_wells(new_wells, electrodes, z_grid,
                                                 static_settings)

        # dict to pass to do_solve
        start_volt_dict = {el: wave.voltage_vec_list[-1][idx]
                           for idx, el in enumerate(wave.el_vec)}

        end_volt_dict = {el: 0.0 for el in wave.el_vec}
        end_volt_dict.update(
            {el: new_volt[idx] for idx, el in enumerate(new_el)})

        evol_param = {
            "zs": z_grid,
            "electrodes": tuple(el for el in wave.el_vec),
            "wells0": wave.fixed_wells[-1]._asdict(),
            "wells1": new_wells._asdict(),
            "volt_start": start_volt_dict,
            "volt_end": end_volt_dict,
            "n_step": n_step,
            "dynamic_settings": dynamic_settings}

        volt_evol, el_evol = self.driver.dynamic(**evol_param)
        # could handle this case, but should be the same in reasonable cases
        assert tuple(el for el in el_evol) == wave.el_vec, "{}; {}".format(
            el_evol, wave.el_vec)

        # append to wave
        wave.voltage_vec_list.extend([volt_evol[:, i] for i in range(n_step)])
        wave.fixed_wells.append(new_wells)
        wave.wells_idx.append(len(wave.voltage_vec_list))
        return wave

    def split(self, name, wave, n_step, n_scan=55, n_itpl=101, out_name0=None,
              out_name1=None, *, scan_curv_start=None, scan_curv_end=None,
              well_separation=None, electrodes=None, z_grid=None,
              static_settings=None, split_settings=None):
        """Calculate evolution to modified parameters

        :param name: name of well to be split
        :param wave: waveform to modify. Modified in place!
        :param n_step: number of steps in the splitting wave-form
        :param n_scan: number of scan points used to infer splitting wave-form
        :param n_itpl: number of interpolation steps to and from the
            the splitting waveform.
        :param out_name0: Name of new well0. If None: out_name0 = name.
        :param out_name1: Name of new well1. If None: out_name1 = name + "_1".

        :param scan_curv_start: d2phidaxial2 when starting the splitting scan
            [in V m^-2]. `None` uses the default
        :param scan_curv_start: d2phidaxial2 when ending the splitting scan
            [in V m^-2]. `None` uses the default
        :param well_separation: The separation between wells after
            splitting. `None` uses the default
        :param electrodes: Name electrodes that may be used in the new wells.
            If `None` the all electrodes in `wave` are used.
        :param z_grid: vector of z-axis grid points to use for optimisation.
            `None` defaults to the default grid supplied with the trap model.
        :param static_settings: settings for the static solver. User beware!
        :param split_settings: settings for the split solver. User beware!

        :return: updated waveform"""
        if electrodes is None:
            electrodes = wave.el_vec
        el_names = wave.el_vec

        assert set(electrodes).issubset(set(el_names)), \
            "\n{}\n{}".format(set(electrodes), set(el_names))

        if z_grid is None:
            z_grid = self.default_z_grid

        if scan_curv_start is None:
            scan_curv_start = self.default_split_start
        if scan_curv_end is None:
            scan_curv_end = self.default_split_end
        if well_separation is None:
            well_separation = self.default_split_well_seperation

        spectators = deepcopy(wave.fixed_wells[-1])
        split_idx = spectators.name.index(name)

        # list.pop() target well
        target_well = Wells(
            *([spectators[i].pop(split_idx)] for i in range(len(spectators))))

        # determine a sensible initial and final split well
        scan_start = deepcopy(target_well)
        scan_start.rx_axial[0] = 0.
        scan_start.ry_axial[0] = 0.
        scan_start.phi_radial[0] = 0.
        # empirical, good values will be different for different traps
        # ~1/10th of a "strong" trap
        scan_start.d2phidaxial2[0] = scan_curv_start  # 1.1666111496697802e7
        # tested split/merge with +-5833055.748348901

        scan_end = deepcopy(target_well)
        scan_end.rx_axial[0] = 0.
        scan_end.ry_axial[0] = 0.
        scan_end.phi_radial[0] = 0.
        # empirical, good values will be different for different traps
        # value is chosen to give a 2-ion separation of ~70 um = 1 electrode
        scan_end.d2phidaxial2[0] = scan_curv_end  # -1.1666111496697802e7 * 4

        split_params = {
            "electrodes": wave.el_vec,
            "zs": z_grid,
            "scan_start": scan_start._asdict(),
            "scan_end": scan_end._asdict(),
            "spectators": spectators._asdict(),
            "n_step": n_step,
            "n_scan": n_scan,
            "split_settings": split_settings,
        }

        # solve splitting dynamics
        volt_split, split_el, sep_vec = self.driver.split(**split_params)
        volt_split = [volt_split[:, i] for i in range(n_step)]

        # 140 um spaced wells -> at +- 1 electrode to start
        names = [
            name if out_name0 is None else out_name0,
            (name + "_1") if out_name1 is None else out_name1, ]
        split_wells = Wells(
            name=names,
            z=[target_well.z[0] - well_separation/2,
               target_well.z[0] + well_separation/2],
            width=[target_well.width[0]] * 2,
            dphidx=[target_well.dphidx[0]] * 2,
            dphidy=[target_well.dphidy[0]] * 2,
            dphidz=[target_well.dphidz[0]] * 2,
            rx_axial=[target_well.rx_axial[0]] * 2,
            ry_axial=[target_well.ry_axial[0]] * 2,
            phi_radial=[target_well.phi_radial[0]] * 2,
            d2phidaxial2=[target_well.d2phidaxial2[0]] * 2,
            d3phidz3=[target_well.d3phidz3[0]] * 2,
            d2phidradial_h2=[target_well.d2phidradial_h2[0]] * 2)

        # new wells & voltage-set
        final_wells = Wells(
            *(spectators[i][:split_idx] + split_wells[i] +
              spectators[i][split_idx:] for i in range(len(split_wells))))
        # ToDo: may want to check if there is sufficient space
        final_volt, final_el = self._volt_from_wells(
            final_wells, electrodes=wave.el_vec, z_grid=z_grid,
            static_settings=static_settings)

        # interpolate start and finish
        wave.voltage_vec_list.extend(
            self._interpolate(wave.voltage_vec_list[-1], volt_split[0], n_itpl)
            )
        wave.voltage_vec_list.extend(volt_split)
        wave.voltage_vec_list.extend(
            self._interpolate(wave.voltage_vec_list[-1], final_volt, n_itpl))

        wave.fixed_wells.append(final_wells)
        wave.wells_idx.append(len(wave.voltage_vec_list))
        return wave

    def merge(self, name0, name1, wave, n_step, n_scan=55, n_itpl=101,
              out_name=None, prepare_wells=True, n_prepare=101, *,
              scan_curv_start=None, scan_curv_end=None,
              well_separation=None, merge_pos=None,
              electrodes=None, z_grid=None, static_settings=None,
              dynamic_settings=None, split_settings=None):
        """Calculate evolution to modified parameters

        :param name0: name of well0 to be merged
        :param name1: name of well1 to be merged. Must be adjacent to well0
        :param wave: waveform to modify. Modified in place!
        :param n_step: number of steps in the splitting wave-form
        :param n_scan: number of scan points used to infer splitting wave-form
        :param n_itpl: number of interpolation steps to and from the
            the splitting waveform.
        :param out_name: Name of new well. If None: out_name = name0.
        :param prepare_wells: should the wells be moved to a good merging start
            position? If you want fine control of this, do it manually!
        :param n_prepare: number of voltage steps for well preparation.

        :param scan_curv_start: d2phidaxial2 when starting the splitting scan
            [in V m^-2]. `None` uses the default
        :param scan_curv_start: d2phidaxial2 when ending the splitting scan
            [in V m^-2]. `None` uses the default
        :param well_separation: The separation between wells before
            merging. `None` uses the default
        :param merge_pos: Position where the wells should be merged. [in m]
            If `None` the nearest `default_split_positions` is used.
        :param electrodes: Name electrodes that may be used in the new wells.
            If `None` the all electrodes in `wave` are used.
        :param z_grid: vector of z-axis grid points to use for optimisation.
            `None` defaults to the default grid supplied with the trap model.
        :param static_settings: settings for the static solver. User beware!
        :param dynamic_settings: settings for the dynamic solver. User beware!
        :param split_settings: settings for the split solver. User beware!

        :return updated waveform"""
        if electrodes is None:
            electrodes = wave.el_vec
        el_names = wave.el_vec

        assert set(electrodes).issubset(set(el_names)), \
            "\n{}\n{}".format(set(electrodes), set(el_names))

        if z_grid is None:
            z_grid = self.default_z_grid

        if scan_curv_start is None:
            scan_curv_start = self.default_split_start
        if scan_curv_end is None:
            scan_curv_end = self.default_split_end
        if well_separation is None:
            well_separation = self.default_split_well_seperation

        spectators = deepcopy(wave.fixed_wells[-1])
        merge_idx = [spectators.name.index(name0),
                     spectators.name.index(name1)]

        # ToDo: assert no wells between wells to be merged
        target_well = Wells(
            *([spectators[i][well_idx] for well_idx in merge_idx]
              for i in range(len(spectators))))

        spectators = Wells(
            *([val for i, val in enumerate(spectators[i])
               if i not in merge_idx]
              for i in range(len(spectators))))

        if merge_pos is None:
            pos_idx = np.argmin(np.abs(
                np.mean(target_well.z) - self.default_split_positions))
            merge_pos = self.default_split_positions[pos_idx]
        # merging is inverse splitting! -> use splitting solver
        # determine a sensible initial and final split well
        scan_start = Wells(
            name=[out_name if out_name is not None else name0],
            z=[merge_pos],
            width=[np.mean(target_well.width)],
            dphidx=[np.mean(target_well.dphidx)],
            dphidy=[np.mean(target_well.dphidy)],
            dphidz=[np.mean(target_well.dphidz)],
            rx_axial=[0.],
            ry_axial=[0.],
            phi_radial=[0.],
            d2phidaxial2=[scan_curv_start],
            d3phidz3=[np.mean(target_well.d3phidz3)],
            d2phidradial_h2=[np.mean(target_well.d2phidradial_h2)],)
        scan_end = deepcopy(scan_start)
        # empirical, good values will be different for different traps
        # value is chosen to give a 2-ion separation of ~70 um = 1 electrode
        scan_end.d2phidaxial2[0] = scan_curv_end

        # solve splitting dynamics (merging is inverse splitting)
        split_params = {
            "electrodes": tuple(el for el in wave.el_vec),
            "zs": z_grid,
            "scan_start": scan_start._asdict(),
            "scan_end": scan_end._asdict(),
            "spectators": spectators._asdict(),
            "n_step": n_step,
            "n_scan": n_scan,
            "split_settings": split_settings,
        }

        # solve splitting dynamics
        volt_merge, merge_el, sep_vec = self.driver.split(**split_params)
        volt_merge = [volt_merge[:, -i] for i in range(n_step)]

        if prepare_wells:
            # move wells to be separated by one electrode
            # self.modify to merge start position
            name_order = np.sign(target_well.z[1] - target_well.z[0])
            move_dict = {name0: {"z": scan_start.z[0]
                                 - name_order * well_separation/2},
                         name1: {"z": scan_start.z[0]
                                 + name_order * well_separation/2}, }
            wave = self.modify(move_dict, wave, n_prepare)

        # volt_from_wells for end well
        merged_well = deepcopy(scan_start)
        merged_well.d2phidaxial2[0] = np.mean(target_well.d2phidaxial2)

        # new wells & voltage-set
        final_wells = Wells(
            *(spectators[i][:min(merge_idx)] + merged_well[i] +
              spectators[i][min(merge_idx):] for i in range(len(merged_well))))

        # ToDo: may want to check if wells cross other wells.
        final_volt, final_el = self._volt_from_wells(
            final_wells, electrodes=wave.el_vec, z_grid=z_grid,
            static_settings=static_settings)

        # interpolate start and finish
        wave.voltage_vec_list.extend(
            self._interpolate(wave.voltage_vec_list[-1],
                              volt_merge[0], n_itpl))
        wave.voltage_vec_list.extend(volt_merge)

        wave.voltage_vec_list.extend(
            self._interpolate(wave.voltage_vec_list[-1], final_volt, n_itpl))

        wave.fixed_wells.append(final_wells)
        wave.wells_idx.append(len(wave.voltage_vec_list))
        return wave

    def spawn_wells(self, z, wave, n_step=5, *, z_grid=None, **kwargs):
        """Spawn new wells in a waveform

        Each well is identified by its index within parameter lists. An
        optional more user-friendly name may also be specified for later
        convenience.

        :param z: iterable of well centre positions in m.
        :param f_axial: list of well axial frequencies in Hz. Scalars are
            broadcast. Default: 1e6
        :param f_rad_x: list of radial frequencies in Hz. For a non-rotated
            well this mode is on the x-axis. Scalars are broadcast.
            Default: 5e6
        :param width: characteristic size over which the well is produced in m.
            Scalars are broadcast. Default: 5e-6
        :param dphidx: x-compensation in V/m. Scalars are broadcast. Default: 0
        :param dphidy: y-compensation in V/m. Scalars are broadcast. Default: 0
        :param dphidz: z-compensation in V/m. Scalars are broadcast. Default: 0
        :param rx_axial: x-rotation angle of the axial mode from the z-axis in
            radians. Scalars are broadcast. Default: 0.
        :param ry_axial: y-rotation angle of the axial mode from the z-axis in
            radians. Scalars are broadcast. Default: 0.
        :param phi_radial: Rotation of the radial mode axes from the coordinate
            axes in radians. To be precise, the coordinate axes are transformed
            to the well principal axes by the following steps:
                1.  A rotation around the z-axis by phi_radial
                2.  A rotation around the y-axis by ry_axial
                3.  A rotation around the x-axis by rx_axial
            Default: 0.
        :param d3phidz3: cubic electric potential term in V*m^-3. Scalars are
            broadcast. Default: 0.
        :param name: List of string names for wells. Elements set to None will
            use the well index as a name. If unspecified, all names are the
            well index.

        :param z_grid: z-grid on which to perform optimisation. If `None` SURF
            will use the default grid."""
        old_wells = wave.fixed_wells[-1]
        old_volt = wave.voltage_vec_list[-1]

        tmp_wells = self._mk_wells(z, **kwargs)
        new_wells = deepcopy(old_wells)
        new_wells = Wells(*[[*new_wells[i], *tmp_wells[i]]
                            for i in range(len(new_wells))])

        new_volt, el = self._volt_from_wells(new_wells, wave.el_vec,
                                             z_grid)
        v_steps = self._interpolate(old_volt, new_volt, n_step)
        wave.fixed_wells.append(new_wells)
        wave.voltage_vec_list.extend(v_steps)
        wave.wells_idx.append(len(wave.voltage_vec_list))

    def _interpolate(self, volt0, volt1, n_step):
        """Smoothly evolve between 2 voltage vectors.

        Assumes electrode ordering in both voltage vectors is identical.

        May be used to connect different (similar) waveforms or
        evolve to/from non SURF voltages"""
        return [volt0 + (volt1 - volt0) * t for t in np.linspace(0, 1, n_step)]

    def f_to_field(self, frequency):
        "convert mode frequency to field curvature"
        return (self.mass * const("atomic mass constant")
                / (self.charge * const("atomic unit of charge"))
                * (2 * np.pi * frequency)**2)

    def field_to_f(self, field_curvature):
        "convert field curvature to mode frequency"
        return np.sqrt(field_curvature
                       * self.charge * const("atomic unit of charge")
                       / (self.mass * const("atomic mass constant"))
                       ) / (2 * np.pi)

    def _mk_wells(self, z, f_axial=None, f_rad_x=None, width=5e-6, dphidx=0.,
                  dphidy=0., dphidz=0., rx_axial=0., ry_axial=0.,
                  phi_radial=0., d3phidz3=0., name=None):
        """Wells should be specified as parameter iterables of equal length.

        Each well is identified by its index within parameter lists. An
        optional more user-friendly name may also be specified for later
        convenience.

        :param z: iterable of well centre positions in m.
        :param f_axial: list of well axial frequencies in Hz. Scalars are
            broadcast. If `None` `self.default_f_axial` is used.
        :param f_rad_x: list of radial frequencies in Hz. For a non-rotated
            well this mode is on the x-axis. Scalars are broadcast.
            If `None` `self.default_f_rad_x` is used.
        :param width: characteristic size over which the well is produced in m.
            Scalars are broadcast. Default: 5e-6
        :param dphidx: x-compensation in V/m. Scalars are broadcast. Default: 0
        :param dphidy: y-compensation in V/m. Scalars are broadcast. Default: 0
        :param dphidz: z-compensation in V/m. Scalars are broadcast. Default: 0
        :param rx_axial: x-rotation angle of the axial mode from the z-axis in
            radians. Scalars are broadcast. Default: 0.
        :param ry_axial: y-rotation angle of the axial mode from the z-axis in
            radians. Scalars are broadcast. Default: 0.
        :param phi_radial: Rotation of the radial mode axes from the coordinate
            axes in radians. To be precise, the coordinate axes are transformed
            to the well principal axes by the following steps:
                1.  A rotation around the z-axis by phi_radial
                2.  A rotation around the y-axis by ry_axial
                3.  A rotation around the x-axis by rx_axial
            Default: 0.
        :param d3phidz3: cubic electric potential term in V*m^-3. Scalars are
            broadcast. Default: 0.
        :param name: List of string names for wells. Elements set to None will
            use the well index as a name. If unspecified, all names are the
            well index."""
        if f_axial is None:
            f_axial = self.default_f_axial
        if f_rad_x is None:
            f_rad_x = self.default_f_rad_x

        if not isinstance(z, Iterable):
            z = [z,]
        else:
            z = [i for i in z]

        if not isinstance(f_axial, Iterable):
            f_axial = [f_axial for i in z]
        d2phidaxial2 = [self.f_to_field(i) for i in f_axial]
        if not isinstance(f_rad_x, Iterable):
            f_rad_x = [f_rad_x for i in z]
        d2phidradial_h2 = [self.f_to_field(i) for i in f_rad_x]

        if not isinstance(width, Iterable):
            width = [width for i in z]
        if not isinstance(dphidx, Iterable):
            dphidx = [dphidx for i in z]
        if not isinstance(dphidy, Iterable):
            dphidy = [dphidy for i in z]
        if not isinstance(dphidz, Iterable):
            dphidz = [dphidz for i in z]

        if not isinstance(rx_axial, Iterable):
            rx_axial = [rx_axial for i in z]
        if not isinstance(ry_axial, Iterable):
            ry_axial = [ry_axial for i in z]
        if not isinstance(phi_radial , Iterable):
            phi_radial = [phi_radial for i in z]
        if not isinstance(d3phidz3, Iterable):
            d3phidz3 = [d3phidz3 for i in z]

        if name is None:
            name = [str(i) for i in range(len(z))]
        else:
            [n if n is not None else str(i) for i, n in enumerate(name)]

        return Wells(name, z, width, dphidx, dphidy, dphidz, rx_axial,
                     ry_axial, phi_radial, d2phidaxial2, d3phidz3,
                     d2phidradial_h2)
