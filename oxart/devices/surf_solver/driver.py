"""This driver requires PyJulia & working julia install with configured PyCall

PyJulia doesn't play nice with conda. You should call this driver from the same
environment that you configured for PyCall in Julia. Instructions to configure
PyCall with conda are given in the README file of the SURF Julia library.
"""

import numpy as np
import julia
from sipyco import pyon
import shelve
import os


class SURF:
    """SURF Uncomplicated Regional Fields (python driver)"""
    def __init__(self,
                 trap_model_path="/home/ion/scratch/julia_projects/SURF/"
                 "trap_model/comet_model.jld",
                 cache_path=None,
                 **kwargs):
        """
        :param trap_model_path: path to the SURF trap model file
        :param cache_path: path on which to cache results. None disables cache.
        """
        self.jl = julia.Julia()
        self.jl.eval("import SURF")
        self.jl.eval("using SURF.Electrodes")
        self.jl.eval("using SURF.ExternalField")
        self.jl.eval("using SURF.TargetPotential")
        self.jl.eval("using SURF.DataSelect")
        self.jl.eval("using SURF.Load")

        self.current_config_args = {}
        self.load_config(trap_model_path, cache_path, **kwargs)
        print("ready")

    def load_config(self,
                    trap_model_path=None,
                    cache_path=None,
                    omega_rf=None,
                    mass=None,
                    v_rf=None,
                    force_reload=False):
        """
        Load trap model and default solver settings from the specified file and
        set solution solution cache path.

        :param trap_model_path: Path to the SURF trap model file
        :param cache_path: Path where future solutions are saved to, and if
            present later recalled from. Be sure to update/purge the cache
            if you change the trap model! ``None`` disables the cache.
        :param omega_rf: Angular frequency of trap-RF [in rad/s]
        :param mass: Mass of ion in atomic mass units
        :param v_rf: RF voltage amplitude.
        :param force_reload: Reload model even if arguments are identical to
            currently loaded config. Set to ``True`` if the model changed.
        """
        if trap_model_path is not None:
            self.trap_model_path = trap_model_path
        # create cache directory as needed
        if cache_path is not None:
            cache_path = os.path.join(cache_path,
                                      "m{}_w{}_v{}".format(mass, omega_rf, v_rf))
            if not os.path.isdir(cache_path):
                os.mkdir(cache_path)
        self.cache_path = cache_path

        args = {
            "trap_model_path": self.trap_model_path,
            "cache_path": self.cache_path,
            "omega_rf": omega_rf,
            "mass": mass,
            "v_rf": v_rf
        }
        if args == self.current_config_args and not force_reload:
            return self.get_config()
        self.current_config_args = args

        model = self.jl.eval("SURF.Load.load_model")(self.trap_model_path,
                                                     omega_rf=omega_rf,
                                                     mass=mass,
                                                     v_rf=v_rf)
        self.raw_elec_grid, self.raw_field_grid = model[0:2]
        self.elec_fn = self.jl.eval("mk_electrodes_fn")(self.raw_elec_grid)
        self.field_fn = self.jl.eval("mk_field_fn")(self.raw_field_grid)

        # recommended default values for user
        self.user_defaults = {
            "zs": model[2],
            "static_settings": model[3],
            "dynamic_settings": model[4],
            "split_settings": model[5],
        }
        return self.get_config()

    def get_div_grad_phi(self, z):
        """return div(grad(Phi)) at z position"""
        # hack: field names are unicode (not a valid python identifier)
        # The work-around is to evaluate the field names in julia

        # assignment in julia repel main name-space
        julia.Main.last_field_fn = self.field_fn
        div_grad_phi = self.jl.eval("last_field_fn.d2\N{Greek Capital Letter Phi}dx2")(
            z)
        div_grad_phi += self.jl.eval("last_field_fn.d2\N{Greek Capital Letter Phi}dy2")(
            z)
        div_grad_phi += self.jl.eval("last_field_fn.d2\N{Greek Capital Letter Phi}dz2")(
            z)
        return div_grad_phi

    def get_config(self):
        """Dictionary containing configuration Settings"""
        conf = {
            "trap_model_path": self.trap_model_path,
            "cache_path": self.cache_path,
            "zs": self.user_defaults["zs"],
        }
        settings = {
            "static_settings": (
                self.user_defaults["static_settings"].scale_tup,
                self.user_defaults["static_settings"].v_weight,
                self.user_defaults["static_settings"].v_max,
            ),
            "dynamic_settings": (
                self.user_defaults["dynamic_settings"].scale_tup,
                self.user_defaults["dynamic_settings"].v_weight,
                self.user_defaults["dynamic_settings"].v_step_weights,
                self.user_defaults["dynamic_settings"].v_max,
            ),
            "split_settings": (
                self.user_defaults["split_settings"].split_scale_tup,
                self.user_defaults["split_settings"].spectator_scale_tup,
                self.user_defaults["split_settings"].v_weight,
                self.user_defaults["split_settings"].v_max,
            ),
        }
        conf.update(settings)
        return conf

    def static(self, **param_dict):
        """Controls static solver and handles julia objects

        This is required as sipyco can't serialise the julia objects.

        :param **param_dict: dictionary with execution information
            specify fields by using kwargs/unpacking a dictionary.
            Most parameters load sane defaults.

        :returns: voltage_array, electrode_name_tup
            voltage_array shape: (electrode_name_tup, n_time_steps).
        """
        names = param_dict.get("electrodes", None)
        if names is None:
            elec_fn = self.elec_fn
        else:
            elec_fn = self._select_elec(self.elec_fn, names)

        zs = param_dict.get("zs", None)
        if zs is None:
            zs = self.user_defaults["zs"]

        elec_grid, field_grid = self._mk_grids(zs, elec_fn, self.field_fn)

        wells = self._mk_wells(**param_dict["wells"])

        if param_dict.get("static_settings", None) is None:
            settings = self.user_defaults["static_settings"]
        else:
            settings = self._mk_solver_settings(*param_dict["static_settings"],
                                                solver="Static")

        # need to fix argument order!
        arg_key = pyon.encode(
            (elec_fn.names, zs, param_dict.get("static_settings",
                                               None), param_dict["wells"]["z"],
             param_dict["wells"]["width"], param_dict["wells"]["dphidx"],
             param_dict["wells"]["dphidy"], param_dict["wells"]["dphidz"],
             param_dict["wells"]["rx_axial"], param_dict["wells"]["ry_axial"],
             param_dict["wells"]["phi_radial"], param_dict["wells"]["d2phidaxial2"],
             param_dict["wells"]["d3phidz3"], param_dict["wells"]["d2phidradial_h2"]))
        if self.cache_path is not None:
            with shelve.open(os.path.join(self.cache_path, "static")) as db:
                try:
                    return db[arg_key]
                except KeyError:
                    pass  # key not found

        voltages = self._solve_static(wells, elec_grid, field_grid, settings)

        if self.cache_path is not None:
            with shelve.open(os.path.join(self.cache_path, "static")) as db:
                try:
                    db[arg_key] = voltages, elec_fn.names
                except ValueError:
                    pass  # value too large
        return voltages, elec_fn.names

    def split(self, **param_dict):
        """Controls split solver and handles julia objects

        This is required as sipyco can't serialise the julia objects.

        :param **param_dict: dictionary with execution information
            specify fields by using kwargs/unpacking a dictionary.
            Most parameters load sane defaults.

        :returns: voltage_array, electrode_name_tup
            voltage_array shape: (electrode_name_tup, n_time_steps).
        """
        names = param_dict.get("electrodes", None)
        if names is None:
            elec_fn = self.elec_fn
        else:
            elec_fn = self._select_elec(self.elec_fn, names)

        zs = param_dict.get("zs", None)
        if zs is None:
            zs = self.user_defaults["zs"]

        elec_grid, field_grid = self._mk_grids(zs, elec_fn, self.field_fn)

        scan_start = self._mk_wells(**param_dict["scan_start"])
        scan_end = self._mk_wells(**param_dict["scan_end"])
        spectators = self._mk_wells(**param_dict["spectators"])

        # only supports a single well in solver
        if param_dict.get("split_settings", None) is None:
            settings = self.user_defaults["split_settings"]
        else:
            settings = self._mk_solver_settings(*param_dict["split_settings"],
                                                solver="Split")

        # need to fix argument order!
        arg_key = pyon.encode((
            elec_fn.names,
            zs,
            param_dict.get("split_settings", None),
            param_dict["scan_start"]["z"],
            param_dict["scan_start"]["width"],
            param_dict["scan_start"]["dphidx"],
            param_dict["scan_start"]["dphidy"],
            param_dict["scan_start"]["dphidz"],
            param_dict["scan_start"]["rx_axial"],
            param_dict["scan_start"]["ry_axial"],
            param_dict["scan_start"]["phi_radial"],
            param_dict["scan_start"]["d2phidaxial2"],
            param_dict["scan_start"]["d3phidz3"],
            param_dict["scan_start"]["d2phidradial_h2"],
            param_dict["scan_end"]["z"],
            param_dict["scan_end"]["width"],
            param_dict["scan_end"]["dphidx"],
            param_dict["scan_end"]["dphidy"],
            param_dict["scan_end"]["dphidz"],
            param_dict["scan_end"]["rx_axial"],
            param_dict["scan_end"]["ry_axial"],
            param_dict["scan_end"]["phi_radial"],
            param_dict["scan_end"]["d2phidaxial2"],
            param_dict["scan_end"]["d3phidz3"],
            param_dict["scan_end"]["d2phidradial_h2"],
            param_dict["spectators"]["z"],
            param_dict["spectators"]["width"],
            param_dict["spectators"]["dphidx"],
            param_dict["spectators"]["dphidy"],
            param_dict["spectators"]["dphidz"],
            param_dict["spectators"]["rx_axial"],
            param_dict["spectators"]["ry_axial"],
            param_dict["spectators"]["phi_radial"],
            param_dict["spectators"]["d2phidaxial2"],
            param_dict["spectators"]["d3phidz3"],
            param_dict["spectators"]["d2phidradial_h2"],
            param_dict["n_step"],
            param_dict["n_scan"],
        ))
        if self.cache_path is not None:
            with shelve.open(os.path.join(self.cache_path, "split.db")) as db:
                try:
                    return db[arg_key]
                except KeyError:
                    pass  # key not found

        voltages, sep_vec = self._solve_split(scan_start, scan_end, spectators,
                                              param_dict["n_step"],
                                              param_dict["n_scan"], elec_fn,
                                              self.field_fn, elec_grid, field_grid,
                                              settings)

        if self.cache_path is not None:
            with shelve.open(os.path.join(self.cache_path, "split.db")) as db:
                try:
                    db[arg_key] = (voltages, elec_fn.names, sep_vec)
                except ValueError:
                    pass  # value too large

        return voltages, elec_fn.names, sep_vec

    def dynamic(self, **param_dict):
        """Controls dynamic solver and handles julia objects

        This is required as sipyco can't serialise the julia objects.

        :param **param_dict: dictionary with execution information
            specify fields by using kwargs/unpacking a dictionary.
            Most parameters load sane defaults.

        :returns: voltage_array, electrode_name_tup
            voltage_array shape: (electrode_name_tup, n_time_steps).
        """
        names = param_dict.get("electrodes", None)
        if names is None:
            elec_fn = self.elec_fn
        else:
            elec_fn = self._select_elec(self.elec_fn, names)

        zs = param_dict.get("zs", None)
        if zs is None:
            zs = self.user_defaults["zs"]

        elec_grid, field_grid = self._mk_grids(zs, elec_fn, self.field_fn)

        wells0 = self._mk_wells(**param_dict["wells0"])
        wells1 = self._mk_wells(**param_dict["wells1"])

        trajectory = self._mk_trajectory(wells0, wells1, param_dict["n_step"])

        if param_dict.get("dynamic_settings", None) is None:
            settings = self.user_defaults["dynamic_settings"]
        else:
            settings = self._mk_solver_settings(*param_dict["dynamic_settings"],
                                                solver="Dynamic")

        v0 = [param_dict["volt_start"][name] for name in elec_fn.names]
        v1 = [param_dict["volt_end"][name] for name in elec_fn.names]

        # need to fix argument order!
        arg_key = pyon.encode((
            elec_fn.names,
            zs,
            param_dict.get("dynamic_settings", None),
            v0,
            v1,
            param_dict["wells0"]["z"],
            param_dict["wells0"]["width"],
            param_dict["wells0"]["dphidx"],
            param_dict["wells0"]["dphidy"],
            param_dict["wells0"]["dphidz"],
            param_dict["wells0"]["rx_axial"],
            param_dict["wells0"]["ry_axial"],
            param_dict["wells0"]["phi_radial"],
            param_dict["wells0"]["d2phidaxial2"],
            param_dict["wells0"]["d3phidz3"],
            param_dict["wells0"]["d2phidradial_h2"],
            param_dict["wells1"]["z"],
            param_dict["wells1"]["width"],
            param_dict["wells1"]["dphidx"],
            param_dict["wells1"]["dphidy"],
            param_dict["wells1"]["dphidz"],
            param_dict["wells1"]["rx_axial"],
            param_dict["wells1"]["ry_axial"],
            param_dict["wells1"]["phi_radial"],
            param_dict["wells1"]["d2phidaxial2"],
            param_dict["wells1"]["d3phidz3"],
            param_dict["wells1"]["d2phidradial_h2"],
            param_dict["n_step"],
        ))
        if self.cache_path is not None:
            with shelve.open(os.path.join(self.cache_path, "dynamic.db")) as db:
                try:
                    return db[arg_key]
                except KeyError:
                    pass  # key not found
        voltages = self._solve_dynamic(trajectory, v0, v1, elec_grid, field_grid,
                                       settings)

        if self.cache_path is not None:
            with shelve.open(os.path.join(self.cache_path, "dynamic.db")) as db:
                try:
                    db[arg_key] = voltages, elec_fn.names
                except ValueError:
                    pass  # value too large
        return voltages, elec_fn.names

    def get_all_electrode_names(self):
        """Return a list of all electrode names defined in the trap model"""
        return self.elec_fn.names

    def _mk_wells(self, z, width, dphidx, dphidy, dphidz, rx_axial, ry_axial,
                  phi_radial, d2phidaxial2, d3phidz3, d2phidradial_h2, **kwargs):
        """Struct, characterising target potential wells at a specific time.

        For n coexisting wells:
        * All arguments should be vectors of length n.
        * The i-th element of vectors characterises well i

        (phi is the electric potential)

        :param z: well position
        :param width: characteristic size of the well
        :param dphidx: x-compensation
        :param dphidy: y-compensation
        :param dphidz: z-compensation (for splitting)
        :param rx_axial: x-rotation of axial mode from z direction
        :param ry_axial: y-rotation of axial mode from z direction
        :param phi_radial: z-rotation aplied before other rotations
        :param d2phidaxial2: axial well strength
        :param d3phidz3: cubic z-field term (for splitting)
        :param d2phidradial_h2: horizontal radial mode frequency
        :param **kwargs: additional kwargs are ignored"""
        return self.jl.eval("PotentialWells")(z, width, dphidx, dphidy, dphidz,
                                              rx_axial, ry_axial, phi_radial,
                                              d2phidaxial2, d3phidz3, d2phidradial_h2)

    def _mk_trajectory(self, wells_start, wells_end, n_step):
        """Trajectory smoothly evolving wells_start to wells_end.

        :param wells_start: struct returned by self.mk_wells()
        :param wells_end: struct returned by self.mk_wells(). This should have
            the same number of wells as wells_start.
        :param n_step: numper of steps from start to end (both included)

        returns trajectory (Tuple of n_step wells structs)
        """
        return self.jl.eval("SURF.ModelTrajectories.create_shuttle_trajectory")(
            wells_start, wells_end, n_step)

    def _mk_grids(self, zs, elec_fn, field_fn):
        """Sample electrodes and external fields at positions zs

        return (ElectrodesGrid, FieldGrid)"""
        return (self.jl.eval("mk_electrodes_grid")(zs, elec_fn),
                self.jl.eval("mk_field_grid")(zs, field_fn))

    def _select_elec(self, elec, names):
        """Select a subset of electrodes to use"""
        # julia is 1-indexed
        indices = [elec.names.index(name) + 1 for name in names]
        return self.jl.eval("select_electrodes")(elec, indices)

    def _mk_solver_settings(self, *args, solver="Static"):
        return self.jl.eval("SURF." + solver + ".Settings")(*args)

    def _solve_static(self, wells, elec_grid, field_grid, settings):
        """Find voltages to best produce target wells

        :param wells: struct as returned by mk_wells
        :param elec_grid: gridded electrodes as returned by mk_grid
        :param field_grid: gridded external field as returned by mk_grid
        :param settings: solver settings struct

        :returns: voltage vector, elements match order of electrodes in
            elec_grid
        """
        weights_fn = self.jl.eval("mk_gaussian_weights")
        cull_fn = self.jl.eval("get_cull_indices")
        calc_target_fn = self.jl.eval("SURF.Static.calc_target")
        cost_fn = self.jl.eval("SURF.Static.cost_function")
        constraint_fn = self.jl.eval("SURF.Static.constraint")

        volt_set = self.jl.eval("SURF.Static.solver")(wells, elec_grid, field_grid,
                                                      weights_fn, cull_fn,
                                                      calc_target_fn, cost_fn,
                                                      constraint_fn, settings)
        return np.ascontiguousarray(np.array(volt_set))

    def _solve_dynamic(self, trajectory, v_set_start, v_set_end, elec_grid, field_grid,
                       settings):
        """Find voltages to best produce target trajectory (fixed start & end).

        :param trajectory: as returned by mk_trajectory
        :param v_set_start: vector specifying start voltages for electrodes
        :param v_set_end: vector specifying end voltages for electrodes
            (order matches v_set_start)
        :param elec_grid: gridded electrodes as returned by mk_grid
            (order matches v_sets)
        :param field_grid: gridded external field as returned by mk_grid
        :param settings: solver settings struct

        :returns: voltage array, (n_electrode, time_step)
        """
        weights_fn = self.jl.eval("mk_gaussian_weights")
        cull_fn = self.jl.eval("get_cull_indices")
        calc_target_fn = self.jl.eval("SURF.Dynamic.calc_target")
        cost_fn = self.jl.eval("SURF.Dynamic.cost_function")
        constraint_fn = self.jl.eval("SURF.Dynamic.constraint")

        volt_set = self.jl.eval("SURF.Dynamic.solver")(trajectory, elec_grid,
                                                       field_grid, v_set_start,
                                                       v_set_end, weights_fn, cull_fn,
                                                       calc_target_fn, cost_fn,
                                                       constraint_fn, settings)
        return np.ascontiguousarray(np.array(volt_set))

    def _solve_split(self, scan_start, scan_end, spectator, n_step, n_scan, elec_fn,
                     field_fn, elec_grid, field_grid, settings):
        """Find voltages for splitting/merging a well with spectator wells.

        The solver operates on a single well. This well evolves from well_start
        to well_end.

        :param scan_start: as returned by mk_wells. Only a single well is
            supported.
        :param scan_end: as returned by mk_wells. Only a single well is
            supported. This should only differ from scan_start in d2phidaxial2
        :param spectator: as returned by mk_wells. Static wells present during
            splitting.
        :param n_step: number of time steps in the splitting waveform
        :param n_scan: number of points in separation scan
        :param elec_fn: ElectrodesFn of electrodes to be used
        :param field_fn: FieldFn of external field
        :param settings: solver settings struct

        :return: voltage array, (n_electrode, time_step)
        """
        weights_fn = self.jl.eval("mk_gaussian_weights")
        cull_fn = self.jl.eval("get_cull_indices")
        volt_set, sep_vec = self.jl.eval("SURF.Split.solver")(
            scan_start, scan_end, spectator, n_step, n_scan, elec_fn, field_fn,
            elec_grid, field_grid, weights_fn, cull_fn, settings)
        return (np.ascontiguousarray(np.array(volt_set)), np.array(sep_vec))

    def ping(self):
        return True

    def close(self):
        pass

    def get_model_fields(self, zs, volt_dict):
        """get a dict of trap fields at specified positions for given voltages"""
        el_vec = list(volt_dict.keys())
        volt_vec_list = [list(volt_dict.values())]
        return {
            "zs": zs,
            "phi": self.get_model_field(zs, volt_vec_list, el_vec, "phi"),
            "dphidx": self.get_model_field(zs, volt_vec_list, el_vec, "dphidx"),
            "dphidy": self.get_model_field(zs, volt_vec_list, el_vec, "dphidy"),
            "dphidz": self.get_model_field(zs, volt_vec_list, el_vec, "dphidz"),
            "d2phidx2": self.get_model_field(zs, volt_vec_list, el_vec, "d2phidx2"),
            "d2phidy2": self.get_model_field(zs, volt_vec_list, el_vec, "d2phidy2"),
            "d2phidz2": self.get_model_field(zs, volt_vec_list, el_vec, "d2phidz2"),
            "d2phidxdy": self.get_model_field(zs, volt_vec_list, el_vec, "d2phidxdy"),
            "d2phidxdz": self.get_model_field(zs, volt_vec_list, el_vec, "d2phidxdz"),
            "d2phidydz": self.get_model_field(zs, volt_vec_list, el_vec, "d2phidydz"),
            "d3phidz3": self.get_model_field(zs, volt_vec_list, el_vec, "d3phidz3"),
            "d4phidz4": self.get_model_field(zs, volt_vec_list, el_vec, "d4phidz4"),
        }

    def get_model_field(self, zs, volt_vec_list, el_vec, field="phi"):
        """Get `field` at axial positions `zs` for all rows in `volt_vec_list`

        :param `el_vec`: vector matching electrode names to voltages
        """
        elec_fn = self._select_elec(self.elec_fn, el_vec)
        elec_grid, field_grid = self._mk_grids(zs, elec_fn, self.field_fn)
        order = np.array([el_vec.index(el) for el in elec_fn.names])
        # assignment in julia repel main name-space
        julia.Main.positions = zs
        julia.Main.field_grid = field_grid
        julia.Main.elec_grid = elec_grid
        julia.Main.volt_vec_list = [np.array(vs)[order] for vs in volt_vec_list]
        field = field.replace("phi", "\N{Greek Capital Letter Phi}")
        return self.jl.eval(
            f"(elec_grid.{field} * hcat(volt_vec_list...) .+ field_grid.{field})'")


if __name__ == "__main__":
    print("setting up solver")

    driver = SURF("Comet", "C:\\Users\\Marius\\scratch\\SURF\\src\\UserTraps\\")
    tmp = 6.333873616858256e8
    wells = driver.mk_wells([0.], [2e-5], [0.], [0.], [0.], [0.], [0.], [0.], [tmp / 6],
                            [0], [1.05 * tmp])
    grids = driver.mk_grids(driver.user_defaults["zs"], driver.elec_fn, driver.field_fn)
    print("calling solver")
    volt = driver.solve_static(wells, *grids, driver.user_defaults["static_settings"])
    print(volt)
