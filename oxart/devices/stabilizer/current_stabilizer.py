""" Driver for current stabilizer """

from collections import OrderedDict
import asyncio
import json
import logging
import math
import numpy as np
import sys

logger = logging.getLogger(__name__)


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

    def configure_biquad(self, zeros, poles, gain=1.):
        """Calulate biquad iir filter coeficents
        The function constructs the iir coeficents for a transfer function with
        desired zeros and poles.
        :param zeros: list of upto two zero locations in Hz, must be real or
            complex conjugate pairs.
        :param poles: list of upto two pole locations in Hz, must be real or
            complex conjugate pairs.
        :param gain: gain scaling factor of transfer function.
        """
        def get_polynomial_coefs(factors):
            "convert factors to coeficents"
            if len(factors) == 0:
                return [1., 0., 0.]
            elif len(factors) == 1:
                if factors[0] != 0.:
                    return [1., 1. / factors[0], 0.]
                else:
                    return [0., 1., 0.]
            elif len(factors) == 2:
                div = factors[0] * factors[1]
                if div == 0.:
                    return [0., factors[0] + factors[1], 1.]
                else:
                    return [1., (factors[0] + factors[1]) / div, 1. / div]
            else:
                raise ValueError("Invalid number of factors")

        def z_transform(s_coefs, t_update):
            """
            z-transformation of second order s polynomial in coefficients

            This uses Tustin’s transformation
            see https://arxiv.org/pdf/1508.06319.pdf

            We drop a factor of 1/(1 + z^-1)^2 which is common to both
            polynomials
            """
            c = 2 / t_update

            z_coefs = [
                s_coefs[0] + c * s_coefs[1] + c * c * s_coefs[2],
                2 * s_coefs[0] - 2 * c * c * s_coefs[2],
                s_coefs[0] - c * s_coefs[1] + c * c * s_coefs[2],
                ]
            return z_coefs

        num_coefs = z_transform(get_polynomial_coefs(
            [2 * np.pi * x for x in zeros]), self.t_update)
        denom_coefs = z_transform(get_polynomial_coefs(
            [2 * np.pi * x for x in poles]), self.t_update)

        # normalise to a0 = 1 & apply gain factor
        num_coefs = [np.real(x / denom_coefs[0]) * gain for x in num_coefs]
        denom_coefs = [np.real(x / denom_coefs[0]) for x in denom_coefs]

        self.ba[0] = num_coefs[0]
        self.ba[1] = num_coefs[1]
        self.ba[2] = num_coefs[2]
        self.ba[3] = -denom_coefs[1]
        self.ba[4] = -denom_coefs[2]

    def configure_biquad(self, zeros, poles, gain=1.):
        """Calulate biquad iir filter coeficents
        The function constructs the iir coeficents for a transfer function with
        desired zeros and poles.
        :param zeros: list of upto two zero locations in Hz, must be real or
            complex conjugate pairs.
        :param poles: list of upto two pole locations in Hz, must be real or
            complex conjugate pairs.
        :param gain: gain scaling factor of transfer function.
        """

        def get_polynomial_coefs(factors):
            "convert factors to coeficents"
            if len(factors) == 0:
                return [1., 0., 0.]
            elif len(factors) == 1:
                if factors[0] != 0.:
                    return [1., 1. / factors[0], 0.]
                else:
                    return [0., 1., 0.]
            elif len(factors) == 2:
                div = factors[0] * factors[1]
                if div == 0.:
                    return [0., factors[0] + factors[1], 1.]
                else:
                    return [1., (factors[0] + factors[1]) / div, 1. / div]
            else:
                raise ValueError("Invalid number of factors")

        def z_transform(s_coefs, t_update):
            """
            z-transformation of second order s polynomial in coefficients

            This uses Tustin’s transformation
            see https://arxiv.org/pdf/1508.06319.pdf

            We drop a factor of 1/(1 + z^-1)^2 which is common to both
            polynomials
            """
            c = 2 / t_update

            z_coefs = [
                s_coefs[0] + c * s_coefs[1] + c * c * s_coefs[2],
                2 * s_coefs[0] - 2 * c * c * s_coefs[2],
                s_coefs[0] - c * s_coefs[1] + c * c * s_coefs[2],
            ]
            return z_coefs

        num_coefs = z_transform(get_polynomial_coefs([2 * np.pi * x for x in zeros]),
                                self.t_update)
        denom_coefs = z_transform(get_polynomial_coefs([2 * np.pi * x for x in poles]),
                                  self.t_update)

        # normalise to a0 = 1 & apply gain factor
        num_coefs = [np.real(x / denom_coefs[0]) * gain for x in num_coefs]
        denom_coefs = [np.real(x / denom_coefs[0]) for x in denom_coefs]

        self.ba[0] = num_coefs[0]
        self.ba[1] = num_coefs[1]
        self.ba[2] = num_coefs[2]
        self.ba[3] = -denom_coefs[1]
        self.ba[4] = -denom_coefs[2]

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
        assert gpio_hdr_word >= 0 and gpio_hdr_word <= 0xffff, \
            "GPIO_HDR_SPI setting out of range"
        self.gpio_hdr_word = math.ceil(gpio_hdr_word * self.conversion_factor)


class Feedforward:

    def __init__(self, num_harmonics):
        self.conversion_factor = 1 / 500  # [0, 500uA] maps to [0, 1]
        self.num_harmonics = num_harmonics
        self.sin_amps = [0 for n in range(self.num_harmonics)]
        self.cos_amps = [0 for n in range(self.num_harmonics)]
        self.ff_offset = 0

    def set_cosine_amplitudes(self, cos_amps):
        self.cos_amps = [a * self.conversion_factor for a in cos_amps]

    def set_sine_amplitudes(self, sin_amps):
        self.sin_amps = [a * self.conversion_factor for a in sin_amps]

    def set_offset(self, offset):
        self.offset = offset * self.conversion_factor


async def exchange_json(connection, request):
    reader, writer = connection

    s = json.dumps(request, separators=(",", ":"))
    assert "\n" not in s
    logger.debug("send %s", s)
    writer.write(s.encode() + b"\n")

    TIMEOUT = 5
    try:
        r = (await asyncio.wait_for(reader.readline(), timeout=TIMEOUT)).decode()
    except asyncio.TimeoutError:
        logger.exception(
            "Stabilizer failed to respond within %s seconds "
            "(firmware possibly crashed); exiting.", TIMEOUT)
        sys.exit(1)
    except ConnectionResetError:
        logger.exception("Connection to Stabilizer lost; exiting.")
        sys.exit(1)
    logger.debug("recv %s", r)
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

    def ping(self):
        return True

    async def set_feedback(self,
                           frontend_offset=250,
                           proportional_gain=1,
                           integral_gain=0,
                           feedback_offset=0,
                           channel_offset=0):
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

    async def set_feedback_biquad(self,
                                  frontend_offset=250,
                                  zeros=[],
                                  poles=[],
                                  gain=1.,
                                  feedback_offset=0,
                                  channel_offset=0):
        d = CPU_DAC()
        d.set_out(feedback_offset)
        d.set_en(True)
        i = IIR()
        i.configure_biquad(zeros, poles, gain)
        i.set_x_offset(channel_offset)
        g = GPIO_HDR_SPI()
        g.set_gpio_hdr(frontend_offset)

        assert self.channel in range(2)
        await set_feedback(self.fb_connection, self.channel, i, d, g)

    async def set_feedback_biquad(self,
                                 frontend_offset=250,
                                 zeros=[],
                                 poles=[],
                                 gain = 1.,
                                 feedback_offset=0,
                                 channel_offset=0):
        d = CPU_DAC()
        d.set_out(feedback_offset)
        d.set_en(True)
        i = IIR()
        i.configure_biquad(zeros, poles, gain)
        i.set_x_offset(channel_offset)
        g = GPIO_HDR_SPI()
        g.set_gpio_hdr(frontend_offset)

        assert self.channel in range(2)
        await set_feedback(self.fb_connection, self.channel, i, d, g)

    async def set_feedforward(self, coefficients=None, offset=0):
        if coefficients is None:
            coefficients = np.zeros(self.num_harmonics)
        cos_amps = [coefficients[n].real for n in range(len(coefficients))]
        sin_amps = [coefficients[n].imag for n in range(len(coefficients))]
        ff = Feedforward(self.num_harmonics)
        ff.set_cosine_amplitudes(cos_amps)
        ff.set_sine_amplitudes(sin_amps)
        ff.set_offset(offset)
        await set_feedforward(self.ff_connection, ff)
