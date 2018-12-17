import socket

class Picomotor:
    """ Picomotor Driver """
    def __init__(self, device_ip):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((device_ip, 23))
        self.ip_addr = device_ip
        #assert self.ping(),"Device ping failed"
        # dict containing commands as keys and a list with entries
        # [takes_channel, takes_argument, arg_min, arg_max]
        self.commands = {
            '*IDN?': [False, False],
            '*RCL': [False, True, 0, 1],
            '*RST': [False, False],
            'AB': [False, False],
            'AC': [True, True, 1, 200000],
            'AC?': [True, False],
            'DH': [True, True, -2147483648, 2147483647],
            'DH?': [True, False],
            'MC': [False, False],
            'MD?': [True, False],
            'MV': [True, True, '-', '+'],
            'MV?': [True, False], #check!
            'PA': [True, True,  -2147483648, 2147483647],
            'PA?': [True, False],
            'PR': [True, True,  -2147483648, 2147483647],
            'PR?': [True, False],
            'QM': [True, True, 0, 3],
            'QM?': [True, False],
            'RS': [False, False],
            'SA': [False, True, 1, 31],
            'SA?': [False, False],
            'SC': [False, True, 0, 2],
            'SC?': [False, False],
            'SD?': [False, False],
            'SM': [False, False],
            'ST': [True, False],
            'TB?': [False, False],
            'TE?': [False, False],
            'TP?': [True, False],
            'VA': [True, True, 1, 2000],
            'VA?': [True, False],
            'VE?': [False, False],
            'XX': [False, False],
            'ZZ': [False, True, None], #range?
            'ZZ?': [False, False],
            'GATEWAY': [False, False],
            'GATEWAY?': [False, False],
            'HOSTNAME': [False, True, None], #range?
            'HOSTNAME?': [False, False],
            'IPADDR': [False, True, None], #range?
            'IPADDR?': [False, False],
            'IPMODE': [False, True, 0, 1],
            'IPMODE?': [False, False],
            'MACADDR?': [False, False],
            'NETMASK': [False, True, None], #range?
            'NETMASK?': [False, False]
            }

    def _is_valid_axis(self, ch):
        return ch in [1,2,3,4]

    def _is_valid_argument(self, com, arg):
        if self.commands[com][2] is None:
            return True
        else:
            argmin = self.commands[com][2]
            argmax = self.commands[com][3]
            return argmin <= arg <= argmax or arg is argmin or arg is argmax

    def send_command(self, command, axis = None, argument = None):
        c = command

        assert (command in self.commands), "Invalid Command"
        if self.commands[command][0]:
            assert self._is_valid_axis(axis),"Invalid Axis"
            c = str(axis) + c
        if self.commands[command][1]:
            assert self._is_valid_argument(command, argument),"Invalid Argument"
            c = c + str(argument)

        self.sock.send(str.encode(c+"\n"))
        print(c)

    def receive(self):
        with self.sock.makefile() as stream:
            return stream.readline().strip()
