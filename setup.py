from setuptools import setup, find_packages

scripts = [
    "aqctl_andor_emccd=oxart.frontend.aqctl_andor_emccd:main",
    "aqctl_agilent_6671a=oxart.frontend.aqctl_agilent_6671a:main",
    "aqctl_booster=oxart.frontend.aqctl_booster:main",
    "aqctl_brooks_4850=oxart.frontend.aqctl_brooks_4850:main",
    "aqctl_current_stabilizer=oxart.frontend.aqctl_current_stabilizer:main",
    "aqctl_lakeshore_335=oxart.frontend.aqctl_lakeshore_335:main",
    "aqctl_scpi_dmm=oxart.frontend.aqctl_scpi_dmm:main",
    "aqctl_scpi_synth=oxart.frontend.aqctl_scpi_synth:main",
    "aqctl_surf_solver=oxart.frontend.aqctl_surf_solver:main",
    "aqctl_thorlabs_tcube=oxart.frontend.aqctl_thorlabs_tcube:main",
    "aqctl_tti_ql355=oxart.frontend.aqctl_tti_ql355:main",
    "aqctl_thorlabs_pm100a=oxart.frontend.aqctl_thorlabs_pm100a:main",
    "aqctl_v3500a=oxart.frontend.aqctl_v3500a:main",
    "aqctl_thermostat=oxart.frontend.aqctl_thermostat:main",
    "arduino_dac_controller=oxart.frontend.arduino_dac_controller:main",
    "bb_shutter_controller=oxart.frontend.bb_shutter_controller:main",
    "bme_pulse_picker_timing_controller=oxart.frontend.bme_pulse_picker_timing_controller:main",  # noqa
    "camera_viewer=oxart.frontend.camera_viewer:main",
    "conex_motor_controller=oxart.frontend.conex_motor_controller:main",
    "hoa2_dac_controller=oxart.frontend.hoa2_dac_controller:main",
    "holzworth_synth_controller=oxart.frontend.holzworth_synth_controller:main",
    "logger_solstis=oxart.frontend.logger_solstis:main",
    "ophir_controller=oxart.frontend.ophir_controller:main",
    "picomotor_controller=oxart.frontend.picomotor_controller:main",
    "scpi_awg_controller=oxart.frontend.scpi_awg_controller:main",
    "thorlabs_ddr25_controller=oxart.frontend.thorlabs_ddr25_controller:main",
    "thorlabs_ddr05_controller=oxart.frontend.thorlabs_ddr05_controller:main",
    "thorlabs_k10cr1_controller=oxart.frontend.thorlabs_k10cr1_controller:main",
    "thorlabs_mdt69xb_controller=oxart.frontend.thorlabs_mdt69xb_controller:main",
    "thorlabs_mdt693a_controller=oxart.frontend.thorlabs_mdt693a_controller:main",
    "thorlabs_bpc303_controller=oxart.frontend.thorlabs_bpc303_controller:main",
]

setup(
    name="oxart-devices",
    version="0.2",
    description="ARTIQ/SiPyCo-compatible drivers for laboratory equipment",
    author="Oxford Ion Trap Quantum Computing Group",
    packages=find_packages(),
    entry_points={"console_scripts": scripts},
    install_requires=["sipyco"],
    # zip_safe=False apparently improves compatibility for namespace packages:
    # https://github.com/pypa/sample-namespace-packages/issues/6
    zip_safe=False,
)
