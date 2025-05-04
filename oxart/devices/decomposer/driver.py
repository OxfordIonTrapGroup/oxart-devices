"""This driver requires PyJulia & working julia install with configured PyCall

PyJulia doesn't play nice with conda. You should call this driver from the same
environment that you configured for PyCall in Julia. Instructions to configure
PyCall with conda are given in the README file of the SURF Julia library.
"""

import numpy as np
import os
import warnings

from julia.api import Julia

class Result:
    """
    Compare attributes to the Julia struct Decomposer.Solver.Result
    """
    def __init__(self, jl_result):
        self.error = jl_result.error
        self.ASFs = jl_result.ASFs
        self.PHIs = jl_result.PHIs
        self.ASF_max = jl_result.ASF_max
        self.ASF_scale = jl_result.ASF_scale
        self.wanted_unitaries = jl_result.wanted_unitaries
        self.ASF_pi = jl_result.ASF_pi
        self.error_per_pi_half_pulse = jl_result.error_per_pi_half_pulse
        self.dt = jl_result.dt
        self.n_qubits = jl_result.n_qubits
        self.n_pulses = jl_result.n_pulses
        self.fidelity_errors = jl_result.fidelity_errors
        self.squared_differences_error = jl_result.squared_differences_error
        self.avg_area_error = jl_result.avg_area_error
        self.mean_fidelity_error = jl_result.mean_fidelity_error
        self.min_number_of_pi_pulses = jl_result.min_number_of_pi_pulses
        self.avg_number_of_pi_pulses = jl_result.avg_number_of_pi_pulses
        self.max_number_of_pi_pulses = jl_result.max_number_of_pi_pulses
        self.is_converged = jl_result.is_converged
        self.cost_type = jl_result.cost_type
        self.optimisation_threshold = jl_result.optimisation_threshold

    def __str__(self):
        return f"Error: {self.error}, was successful: {self.is_converged}\nASFs: {self.ASFs}\nPHIs: {self.PHIs}"
    
    def to_dict(self):
        return {
            "error": self.error,
            "ASFs": self.ASFs,
            "PHIs": self.PHIs,
            "ASF_max": self.ASF_max,
            "ASF_scale": self.ASF_scale,
            "wanted_unitaries": self.wanted_unitaries,
            "ASF_pi": self.ASF_pi,
            "error_per_pi_half_pulse": self.error_per_pi_half_pulse,
            "dt": self.dt,
            "n_qubits": self.n_qubits,
            "n_pulses": self.n_pulses,
            "fidelity_errors": self.fidelity_errors,
            "squared_differences_error": self.squared_differences_error,
            "avg_area_error": self.avg_area_error,
            "mean_fidelity_error": self.mean_fidelity_error,
            "min_number_of_pi_pulses": self.min_number_of_pi_pulses,
            "avg_number_of_pi_pulses": self.avg_number_of_pi_pulses,
            "max_number_of_pi_pulses": self.max_number_of_pi_pulses,
            "is_converged": self.is_converged,
            "cost_type": self.cost_type,
            "optimisation_threshold": self.optimisation_threshold
        }

class Decomposer:
    def __init__(self,
                 num_threads=1,
                 cache_path=None) -> None:
        """
        :param cache_path: path on which to cache results (default: None)
                           disables the cache. NOT IMPLEMENTED
        """
        self.setup_done = False
        self.num_threads = num_threads
        self.cache_path = cache_path

        # This doesnt work yet for some reason, set JULIA_NUM_THREADS before starting server
        # For small numbers of qubits it appears that the scheduling with multiple threads takes more time than just running it on one thread
        # os.environ["JULIA_NUM_THREADS"] = str(self.num_threads)

        self.use_threads = "false"
        if int(self.num_threads) != 1:
            self.use_threads = "true"
        print(f"Use threads? {self.use_threads}")

        self.jl = Julia()  # compiled_modules=False)
        self.prepare_julia_environment()

    # def precompile(self):
    #     jl.eval(f"Load.precompile_decomposer({})")

    def prepare_julia_environment(self):
        # ===== Load packages =====
        self.jl.eval("using StaticArrays")
        self.jl.eval("using LinearAlgebra")
        self.jl.eval("using BenchmarkTools")

        self.jl.eval("import Decomposer")
        self.jl.eval("using Decomposer.Helper")
        self.jl.eval("using Decomposer.Solver")
        self.jl.eval("using Decomposer.Load")

    def setup_decomposer(self, n_qubits: int, n_pulses: int, cost_type: str = "FastAreaMinimisation", optimisation_threshold: float = 1e-7, precompile: bool=False) -> None:
        """
        Setup the decomposer with the given parameters

        :param n_qubits: number of qubits to compute pulse sequence for
        :param n_pulses: number of pulses in pulse sequence
        :param cost_type: type of cost function for different area minimisation techniques (NoAreaMinimisation|AreaMinimisation|[FastAreaMinimisation])
        :param optimisation_threshold: optimisation error threshold (default: 1e-7)
        :param precompile: precompile the decomposer for faster first execution (default: False)
        """
        self.n_qubits = n_qubits
        self.n_pulses = n_pulses
        self.cost_type = cost_type
        self.optimisation_threshold = optimisation_threshold
        self.precompile = precompile
        self.setup_done = True

        # ===== Prepare variables in julia =====
        self.jl.eval(f"n_qubits::Int64 = {self.n_qubits}")
        self.jl.eval(f"n_pulses::Int64 = {self.n_pulses}")
        self.jl.eval(f"cost_type::String = \"{self.cost_type}\"")
        self.jl.eval(f"use_threads::Bool = {self.use_threads}")
        self.jl.eval(f"optimisation_threshold::Float64 = {self.optimisation_threshold}")

        # ===== Precompile decomposition? =====
        if self.precompile:
            self.jl.eval(f"Load.precompile_decomposer(n_qubits, n_pulses, cost_type, use_threads)")

    def decompose(self, ASF_pis: list, ASF_max: float, target_rotations: list, ASF_scale: float=10.0) -> None:
        """
        Decompose target rotations into ASFs and PHIs.
        The rotations are given in the form [[x1,y1,z1], [x2,y2,z2], ...]
        If x,y,z rotations are given at the same time, then the rotation matrices are constructed for each axis and then multiplied together in the order z-y-x.

        :param ASF_pis: ASF required to drive pi pulse for each qubit
        :param ASF_max: maximum value for the ASF
        :param target_rotations: target rotations for each qubit in terms of pi/2 rotations around (x,y,z) axes. Float values can be given for each rotation.

        :return: result: Result object containing all relevant information
        """
        if not self.setup_done:
            raise ValueError("Decomposer not setup. Call setup_decomposer() first")
        if len(ASF_pis) != self.n_qubits:
            raise ValueError("Number of ASF_pis should be equal to number of qubits")
        if len(target_rotations) != self.n_qubits:
            raise ValueError("Number of target rotations should be equal to number of qubits")
        
        # ===== prepare variables in julia =====
        # setup ASF_pis
        self.jl.eval(f"ASF_pis = SVector{{n_qubits,Float64}}([{' '.join(str(i) for i in ASF_pis)}])")
        # setup ASF_max
        self.jl.eval(f"ASF_max = {ASF_max}")
        # setup ASF_scale
        self.jl.eval(f"ASF_scale = {ASF_scale}")
        # setup target rotations
        rotations_string = f"Rs = SVector{{n_qubits,SVector{{3,Float64}}}}(["
        for tr in target_rotations:
            rotations_string += f"SVector{{3,Float64}}({tr}),"
        rotations_string = rotations_string[:-1] + "])"
        self.jl.eval(rotations_string)

        # ===== Decompose target rotations =====
        self.jl.eval(f"""result = Solver.decompose_xyz_rotations(
                     n_qubits,
                     n_pulses,
                     ASF_pis,
                     Rs;
                     ASF_max=ASF_max,
                     ASF_scale=ASF_scale,
                     optimisation_threshold=optimisation_threshold,
                     cost_type=cost_type,
                     use_threads=use_threads)
                     """)
        
        # ===== Get results =====
        result_jl = self.jl.eval("result")
        result = Result(result_jl)
        print("Result")
        print(f"Error: {result.error}")

        return result.to_dict()

    def ping(self):
        return True
    
    def get_active_threads(self):
        num_threads = self.jl.eval("Threads.nthreads()")
        return num_threads
    
    # def compute_cliffords(self):
    #     pass

    # def close(self):
    #     pass

    # def print_results(self):
    #     pass


if __name__ == "__main__":
    print("Setting up Gate Decomposer...")
    dev = Decomposer(num_threads=4)
    dev.setup_decomposer(2, 6, "FastAreaMinimisation", 1e-7)
    result = dev.decompose(ASF_pis=0.1/np.array([1, 1.3]), ASF_max=0.6, target_rotations=[[1.0,0.0,0.0], [-1.0,0.0,0.0]])

    print(f"Error: {result.error}")
    print(f"Optimisation time: {result.dt}")
    print(f"ASFs: {result.ASFs}")
    print(f"PHIs: {result.PHIs}")

    print(dev.ping())
