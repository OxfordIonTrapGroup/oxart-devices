import driver
import time

motor = driver.PicomotorController("10.255.6.226")

motor.send_command('*IDN?')
print(motor.receive())

motor.send_command('MV', 2, '-')
time.sleep(0.01)
motor.send_command('ST', 2)

time.sleep(0.01)
motor.send_command('MV', 5, '-')
motor.print_error_messages()
