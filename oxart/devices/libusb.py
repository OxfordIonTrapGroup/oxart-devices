"""Helpers for dealing with libusb runtime shared library dependencies.

Some device driver, e.g. for Andor cameras, dynamically load the libusb library for
communicating with USB devices from user space. This module contains helper functions
for setting up the correct dependencies.
"""

import subprocess
import shutil


def get_libusb_library_path():
    """Execute `libusb-config --libs` and return the library search path specified by
    the -L flag.

    The returned path can e.g. be appended to LD_LIBRARY_PATH.
    """
    if shutil.which("libusb-config") is None:
        raise FileNotFoundError(
            "libusb-config not found in $PATH. Is libusb-dev installed (or, for Nix, " +
            "nixpkgs.libusb-compat-0_1)?")

    try:
        result = subprocess.run(
            ["libusb-config", "--libs"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"libusb-config failed with exit code {e.returncode}: {e.stderr.strip()}"
        ) from e

    output = result.stdout.strip()
    if not output:
        raise RuntimeError("libusb-config returned empty output")

    paths = [arg[2:] for arg in output.split() if arg.startswith("-L") and len(arg) > 2]
    if len(paths) != 1:
        raise RuntimeError("Expected to find exactly one library path (-L…) in " +
                           f"'libusb-config --libs' output, got: '{output}'")
    return paths[0]
