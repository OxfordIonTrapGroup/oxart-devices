import picomirror
import time

mirror = picomirror.PicoMirror("10.255.6.226", 1, 2)

mirror.set_velocities(1000, 1000)
mirror.move_absolute(0, 0)
