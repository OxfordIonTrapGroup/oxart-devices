from pipython import GCSDevice, pitools


class Hexapod:
    """Driver for the Hexpod controller C-887.52
    """

    def __init__(self, address: str):
        self.dev = GCSDevice('C-887')
        self.dev.ConnectTCPIP(address)

        # Referencing
        self.dev.FRF()
        pitools.waitonreferencing(self.dev)

        # References the stage using the reference position
        pitools.startup(self.dev, stages=None, refmodes='FRF')
        pitools.waitonreferencing(self.dev)

        # Activating zero coordinate system
        self.activate_coordinate_system()
        print('Hexapod ready: {}'.format(self.dev.qIDN().strip()))

    def move(self, axes: list[str], values: list[float]):
        """MOV: Move to absolute position

        according to activated coordinates unit mm, deg
        """
        self.dev.MOV(axes, values)
        pitools.waitontarget(self.dev, axes=self.Axes())

    def set_velocity(self, velocity=5):
        """VLS: Set velocity mm/s"""
        self.dev.VLS(velocity)

    def activate_coordinate_system(self, name='Zero'):
        """KEN: Activate coordinates with given name"""
        self.dev.KEN(name)

    def set_coordinate_system(self, name: str):
        """KSF: Set coordinate system centered at current positon of hexapod"""
        self.dev.KSF(name)

    def set_pivot_point(self,
                        axes: list[str] = ['R', 'S', 'T'],
                        values: list[float] = [0., 0., 0.]):
        """SPI: Fixing the pivot point, origin is 9mm below topplate surface"""
        self.dev.SPI(axes=axes, values=values)

    def set_lower_soft_limits(self, axes: list[str], values: list[float]):
        """NLM: Set lower soft limits"""
        self.dev.NLM(axes, values)

    def set_upper_soft_limits(self, axes: list[str], values: list[float]):
        """PLM: Set upper soft limits"""
        self.dev.PLM(axes, values)

    def enable_soft_limits(self, axes: list[str], values: list[bool]):
        """SSL: Activate/deactivate soft limits"""
        self.dev.SSL(axes, values)

    def get_axes(self):
        """Names of axes ['X', 'Y', 'Z', 'U', 'V', 'W']"""
        return self.dev.axes

    def get_positions(self):
        """qPOS: Get current positions (depends on activated coord sys)"""
        return self.dev.qPOS()

    def close(self):
        self.dev.CloseConnection()

    def ping(self):
        return True
