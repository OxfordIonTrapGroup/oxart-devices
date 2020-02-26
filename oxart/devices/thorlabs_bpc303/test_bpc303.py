from driver import Message, BPC303, MGMSG, SRC_DEST
import struct

d = BPC303("/dev/bpc303_71134204")
print("ping: ", d.ping())

for i in range(3):
	print("channel {} enabled? ".format(i), d.get_enable(i+1))
	print("channel {} voltage limit: ".format(i), d.get_voltage_limit(i+1))
	print("channel {} feedback on? ".format(i), d.get_enable_feedback(i+1))
	print("channel {} position: ".format(i), d.get_position(i+1))

print("serial number: ", d.get_serial())
