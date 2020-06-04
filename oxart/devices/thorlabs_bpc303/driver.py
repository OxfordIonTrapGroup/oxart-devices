from oxart.devices.thorlabs_apt.driver import MGMSG, SRC_DEST, Message, MsgError
import struct
import sipyco.pyon as pyon
import serial
import logging

logger = logging.getLogger(__name__)

# Conventions in the following:
# A card occupies a bay in the rack and has a number of channels.
# There is a RACK_CONTROLLER, which routes signals down to RACK_BAYs
# if specified as destination.
# bay_id: one of [1, 2, 3, (4, 5, 6, 7, 8, 9, 10)]
# bay_idx: one of [0, 1, 2, (3, 4, 5, 6, 7, 8, 9)]
# channel: always channel 0 for all bays of BPC303. The same holds for most APT devices.

NUM_SLOTS_MAX = 10
PZ_TRAVEL_UM = 20.0
PZ_MAX_VOLTAGE = 75.0

class _APTCardSlotDevice:
    def __init__(self, port):
        self.h = serial.Serial(port, 115200, write_timeout=0.1)
        self._status_update_counter = 0

        # Detect occupied bays
        self.bays = []
        for bay_idx in range(NUM_SLOTS_MAX):
            msg = self._send_request(
                MGMSG.RACK_REQ_BAYUSED,
                param1 = bay_idx,
                wait_for = [MGMSG.RACK_GET_BAYUSED])
            bay_is_occupied = (msg.param2 == 0x01)
            logger.info("{} is {}".format(
                bay_idx,
                "occupied" if bay_is_occupied else "not occupied"))
            if bay_is_occupied:
                self.bays.append(SRC_DEST["RACK_BAY_{}".format(bay_idx)])

    def _send_message(self, message):
        msg = message.pack()
        logger.debug("Sending: {}".format(message))
        logger.debug("tx: {}".format(msg.hex()))
        self.h.write(msg)

    def _read_message(self):
        header = self.h.read(6)
        data = b""
        if header[4] & 0x80:
            (length, ) = struct.unpack("<H", header[2:4])
            data = self.h.read(length)
        msg = Message.unpack(header + data)
        logger.debug("rx: {}{}".format(header.hex(), data.hex()))
        logger.debug("Received: {}".format(msg))
        return msg

    def _send_request(self, msgreq_id, wait_for,
        param1 = 0, param2 = 0,
        dest = SRC_DEST["RACK_CONTROLLER"].value,
        data=None):
        self._send_message(Message(msgreq_id, param1, param2, dest, data=data))
        while True:
            msg = self._read_message()
            self._triage_message(msg)

            if msg._id in wait_for:
                return msg

    def _triage_message(self, msg):
        """Triage an incoming message in case of errors or action required"""
        msg_id = msg._id
        data = msg.data

        if msg_id == MGMSG.HW_DISCONNECT:
            raise MsgError("Error: Please disconnect")
        elif msg_id == MGMSG.HW_RESPONSE:
            raise MsgError("Hardware error, please disconnect")
        elif msg_id == MGMSG.HW_RICHRESPONSE:
            (code, ) = struct.unpack("<H", data[2:4])
            raise MsgError("Hardware error {}: {}"
                           .format(code,
                                   data[4:].decode(encoding="ascii")))
        elif msg_id == MGMSG.PZ_GET_PZSTATUSUPDATE:
            self._status_update_counter += 1
            if self._status_update_counter > 25:
                logger.debug("Acking status updates")
                self._status_update_counter = 0
                self.ack_status_update()

    def identify(self, bay_id):
        """ Corresponding screen will start blinking on frontpanel """
        self._send_message(Message(MGMSG.MOD_IDENTIFY, param1=bay_id-1))

    def set_enable(self, bay_id, enable=True, channel=0):
        """ Enables a bay """
        active = 1 if enable else 2
        self._send_message(Message(MGMSG.MOD_SET_CHANENABLESTATE,
            param1=channel, param2=active, dest = self.bays[bay_id-1]))

    def get_enable(self, bay_id, channel=0):
        """ Return whether that bay is enabled """
        msg = self._send_request(
            MGMSG.MOD_REQ_CHANENABLESTATE,
            wait_for = [MGMSG.MOD_GET_CHANENABLESTATE],
            dest = self.bays[bay_id-1],
            param1 = channel)
        if (msg.param2 == 0x01):
            return True
        if (msg.param2 == 0x02):
            return False

    def get_status_bits(self, bay_id):
        msg = self._send_request(
            MGMSG.PZ_REQ_PZSTATUSBITS,
            wait_for=[MGMSG.PZ_GET_PZSTATUSBITS],
            dest=self.bays[bay_id-1])
        chan, status = struct.unpack("=HI", msg.data)
        return status

    def ack_status_update(self):
        self._send_message(Message(
            MGMSG.PZ_ACK_PZSTATUSUPDATE,
            dest=SRC_DEST["RACK_CONTROLLER"].value))

    def get_serial(self):
        msg = self._send_request(
            MGMSG.HW_REQ_INFO,
            wait_for=[MGMSG.HW_GET_INFO],
            dest=SRC_DEST["RACK_CONTROLLER"].value)
        serial, model, hw_type, firmware, _, hw_version, mod, num_channels = \
        struct.unpack("=L8sH4s60sHHH", msg.data)
        return serial

    def ping(self):
        try:
            for i,_ in enumerate(self.bays):
                self.get_status_bits(i+1)
        except:
            return False
        return True

    def close(self):
        """Close the serial port."""
        self.h.close()

# Need for mdt69xb mediator to work:
# get_channel('x')
# set_channel('x', 27.4)
# get_channel_output('x')
# save_setpoints()

class BPC303(_APTCardSlotDevice):
    def __init__(self, port, enable_feedback=False):
        super().__init__(port)
        logger.info("Device vlimit is {}, travel is {}um".format(PZ_MAX_VOLTAGE, PZ_TRAVEL_UM))
        self.fname = "piezo_{}.pyon".format(self.get_serial())
        self.voltages = {"volt_{}".format(i): -1 for i in range(len(self.bays))}
        self.positions = {"pos_{}".format(i): -1 for i in range(len(self.bays))}
        self.enable_feedback = en_fb
        self._load_setpoints()
        self.setup()

    def setup(self):
        for b in range(len(self.bays)):
            self.set_voltage_limit(b+1, PZ_MAX_VOLTAGE)
            self.set_enable(b+1)
            # Enable feedback -> Only set_position commands take effect
            self.set_enable_feedback(b+1, enable=self.enable_feedback)
    #
    ### Functions interfacing with the mediator
    #
    def set_channel(self, channel_char, value):
        """Set one of the axes ('x', 'y', 'z') to a certain value"""
        self._check_valid_channel(channel_char)
        bay_id = ord(channel_char) - ord('w')
        if self.enable_feedback:
            self.set_position(bay_id, value)
        else:
            self.set_voltage(bay_id, value)

    def get_channel(self, channel_char):
        """ Get last value set from this driver (don't query hardware) """
        self._check_valid_channel(channel_char)
        bay_idx = ord(channel_char) - ord('x')
        if self.enable_feedback:
            return self.positions["pos_{}".format(bay_idx)]
        else:
            return self.voltages["volt_{}".format(bay_idx)]

    def get_channel_output(self, channel_char):
        """ Get actual output value (query hardware) """
        self._check_valid_channel(channel_char)
        bay_id = ord(channel_char) - ord('w')
        if self.enable_feedback:
            return self.get_position(bay_id)
        else:
            return self.get_voltage(bay_id)
    #
    ### Internal functions
    #
    def set_voltage(self, bay_id, voltage, channel=0):
        """
        Set a piezo to a given voltage.
        In closed-loop control, this is ignored.
        """
        voltage = float(voltage)
        self._check_voltage_in_limit(voltage)
        payload = struct.pack("<Hh", channel, int(voltage*32767/PZ_MAX_VOLTAGE))
        self._send_message(Message(
            MGMSG.PZ_SET_OUTPUTVOLTS,
            dest=self.bays[bay_id-1],
            data=payload))
        self.voltages["volt_{}".format(bay_id-1)] = voltage
        self._save_setpoints()

    def get_voltage(self, bay_id, channel=0):
        msg = self._send_request(
            MGMSG.PZ_REQ_OUTPUTVOLTS,
            wait_for=[MGMSG.PZ_GET_OUTPUTVOLTS],
            dest=self.bays[bay_id-1],
            param1=channel)
        chan, v = struct.unpack("=Hh", msg.data)
        return v/32767*PZ_MAX_VOLTAGE

    def set_position(self, bay_id, position, channel=0):
        """
        Set a piezo to a given position.
        In open-loop mode, this is ignored.
        """
        position = float(position)
        self._check_position_in_limit(position)
        payload = struct.pack("<HH", channel, int(position*32767.0/PZ_TRAVEL_UM))
        self._send_message(Message(
            MGMSG.PZ_SET_OUTPUTPOS,
            dest=self.bays[bay_id-1],
            data=payload))
        self.positions["pos_{}".format(bay_id-1)] = position
        self._save_setpoints()

    def get_position(self, bay_id, channel=0):
        msg = self._send_request(
            MGMSG.PZ_REQ_OUTPUTPOS,
            wait_for=[MGMSG.PZ_GET_OUTPUTPOS],
            dest=self.bays[bay_id-1],
            param1=channel)
        chan, pos = struct.unpack("=HH", msg.data)
        return pos/32767.0*PZ_TRAVEL_UM

    def set_enable_feedback(self, bay_id, enable=True, smooth=True, channel=0):
        """
        When in closed‐loop mode, position is maintained by a feedback signal
        from the piezo actuator.
        If set to Smooth, the transition from open to closed loop (or vice versa)
        is achieved over a longer period in order to minimize voltage transients.
        """
        if enable:
            mode = 0x02
        else:
            mode = 0x01
        if smooth:
            mode += 2

        self._send_message(Message(
            MGMSG.PZ_SET_POSCONTROLMODE,
            dest=self.bays[bay_id-1],
            param1=channel,
            param2=mode))

    def get_enable_feedback(self, bay_id, channel=0):
        msg = self._send_request(
            MGMSG.PZ_REQ_POSCONTROLMODE,
            wait_for=[MGMSG.PZ_GET_POSCONTROLMODE],
            dest=self.bays[bay_id-1],
            param1=channel)
        return not msg.param2 % 2

    def set_voltage_limit(self, bay_id, voltage, channel=0):
        if voltage > 150 or voltage < 0:
            raise ValueError(
                "{}V not between 0V and 150V".format(voltage))
        payload = struct.pack("<HHH", channel, int(10*voltage), 0)
        self._send_message(Message(
            MGMSG.PZ_SET_OUTPUTMAXVOLTS,
            dest=self.bays[bay_id-1],
            data=payload))

    def get_voltage_limit(self, bay_id):
        msg = self._send_request(
            MGMSG.PZ_REQ_OUTPUTMAXVOLTS,
            wait_for = [MGMSG.PZ_GET_OUTPUTMAXVOLTS],
            dest=self.bays[bay_id-1])
        chan, voltage_limit, flags = struct.unpack("=HHH", msg.data)
        return voltage_limit/10.0

    def get_pi_constants(self, bay_id, channel=0):
        msg = self._send_request(
            MGMSG.PZ_REQ_PICONSTS,
            wait_for = [MGMSG.PZ_GET_PICONSTS],
            param1=channel,
            dest=self.bays[bay_id-1])
        chan, prop_gain, int_gain = struct.unpack("=HHH", msg.data)
        return prop_gain, int_gain

    def set_pi_constants(self, bay_id, prop_gain, int_gain, channel=0):
        payload = struct.pack("<HHH", channel, prop_gain, int_gain)
        self._send_message(Message(
            MGMSG.PZ_SET_PICONSTS,
            dest=self.bays[bay_id-1],
            data=payload))

    #
    ### Safety functions
    #
    def _check_voltage_in_limit(self, voltage):
        """Raises a ValueError if the voltage is not in limit for the current
        controller settings"""
        if voltage > PZ_MAX_VOLTAGE or voltage < 0:
            raise ValueError(
                "{}V not between 0 and vlimit={}".format(voltage, PZ_MAX_VOLTAGE))

    def _check_position_in_limit(self, position):
        """Raises a ValueError if the position is not in limit for the current
        controller settings"""
        if position > PZ_TRAVEL_UM or position < 0:
            raise ValueError(
                "Position {}μm not between 0μm and travel={}μm".format(position, PZ_TRAVEL_UM))

    def _check_valid_channel(self, channel):
        """Raises a ValueError if the channel is not valid"""
        if channel not in 'xyz':
            raise ValueError("Channel must be one of 'x', 'y', or 'z'")
    #
    ### Save file operations
    #
    def _load_setpoints(self):
        """Load setpoints from a file"""
        try:
            self.voltages, self.positions = pyon.load_file(self.fname)
            logger.info(
                "Loaded '{}', voltages: {}, positions: {}".format(
                    self.fname, self.voltages, self.positions))
        except FileNotFoundError:
            logger.warning(
                "Couldn't find '{}', no setpoints loaded".format(self.fname))

    def _save_setpoints(self):
        """Write the setpoints out to file"""
        pyon.store_file(self.fname, [self.voltages, self.positions])
        logger.debug(
            "Saved '{}', voltages: {}, positions: {}".format(
                self.fname, self.voltages, self.positions))

    def save_setpoints(self):
        """Deprecated: setpoints are saved internally on every set command"""
        self._save_setpoints()
