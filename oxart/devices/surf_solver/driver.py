"""This driver requires PyJulia & working julia install with configured PyCall

PyJulia doesn't play nice with conda. The best way to use a conda environment
with this driver is by calling the frontend/driver from Julia using PyCall
configured for the conda environment"""

import numpy as np
import julia

class SURF:
    """SURF Uncomplicated Regional Fields"""
    def __init__(self, user_trap="Comet", julia_lib_path=None):
        self.jl = julia.Julia(init_julia=False, runtime="C:\\Julia\\bin\\julia.exe")

        if julia_lib_path != None:
            self.jl.eval("cd")(julia_lib_path)
        else:
            julia_lib_path = self.jl.eval("pwd()")

        self.jl.eval("using Pkg")
        self.jl.eval("Pkg.activate")(julia_lib_path)

        self.jl.eval("import SURF")
        self.jl.eval("using SURF.Electrodes")
        self.jl.eval("using SURF.ExternalField")
        self.jl.eval("using SURF.Traps")
        self.jl.eval("using SURF.DataSelect")

        self.raw_elec_grid, self.raw_field_grid = self.jl.eval(
            "SURF." + user_trap + ".load_grids"
            )(julia_lib_path+"\\src\\UserTraps\\")
        self.elec_fn = self.jl.eval("mk_electrodes_fn")(self.raw_elec_grid)
        self.field_fn = self.jl.eval("mk_field_fn")(self.raw_field_grid)

        # recommended default values for user
        self.user_defaults = {
            "zs": self.jl.eval(
                "SURF." + user_trap + ".zs"),
            "static_maw_settings": self.jl.eval(
                "SURF." + user_trap + ".static_maw_settings"),
            "dynamic_free_maw_settings": self.jl.eval(
                "SRUF." + user_trap + ".dynamic_free_maw_settings"),
            "dynamic_clamped_maw_settings": self.jl.eval(
                "SRUF." + user_trap + ".dynamic_clamped_maw_settings"),
            "splitting_maw_settings": self.jl.eval(
                "SRUF." + user_trap + ".splitting_maw_settings"),
        }

    def mk_wells(self, z, width, dphidx, dphidy, dphidz,
                 rx_axial, ry_axial, phi_radial,
                 d2phidz2, d3phidz3, d2phidradial_h2):
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
        """
        return self.jl.eval("PotentialWells")(z, width, dphidx, dphidy, dphidz,
                 rx_axial, ry_axial, phi_radial,
                 d2phidz2, d3phidz3, d2phidradial_h2)

    def mk_trajectory(self, wells_start, wells_end, n_step):
        """Trajectory smoothly evolving wells_start to wells_end.

        :param wells_start: struct returned by self.mk_wells()
        :param wells_end: struct returned by self.mk_wells(). This should have the
            same number of wells as wells_start.
        :param n_step: numper of steps from start to end (both included)

        returns trajectory (Tuple of n_step wells structs)
        """
        return self.jl.eval(
            "SRUF.ModelTrajectories.create_shuttle_trajectory")(
            wells_start, wells_end, n_step)

    def mk_grids(self, zs, elec_fn, field_fn):
        """Sample electrodes and external fields at positions zs

        return (ElectrodesGrid, FieldGrid)"""
        return (self.jl.eval("mk_electrodes_grid")(zs, elec_fn),
                self.jl.eval("mk_field_grid")(zs, field_fn))

    def select_elec(self, elec, names):
        """Select a subset of electrodes to use"""
        # julia is 1-indexed
        indices = [elec.names.index(name) + 1 for name in names]
        return self.jl.eval("select_electrodes")(elec, indices)

    def mk_solver_settings(self, solver="StaticMAW", *args):
        return self.jl.eval("SRUF."+solver+".Settings")(*args)1

    def solve_static(self, wells, elec_grid, field_grid, settings):
        """Find voltages to best produce target wells

        :param wells: struct as returned by mk_wells
        :param elec_grid: gridded electrodes as returned by mk_grid
        :param field_grid: gridded external field as returned by mk_grid
        :param settings: solver settings struct

        :returns: voltage vector, elements match order of electrodes in elec_grid
        """
        weights_fn = self.jl.eval("mk_gaussian_weights")
        cull_fn = self.jl.eval("get_cull_indices")
        calc_target_fn = self.jl.eval("SRUF.StaticMAW.calc_target")
        cost_fn = self.jl.eval("SRUF.StaticMAW.cost_function")
        constraint_fn = self.jl.eval("SRUF.StaticMAW.constraint")

        volt_set = self.jl.eval("SRUF.StaticMAW.solver")(
            wells, elec_grid, field_grid, weights_fn, cull_fn, calc_target_fn,
            cost_fn, constraint_fn, settings)
        return volt_set

    def solve_dynamic_clamped(self, trajectory, v_set_start, v_set_end,
                              elec_grid, field_grid, settings):
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
        calc_target_fn = self.jl.eval("SRUF.DynamicClampedMAW.calc_target")
        cost_fn = self.jl.eval("SRUF.DynamicClampedMAW.cost_function")
        constraint_fn = self.jl.eval("SRUF.DynamicClampedMAW.constraint")

        volt_set = self.jl.eval("SURF.DynamicClampedMAW.solver")(
            trajectory, elec_grid, field_grid, v_set_start, v_set_end,
            weights_fn, cull_fn, calc_target_fn, cost_fn, constraint_fn,
            settings)
        return volt_set

    def solve_dynamic_free(self, trajectory, elec_grid, field_grid, settings):
        """Find voltages to best produce target trajectory.
        Start and end voltages are floated.

        :param trajectory: as returned by mk_trajectory
        :param elec_grid: gridded electrodes as returned by mk_grid
            (order matches v_sets)
        :param field_grid: gridded external field as returned by mk_grid
        :param settings: solver settings struct

        :returns: voltage array, (n_electrode, time_step)
        """
        weights_fn = self.jl.eval("mk_gaussian_weights")
        cull_fn = self.jl.eval("get_cull_indices")
        calc_target_fn = self.jl.eval("SURF.DynamicFreeMAW.calc_target")
        cost_fn = self.jl.eval("SURF.DynamicFreeMAW.cost_function")
        constraint_fn = self.jl.eval("SURF.DynamicFreeMAW.constraint")

        volt_set = self.jl.eval("SURF.DynamicFreeMAW.solver")(
            trajectory, elec_grid, field_grid, weights_fn, cull_fn,
            calc_target_fn, cost_fn, constraint_fn, settings)
        return volt_set

    def solve_splitting(self, well_start, well_end, n_step, n_scan, settings):
        """Find voltages for splitting/merging a well.

        The solver operates on a single well. This well evolves from well_start
        to well_end.

        :param well_start: as returned by mk_wells. Only a single well is
            supported.
        :param well_end: as returned by mk_wells. Only a single well is
            supported. This should only differ from well_start in d2Φdaxial2
        :param n_step: number of time steps in the splitting waveform
        :param n_scan: number of points in separation scan
        :param settings:solver settings struct

        :return: voltage array, (n_electrode, time_step)
        """
        volt_set = self.jl.eval("SURF.SplittingMAW.solver")(
            well_start, well_end, n_step, n_scan, self.elec_fn, self.field_fn,
            settings)
        return volt_set

    def ping(self):
        return True

    def close(self):
        pass

if __name__=="__main__":
    print("hello world")
    # driver = IonMover("C:\\Users\\Marius\\scratch\\SURF")
