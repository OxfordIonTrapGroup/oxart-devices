class MultipliedDDSWrapper:
    """Wraps an Arduino DDS class to allow profiles to be set in logical frequencies
    (detunings from zero field) rather than the physical frequencies that are the
    input to the mixup chain."""

    def __init__(self, dmgr, device, multiplier, invert_profile_lines=False):
        self.core = dmgr.get("core")
        self.dds = dmgr.get(device)

        # To get the DDS frequency, divide target frequency by multiplier
        # chain ratio
        self.multiplier = multiplier

        self.invert_profile_lines = invert_profile_lines

    def set_profile(self, profile, freq, phase=0.0, amp=1.0):
        freqDDS = freq / self.multiplier

        if self.invert_profile_lines:
            profile = 7 - profile

        self.dds.set_profile(profile, freqDDS, phase, amp)
