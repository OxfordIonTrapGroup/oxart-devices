""" Driver for current stabilizer """

from collections import OrderedDict
import argparse
import asyncio
import json
import logging
import math
import numpy as np
import socket
import sys


class StabilizerError(Exception):
    pass


class IIR:
    t_update = 2e-6
    full_scale = float((1 << 15) - 1)
    I_set_range = 21  # mA

    def __init__(self):
        self.ba = np.zeros(5, np.float32)
        self.y_offset = 0.
        self.y_min = -self.full_scale - 1
        self.y_max = self.full_scale

    def as_dict(self):
        iir = OrderedDict()
        iir["ba"] = [float(_) for _ in self.ba]
        iir["y_offset"] = self.y_offset
        iir["y_min"] = self.y_min
        iir["y_max"] = self.y_max
        return iir

    def configure_pi(self, kp, ki, g=0.):
        ki = np.copysign(ki, kp) * self.t_update * 2
        g = np.copysign(g, kp)
        eps = np.finfo(np.float32).eps
        if abs(ki) < eps:
            a1, b0, b1 = 0., kp, 0.
        else:
            if abs(g) < eps:
                c = 1.
            else:
                c = 1. / (1. + ki / g)
            a1 = 2 * c - 1.
            b0 = ki * c + kp
            b1 = ki * c - a1 * kp
            if abs(b0 + b1) < eps:
                raise ValueError("low integrator gain and/or gain limit")
        self.ba[0] = b0
        self.ba[1] = b1
        self.ba[2] = 0.
        self.ba[3] = a1
        self.ba[4] = 0.

    def set_x_offset(self, o):
        b = self.ba[:3].sum() * self.full_scale
        self.y_offset = b * o / self.I_set_range


class CPU_DAC:
    full_scale = 0xfff
    cpu_dac_range = 48  # mA
    conversion_factor = full_scale / cpu_dac_range

    def __init__(self):
        self.en = True
        self.out = np.zeros(1, np.float32)

    def set_out(self, out):
        assert out >= 0 and out <= 48, "cpu dac setting out of range"
        self.out = self.conversion_factor * out

    def set_en(self, en):
        self.en = en

    def as_dict(self):
        dac = OrderedDict()
        dac["out"] = int(self.out)
        dac["en"] = bool(self.en)
        return dac


class GPIO_HDR_SPI:
    full_scale = 0xffff
    cpu_dac_range = 250  # mA
    conversion_factor = full_scale / cpu_dac_range

    def set_gpio_hdr(self, gpio_hdr_word):
        assert gpio_hdr_word >= 0 and gpio_hdr_word <= 0xffff, "GPIO_HDR_SPI setting out of range"
        self.gpio_hdr_word = math.ceil(gpio_hdr_word * self.conversion_factor)


"""
class FeedfowardConfig:
    async def connect(self, host, port=1237):
        self.reader, self.writer = await asyncio.open_connection(host, port)

    async def set(self, cos_amplitudes, sin_amplitudes, offset):
        up = OrderedDict([("cos_amplitudes", cos_amps), 
                ("sin_amplitudes", sin_amps), ("offset", offset)])
        raw_msg = json.dumps(up, separators=(",", ":"))
        s.sendall(raw_msg.encode() + b"\n")
        data = s.recv(1024)
        assert "\n" not in s
        logger.debug("send %s", s)
        self.writer.write(s.encode() + b"\n")
        r = (await self.reader.readline()).decode()
        logger.debug("recv %s", r)
        ret = json.loads(r, object_pairs_hook=OrderedDict)
        if ret["code"] != 200:
            raise StabilizerError(ret)
        return ret
"""


class Feedforward:
    feedforward_range = 19  # mA
    conversion_factor = feedforward_range / 2  # [-1,1] maps to [-range/2,range/2]

    def __init__(self):
        pass

    def set_cosine_amplitudes(self, cos_amps):
        self.cos_amps = [a / self.conversion_factor for a in cos_amps]

    def set_sine_amplitudes(self, sin_amps):
        self.sin_amps = [a / self.conversion_factor for a in sin_amps]

    def set_offset(self, offset):
        self.offset = offset / self.conversion_factor


async def exchange_json(connection, request):
    reader, writer = connection

    s = json.dumps(request, separators=(",", ":"))
    assert "\n" not in s
    #logger.debug("send %s", s)
    writer.write(s.encode() + b"\n")

    r = (await reader.readline()).decode()
    #logger.debug("recv %s", r)
    ret = json.loads(r, object_pairs_hook=OrderedDict)
    if ret["code"] != 200:
        raise StabilizerError(ret)
    return ret


async def set_feedback(connection, channel, iir, dac, gpio_hdr):
    up = OrderedDict([("channel", channel), ("iir", iir.as_dict()),
                      ("cpu_dac", dac.as_dict()),
                      ("gpio_hdr_spi", gpio_hdr.gpio_hdr_word)])
    return await exchange_json(connection, up)


async def set_feedforward(connection, ff):
    msg = OrderedDict([("sin_amplitudes", ff.sin_amps), ("cos_amplitudes", ff.cos_amps),
                       ("offset", ff.offset)])
    return await exchange_json(connection, msg)


class Stabilizer:
    def __init__(self, fb_connection, ff_connection):
        self.fb_connection = fb_connection
        self.ff_connection = ff_connection

        # Feedback parameters
        self.channel = 0
        self.channel_offset = 0
        self.proportional_gain = 0
        self.integral_gain = 0
        self.cpu_dac_en = 1
        self.cpu_dac_output = 0
        self.gpio_hdr = 0

        # Feedforward parameters
        self.num_harmonics = 5
        self.sin_amps = [0 for n in range(self.num_harmonics)]
        self.cos_amps = [0 for n in range(self.num_harmonics)]
        self.ff_offset = 0

    def ping(self):
        return True

    async def set_feedback(self, frontend_offset = 250, proportional_gain = 1, integral_gain = 0, feedback_offset = 0, channel_offset = 0):
        d = CPU_DAC()
        d.set_out(feedback_offset)
        d.set_en(True)
        i = IIR()
        i.configure_pi(proportional_gain, integral_gain)
        i.set_x_offset(channel_offset)
        g = GPIO_HDR_SPI()
        g.set_gpio_hdr(frontend_offset)

        assert self.channel in range(2)
        await set_feedback(self.fb_connection, self.channel, i, d, g)

    async def set_feedforward(self, coefficients=None, offset=1):
        if coefficients is None:
            coefficients = np.zeros(self.num_harmonics)
        cos_amps = [coefficients[n].real for n in range(len(coefficients))]
        sin_amps = [-coefficients[n].imag for n in range(len(coefficients))]
        ff = Feedforward()
        ff.set_cosine_amplitudes(cos_amps)
        ff.set_sine_amplitudes(sin_amps)
        ff.set_offset(offset)

        await set_feedforward(self.ff_connection, ff)
