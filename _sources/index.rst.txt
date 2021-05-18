oxart-devices
=============

The ``oxart.devices`` library contains
`SiPyCo <https://github.com/m-labs/sipyco>`_-compatible drivers
for interfacing with various laboratory devices from the
`ARTIQ <https://m-labs.hk/experiment-control/artiq/>`_-based
experiments in the `Oxford Ion Trap Quantum Computing Group
<https://www.physics.ox.ac.uk/research/ion-trap-quantum-computing-group>`_.

The "drivers" (Python device access classes) in this repository were
extracted from a long-standing internal source tree, and vary greatly
in terms of completeness and level of documentation. Nevertheless, we
hope that the code will be useful for physicists and engineers outside
of our group as well, and we are always happy to collaborate (e.g. via
GitHub pull requests).

API documentation for some of the code can be found below, but for now,
the best way to get an overview of the available devices is to browse
the list of SiPyCo controller executables in
https://github.com/OxfordIonTrapGroup/oxart-devices/tree/master/oxart/frontend.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   bme
