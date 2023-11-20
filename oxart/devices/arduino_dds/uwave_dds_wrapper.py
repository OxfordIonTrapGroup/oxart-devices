class UWaveDDSWrapper:
    """Wraps an Arduino DDS class to allow profiles to be set in
    logical frequencies (detunings from zero field) rather than the
    physical frequencies that are the input to the mixup chain
    """

    def __init__(self, dmgr, device, lo_frequency):
        self.core = dmgr.get("core")
        self.dds = dmgr.get(device)

        # S1/2 F=4 - F=3 splitting at zero field, Hz
        zero_field_frequency = 3225.6082864e6

        # To get the DDS frequency, subtract off target frequency from
        # this offset frequency
        self.offset_frequency = -lo_frequency + zero_field_frequency

    def set_profile(self, profile, freq, phase=0.0, amp=1.0):
        freqDDS = self.offset_frequency + freq

        self.dds.set_profile(profile, freqDDS, phase, amp)
