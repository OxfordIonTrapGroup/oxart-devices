import time
import serial
import logging
import asyncio
import numpy as np
from sipyco import pyon
from artiq.language.core import *

logger = logging.getLogger(__name__)



class TrapController:
    """A mediation layer to sanitise control of trap RF and DC voltages"""

    def __init__(self, dmgr, dc_config_file=None, rf_config=None):
        """dc_config: configuration dictionary for dc electrodes
        rf_config: configuration dictionary for rf electrodes
        """

        logger.info("Loading TrapController with dc_config: " + str(dc_config_file))

        if dc_config_file is not None:
            dc_config = pyon.load_file(dc_config_file)
            self._parse_dc_config(dmgr, dc_config)
            # Set the trap voltages to their default setting
            self.set_trap_setting(self._dc_default_trap_setting)

    def set_trap_setting(self, trap_setting):
        """Set the trap voltages to one of the pre-configured
        sets of voltages.
        """

        self._dc_logical_voltages = self._dc_trap_settings[trap_setting]

        # Update the physical voltages
        self._update_physical_voltages()

    def _update_physical_voltages(self, update_hw=True):
        """Updates the physical voltages based on the current
        logical voltage values.
        If update_hw is true, then the dac channels will be
        updated in hardware.
        """

        # Calculate the new physical values, through matrix multiplication
        self._dc_physical_voltages = self._dc_translation_matrix.dot(
            self._dc_logical_voltages)

        print(self._dc_logical_channel_names)
        print(self._dc_logical_voltages)
        print(self._dc_physical_channel_names)
        print(self._dc_physical_voltages)

        # If we are asked to update the voltages, do it
        if update_hw:
            # For each channel, set the voltage
            for i, voltage in enumerate(self._dc_physical_voltages):
                self._dc_hw_devices_lut[i].set_voltage(
                    self._dc_hw_channels_lut[i], voltage)


    def set_dc_voltage(self, logical_electrode, value, update_hw=True):
        """Set the value of a given logical dc electrode. Value is a float
        with units determined by the "relations" config element
        """

        # Find the index of the logical electrode, given its name
        logical_index = self._dc_logical_channel_names.index(
            logical_electrode)
        
        # Set the new logical value
        self._dc_logical_voltages[logical_index] = value

        # Update the physical voltages
        self._update_physical_voltages(update_hw)

    def get_dc_voltage(self, logical_electrode):
        """Reads the last set voltage on the given  logical electrode.
        """

        # Find the index of the logical electrode, given its name
        logical_index = self._dc_logical_channel_names.index(
            logical_electrode)
        
        # Return the value
        return self._dc_logical_voltages[logical_index]

    def ping(self):
        return True

    def _parse_dc_config(self, dmgr, dc_config):
        """Parse in the dc electrode configuration and check for errors.
        This function intialises the dc relation matrix and dc electrode
        vector.
        """

        # Produce a list of names of the logical channels
        self._dc_logical_channel_names = list(
            dc_config["logical_channels"])

        self._dc_physical_channel_names = list(
            dc_config["physical_channels"].keys())

        # An array containing the last set logical voltages
        self._dc_logical_voltages = np.zeros(
            len(self._dc_logical_channel_names))

        # An array containing the last set physical voltages
        self._dc_physical_voltages = np.zeros(
            len(self._dc_physical_channel_names))

        # The matrix converting between logical and phyiscal
        # voltages
        self._dc_translation_matrix = np.zeros((
            len(self._dc_physical_channel_names),
            len(self._dc_logical_channel_names)))

        # Populate the matrix.
        for i, physical_name in enumerate(self._dc_physical_channel_names):
            components = dc_config["relations"][physical_name]

            for logical_name in components.keys():
                j = self._dc_logical_channel_names.index(logical_name)
                self._dc_translation_matrix[i,j] = components[logical_name] 

        # Make a list of devices and channels indexed by physical
        # channel index. This is done to simplify looking through
        # the configuration during run-time
        self._dc_hw_devices_lut = []
        self._dc_hw_channels_lut = []
        for i, name in enumerate(self._dc_physical_channel_names):
            device_name = dc_config["physical_channels"][name]["device"]
            self._dc_hw_devices_lut.append(dmgr.get(device_name))
            self._dc_hw_channels_lut.append(
                dc_config["physical_channels"][name]["channel_id"])


        # Get the list of trap settings
        self._dc_trap_settings = {}
        for name in dc_config["trap_settings"].keys():
            logical_voltage_array = np.zeros(len(self._dc_logical_voltages))
            for electrode in dc_config["trap_settings"][name].keys():
                index = self._dc_logical_channel_names.index(electrode)
                logical_voltage_array[index] = \
                    dc_config["trap_settings"][name][electrode]
            self._dc_trap_settings[name] = logical_voltage_array

        # Store the default trap setting
        self._dc_default_trap_setting = dc_config["default_trap_setting"]



# Example config dictionary
# dc_config = {
#     # logical_channels: <list of logical channel names>
#     "logical_channels": [
#         "endcap",
#         "x_disp",
#         "y_comp",
#         "z_comp",
#         "mode_tilt",
#         "in_plane_twist",
#         "out_of_plane_twist",
#     ],
#     # physical_channels: <dictionary of physical channel descriptors>
#     #   "electrode_name": {
#     #       "device": <name of artiq device channel is controlled by>,
#     #       "channel_id": <id used to identify channel on device> 
#     #   }
#     "physical_channels": {
#         "left_rf": {"device":"trap_dac", "channel_id":1},
#         "center_control": {"device":"trap_dac", "channel_id":0},
#         "right_rf": {"device":"trap_dac", "channel_id":2},
#         "left_back": {"device":"trap_dac", "channel_id":13},
#         "left_center": {"device":"trap_dac", "channel_id":14},
#         "left_front": {"device":"trap_dac", "channel_id":10},
#         "right_back": {"device":"trap_dac", "channel_id":12},
#         "right_center": {"device":"trap_dac", "channel_id":11},
#         "right_front": {"device":"trap_dac", "channel_id":15},
#     },

#     # relations: <dictionary of dictionaries mapping physcial
#     #            electrodes to logical electrodes
#     "relations": {
#         "left_rf": {
#             "endcap": -9241.7,
#             "x_disp": 0.9065,
#             "y_comp": -0.3981,
#             "z_comp": 0.2129,
#             "mode_tilt": 0.1115,
#         },
#         "center_control": {
#             "endcap": -8449.2,
#             "x_disp": 0.7475,
#             "y_comp": -0.2843,   
#             "mode_tilt": 0.0795,
#         },
#         "right_rf": {
#             "endcap": -8966.2,
#             "x_disp":  0.8185,
#             "y_comp": -0.3981,
#             "z_comp": -0.2129,
#             "mode_tilt": 0.0721,
#         },
#         "left_back": {
#             "endcap": -42706.4,
#             "x_disp":  17.0,
#             "mode_tilt": 0.4557,
#             "in_plane_twist": 19400.0,
#             "out_of_plane_twist": -12800.0,
#         },
#         "left_center": {
#             "endcap": -9389.0,
#             "x_disp":  -4.1533,
#             "mode_tilt": -0.1672,
#             "in_plane_twist": -6420.0,
#             "out_of_plane_twist": 4230.0,
#         },
#         "left_front": {
#             "endcap": -42706.4,
#             "x_disp":  6.8814,
#             "mode_tilt": 0.4557,
#             "in_plane_twist": 6420.0,
#             "out_of_plane_twist": -4230.0,
#         },
#         "right_back": {
#             "endcap": 16665.6,
#             "x_disp": -2.8205,
#             "mode_tilt": -0.0121,
#             "in_plane_twist": -19400.0,
#             "out_of_plane_twist": 4230.0,
#         },
#         "right_center": {
#             "endcap": -42706.4,
#             "x_disp":  6.8814,
#             "mode_tilt": 0.4557,
#             "in_plane_twist": 6420.0,
#             "out_of_plane_twist": -4230.0,
#         },
#         "right_front": {
#             "endcap": 16665.6,
#             "x_disp":  -12.748,
#             "mode_tilt":  -0.0121,
#             "in_plane_twist": -6420.0,
#             "out_of_plane_twist": 12800.0,
#         },
#     },
#     # A dictionary of logical voltage settings
#     "trap_settings": {
#         "normal":{
#             "endcap": 0.25,
#             "x_disp": 0,
#             "y_comp": 284,
#             "z_comp": 268,
#             "mode_tilt": 10000,
#             "in_plane_twist": 0,
#             "out_of_plane_twist": 0,
#         },
#         "weak":{
#             "endcap": 0.1,
#             "x_disp": 0,
#             "y_comp": 284,
#             "z_comp": 268,
#             "mode_tilt": 10000,
#             "in_plane_twist": 0,
#             "out_of_plane_twist": 0,
#         },
#     },
#    # The default trap setting to load when initialising
#    "default_trap_setting": "normal",
# }        