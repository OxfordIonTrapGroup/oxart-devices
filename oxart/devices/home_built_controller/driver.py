import serial
import logging
from enum import Enum, unique

logger = logging.getLogger(__name__)


@unique
class MeasurementType(Enum):
    temperature = "temperature_celsius"
    current = "current_ampere"


class TemperatureController:

    def __init__(self, addr):
        self.ser = serial.serial_for_url(addr, baudrate=115200, timeout=2)

        logger.info("##########Setup###################")
        logger.info(f"Is there a serial connection? {self.ser.is_open}")
        self.ser.write(b"serial?\n")
        logger.info(f"Controller name: {self.ser.readline().decode().strip()}")

    def set_pid_parameters(self, tset, kp, ki, kd):
        self.ser.write("gain {:.2f} {:.2f} {:.2f}\n".format(kp, ki, kd).encode())
        self.ser.write("gain?\n".encode())
        logger.info("Gain settings? ", self.ser.readline().decode().strip())

        self.ser.write("tset {:.2f}\n".format(tset).encode())
        self.ser.write("tset?\n".encode())
        logger.info(f"Temperature setpoint?: {self.ser.readline().decode().strip()}")

        self.ser.write("resistiveload 0\n".encode())
        self.ser.write("resistiveload?\n".encode())
        logger.info(f"Unipolar?: {self.ser.readline().decode().strip()}")

        self.ser.write("calib {:.2f} {:.2f} {:.2f}\n".format(25, 0.9651, 3895).encode())
        self.ser.write("calib?\n".encode())
        logger.info(f"Thermistor calibration?: {self.ser.readline().decode().strip()}")

    def set_current(self, iset):
        self.ser.write("iset {:.2f}\n".format(iset).encode())
        self.ser.write("iset?\n".encode())
        logger.info(f"Current: {self.ser.readline().decode().strip()}")

    def enable_pid(self, enable):
        self.ser.write("reg {:.0f}\n".format(1 if enable else 0).encode())
        self.ser.write("reg?\n".encode())
        print(f"Regulator enabled?: {self.ser.readline().decode().strip()}")

    def get_measurement(self):
        self.ser.write("status?\n".encode())
        data = self.ser.readline().decode().strip()
        data = [float(num) for num in data.split(" ")]
        logger.info(f"Temperature: {data[0]}C, current: {data[2]}A")
        result = {
            MeasurementType.temperature: data[0],
            MeasurementType.current: data[2],
        }
        return result

    def close(self):
        self.ser.close()
