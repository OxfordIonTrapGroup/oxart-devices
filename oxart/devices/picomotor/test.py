import driver
import time

motor = driver.Picomotor("10.255.6.226")

motor.send_command('*IDN?')
print(motor.receive())

motor.send_command('MV', 1, '-')
time.sleep(0.1)
motor.send_command('ST', 1)
