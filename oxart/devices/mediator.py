import inspect
from functools import wraps


def _wrap_function(func_name, func, channel_arg_idx=None):
    takes_channel_arg = channel_arg_idx is not None
    idx = channel_arg_idx - 1 if takes_channel_arg else 0

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        got_channel_kwarg = "channel_name" in kwargs
        channel_name = kwargs.pop("channel_name", args[idx])

        dev_name, channel_num = self.mappings[channel_name]
        dev = self.devices[dev_name]

        if takes_channel_arg:
            if got_channel_kwarg:
                kwargs[self._channel_arg] = channel_num
            else:
                args = args[:idx] + (channel_num, ) + args[idx + 1:]
        elif not got_channel_kwarg:
            args = args[1:]

        return getattr(dev, func_name)(*args, **kwargs)

    return wrapper


def multi_channel_dev_mediator(mediator_cls):
    """ Monkeypatch mediator classes for multi-channel devices to wrap all
    methods from the device driver.

    The decorated mediator allow one to call any method of the base driver,
    replacing channel arguments with a channel_name, which is a key in the
    mappings dict. Driver functions that don't take a channel argument must
    still have a channel_name argument (keyword or first positional argument).

    Docstrings are taken from the driver class.

    - mediator_cls should have a _driver_cls member, giving the driver to use.
    - mediator_cls can have a _channel_arg member (defaults to "channel").
    - _channel_arg ("channel") positional arguments in the driver methods are
      replaced with "channel_name" arguments in the wrapped functions.

    Example::

    @multi_channel_dev_mediator
    class ExampleMediator:
        _driver_cls = MyDriver
        def __init__(self, dmgr, devices, mappings):
            self.core = dmgr.get("core")
            self.devices = {dev: dmgr.get(dev) for dev in devices}
            self.mappings = mappings
    """
    if not hasattr(mediator_cls, "_channel_arg"):
        setattr(mediator_cls, "_channel_arg", "channel")

    funcs = [
        (func_name, func)
        for (func_name,
             func) in inspect.getmembers(mediator_cls._driver_cls, inspect.isfunction)
        if func_name[0] != '_'
    ]

    for func_name, func in funcs:
        if func_name == "close":
            continue

        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        param_names = [param.name for param in params]
        if mediator_cls._channel_arg in param_names:
            idx = param_names.index(mediator_cls._channel_arg)
            params[idx] = params[idx].replace(name="channel_name")
            wrapper = _wrap_function(func_name, func, idx)
        else:
            params.insert(
                1,
                inspect.Parameter(name="channel_name",
                                  kind=inspect.Parameter.POSITIONAL_OR_KEYWORD))
            wrapper = _wrap_function(func_name, func)
        wrapper.__signature__ = sig.replace(parameters=params)
        setattr(mediator_cls, func_name, wrapper)

    def close(self):
        pass

    setattr(mediator_cls, "close", close)

    return mediator_cls
