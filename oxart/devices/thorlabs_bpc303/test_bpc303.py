from driver import Message, BPC303, MGMSG, SRC_DEST
import struct

d = BPC303("/dev/bpc303_71134204")
print("ping: ", d.ping())

# d.set_pi_constants(1, 100, 100)

for i in range(3):
	print("channel {} enabled? ".format(i), d.get_enable(i+1))
	print("channel {} voltage limit: ".format(i), d.get_voltage_limit(i+1))
	print("channel {} feedback on? ".format(i), d.get_enable_feedback(i+1))
	print("channel {} position: ".format(i), d.get_position(i+1))
	prop_gain, int_gain = d.get_pi_constants(i+1)
	print("channel {} PI constants: {} and {}".format(i, prop_gain, int_gain))

print("serial number: ", d.get_serial())
