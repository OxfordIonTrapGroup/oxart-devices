import telnetlib
from . import constants as c


class IPCMini:
    """Interface to IPCMini Ion Pump Controller"""
    def __init__(self, host, port=23):
        self.tn = telnetlib.Telnet(host, port)

        for win_desc, win_info in c.windows.items():
            self._generator(win_desc, win_info)

    def _read(self):
        # wait for end of response transmission, then read the crc
        bytes_ = self.tn.read_until(c.etx, timeout=0.2)
        bytes_ += self.tn.read_very_eager()
        return bytes_

    def _write(self, bytes_):
        self.tn.write(bytes_)

    def _proto_get(self, win, type_, helper=None):
        def _get():
            msg = c.encode_read(win)
            self._write(msg)
            bytes_ = self._read()
            data = c.decode_read_response(bytes_, win)

            if helper is not None:
                return helper(data)
            elif type_ == 'L':
                return bool(data)
            elif type_ == 'N':
                return int(data)
            elif type_ == 'A':
                return data

        return _get

    def _proto_set(self, win, type_, helper=None):
        def _set(value):
            if helper is not None:
                value = helper(value)

            if type_ == 'L':
                data = "{:02}".format(bool(value)).encode()
            elif type_ == 'N':
                data = "{:06}".format(value).encode()
            elif type_ == 'A':
                data = "{}".format(value).encode()

            msg = c.encode_write(win, data)
            self._write(msg)
            bytes_ = self._read()
            c.decode_write_response(bytes_)

        return _set

    def _generator(self, win_desc, win_info):
        if win_desc in c.lookups:
            read_helper = lambda data: c.lookups[win_desc][int(data)]
            write_helper = lambda value: c.reverse_lookups[win_desc][value]
        elif win_desc in c.floats:
            read_helper = lambda data: float(data)
            write_helper = lambda value: "{:10g}".format(value)
        else:
            read_helper = None
            write_helper = None

        docstring = win_info.get('docstring', None)

        get_fn = self._proto_get(win_info['win'],
                                 win_info['type'],
                                 helper=read_helper)
        if docstring is not None:
            get_fn.__doc__ = "Get " + docstring
        get_fn.__name__ = "get_{}".format(win_desc)
        setattr(self, get_fn.__name__, get_fn)

        if win_info.get('writable', True):
            set_fn = self._proto_set(win_info['win'],
                                     win_info['type'],
                                     helper=write_helper)
            if docstring is not None:
                set_fn.__doc__ = "Set " + docstring
            set_fn.__name__ = "set_{}".format(win_desc)
            setattr(self, set_fn.__name__, set_fn)

    def close(self):
        self.tn.close()

    def ping(self):
        return self.get_error_code() == c.lookups['error_code'][0]
