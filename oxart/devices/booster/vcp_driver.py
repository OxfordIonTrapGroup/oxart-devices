import serial
import time


class BoosterVCP:
    """ Skeletal Booster VCP driver for debugging only """
    def __init__(self, device):
        self.dev = serial.serial_for_url(device)

        self.dev.write(b"STOP\n")  # terminate any logging
        time.sleep(0.1)
        self.dev.flushInput()

        assert self.ping()

    def _cmd(self, cmd, lines=1):
        """ Sends a command and returns the response string """
        self.dev.write((cmd + '\n').encode())

        # echo
        resp = self.dev.readline().decode()
        if resp.startswith('> '):
            resp = resp[1:]
        if resp.strip() != cmd:
            print(resp)
            raise Exception("Unexpected response to '{}': '{}'".format(
                cmd, resp))

        if lines == 1:
            return self.dev.readline().decode().strip()

        resp = [""]*lines
        for line in range(lines):
            resp[line] = self.dev.readline().decode().strip()
        return resp

    def get_version(self):
        """ Returns the device version string """
        return self._cmd('version')


    def get_eth_diag(self):
        """ Returns ethernet diagnostic information """
        return self._cmd('ethdbg', 6)

    def ping(self):
        """ Returns True if we are connected to a Booster """
        try:
            if not self.get_version().startswith("RFPA"):
                return False
        except Exception:
            return False
        return True

    def close(self):
        self.dev.close()
