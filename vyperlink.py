"""Vyperlink v1.1
Interface to Suunto dive computers.
Copyright 2005, Olaf Trygve Berglihn <olafb@pvv.org>
Licenced under GPLv2 license

requires pySerial found at http://pyserial.sourceforge.net/
"""

import serial, time, sys, string, types



DEBUG=0
DEFAULT_PORT = 1
BAUDRATE = 2400
PARITY = serial.PARITY_ODD
RTSCTS = 1
TIMEOUT = 0.1
EXTRAANSWERTIME = 0.8
SPYDER = "spyder"
SPYDER_OLD = "old spyder"
SPYDER_NEW = "new spyder"
COBRA = "cobra"
VYPER = "vyper"
VYTEC = "vytec"
STINGER = "stinger"
MOSQUITO = "mosquito"
EOF = ""



def make_checksum(buffer):
	checksum = 0
	for byte in buffer:
		checksum = byte ^ checksum
	return checksum



class VyperlinkException(Exception):  pass
class SerialException(VyperlinkException):  pass
class ReadException(VyperlinkException):  pass
class WriteException(VyperlinkException):  pass
class ReplyException(VyperlinkException):  pass
class ChecksumException(VyperlinkException):  pass



class Vyperlink:
	MODEL_IDS = {SPYDER:[20,30,40],
		COBRA:[0x0c],
		VYPER:[0x0a],
		VYTEC:[0x0b],
		STINGER:[0x03],
		MOSQUITO:[0x04]}
	sampling = None
	serial = None
	maxdepth = None
	tottime = None
	numdives = None
	personal = None
	model = None
	atringbufend = False
	


	def __init__(self):
		try:
			self._serial = serial.Serial(DEFAULT_PORT, BAUDRATE, 
				parity=PARITY, rtscts=RTSCTS ,timeout=TIMEOUT)
		except serial.SerialException, msg:
			del(self)
			raise SerialException, msg
		self.echos = False
		self._serial.flushInput()
		self._serial.flushOutput()



	def send_testcmd(self, command):
		try:
			self._serial.write(command)
			self._serial.flushOutput()
		except serial.SerialException, msg:
			raise SerialException, msg



	def detect_interface(self):
		detectmode_worked=1
		self._serial.setRTS(1)
		time.sleep(0.3)
		self._serial.setRTS(0)
		self.send_testcmd("AT\r")
		data = self.read_serial(1,EXTRAANSWERTIME)
		data += self.read_serial(2)
		if data != "AT\r":
			sys.stderr.write("Interface not responding in probe"
			+" mode.\n")
			detectmode_worked=0
		self._serial.setRTS(0)	
		data = self.read_serial(1,EXTRAANSWERTIME)
		if data != '':
			sys.stderr.write("Got extraneous character %02x" %data \
				+ " in detection phase - maybe line is" \
				+ " connected to a modem?\n")
		self._serial.setRTS(1)
		self.write_serial("AT\r")
		self._serial.setRTS(0)
		data = self.read_serial(1,EXTRAANSWERTIME)
		data += self.read_serial(2)
		if data == '':
			if detectmode_worked:
				sys.stderr.write("Detected original Suunto"
					+ " interface with RTS-switching.\n")
			else:
				sys.stderr.write("Can't detect interface.\n"
				+ "Hoping it's an original Suunto interface "
				+ "with DC already attached.\n")
			self.echos=False
			return
		if data != 'AT\r':
			sys.stderr.write("Interface not responding when RTS is"
					+ " on.\n")
		data = self.read_serial()
		if data != '':
			sys.stderr.write("Got extraneous character %02x" \
					% data[0] + " in detection phase" \
					+ "- maybe line is connected to a" \
					" modem?\n")
		sys.stderr.write("Detected clone interface without" \
				+ " RTS-switching.\n")
		self.echos=True



	def write_serial(self, buffer):
		try:
			self._serial.setRTS(1)
			if type(buffer) == types.ListType:	
				for byte in buffer:
					self._serial.write(byte)
			else:
				self._serial.write(buffer)
		except serial.SerialException, msg:
			raise WriteException, msg
		self._serial.flush()
		self._serial.setRTS(0)
	


	def read_serial(self, bytes_count=1, timeout=TIMEOUT):
		try:
			self._serial.setRTS(0)
			self._serial.setTimeout(timeout)
			retval = self._serial.read(bytes_count)
			if DEBUG:
				print "read %s" % repr(retval)
			return retval
		except serial.SerialException, msg:
			raise ReadException, msg



	def send_command(self,command):
		crc = make_checksum(command)
		command.append(crc)
		self.write_serial(map(chr, command))
		if self.echos:
			data = self.read_serial(1, EXTRAANSWERTIME)
			data += self.read_serial(len(command)-1)
			if data == '':
				raise ReplyException,"Timout waiting for echos."
			data = map(chr, list(data))
			if data != command:
				raise ReplyException, "Echo incorrect."



	def read_memory(self, start, length):
		command = [0x05, start>>8 & 0xff, start & 0xff, length]
		self.send_command(command)
			
		echo = self.read_serial(1, EXTRAANSWERTIME)
		echo += self.read_serial(3)
		if not echo:
			raise ReplyException, "No reply to read memory command."
		echo = map(ord,list(echo))
		if echo != command[0:4]:
			errmsg = "Reply to read memory malformed."
			if echo == '':
				errmsg += " Interface present but no DC."
			raise ReplyException, errmsg
		
		crc = echo[0]^echo[1]^echo[2]^echo[3]
		reply = self.read_serial(length)
		for i in range(length):
			crc = crc^ord(reply[i])
		reply_crc=self.read_serial()
		if crc != ord(reply_crc):
			raise ReplyException, "Reply failed CRC check."
		return reply



	def identify_computer(self):
		retmodel = ord(self.read_memory(0x24,1))
		for model in self.MODEL_IDS.keys():
			if retmodel in self.MODEL_IDS[model]:
				self.model = model
		if self.model == SPYDER:
			sys.stderr.write("Probably Spyder. Checking further.\n")
			retval = map(ord, self.read_memory(0x16,2))
			if retval[0]==0x01 and retval[1]==0x01:
				self.model = SPYDER_OLD
			elif retval[0]==0x01 and retval[1]==0x02:
				self.model = SPYDER_NEW
			else:
				sys.stderr.write("Unable to identify Spyder.\n")
				self.model = None



	def read_info(self):
		if not self.model:
			self.identify_computer()
		personal = self.read_memory(0x2c, 30)
		data = map(ord, self.read_memory(0x18, 18))
		if self.model == SPYDER_OLD:
			serial = "%2i%2i%5i" % \
				(data[0], data[1], (data[2]<<8)+data[3])
			sampling = 20
		elif self.model == SPYDER_NEW:
			serial = "%2i5d" % ( (data[0]<<8)+data[1],
				(data[2]<<8)+data[3]) 
			sampling = data[12]
		else:
			serial = "%2i%2i%2i" % ( (data[14]<<8)+data[15],
				data[16], data[17] )
			sampling = data[12]
			
		maxdepth = ((data[6]<<8) + data[7])/128.0*0.3048
		tottime = (data[8]<<8) + data[9]
		numdives = (data[10]<<8) + data[11]
		return {"personal":personal,
			"serial": serial,
			"sampling":sampling,
			"maxdepth":maxdepth,
			"numdives":numdives,
			"model":self.model}



	def make_profile_spyder(self, data):
		prof = {
		"temp_maxdepth" : data[1],
		"temp_enddive" : data[1],
		"temp_start" : data[1],
		"divenum" : data[-2],
		"sampling" : data[-4],
		"year" : data[-7],
		"month" : data[-8],
		"day" : data[-9],
		"hr" : data[-10],
		"min" : data[-11],
		"slowwarn" : [],
		"profile" : [0.0]
		}
		if prof["year"] == 99:
			prof["year"] += 1900
		else:
			prof["year"] += 2000

		for i in range(len(samples)):
			byte = samples[i]
			if byte in [0x7d, 0x7e, 0x7f, 0x80, 0x82]:
				pass
			elif byte == 0x81:
				prof["slowwarn"].append(i)
			else:
				if byte > 127.5:
					byte -= 256
				prof["profile"].append(prof["profile"][-1]
						- byte*0.3048)
		return prof



	def make_profile_vyper(self, data):
		prof = {
			"temp_maxdepth" : data[-4],
			"temp_enddive" : data[-3],
			"divenum" : data[2],
			"sampling" : data[3],
			"temp_start" : data[8],
			"year" : data[9],
			"month" : data[10],
			"day" : data[11],
			"hr" : data[12],
			"min" : data[13],
			"profile" : [0.0],
			"slowwarn" : [],
			"bookmark" : []
		}
		if prof["year"] == 99:
			prof["year"] += 1900
		else:
			prof["year"] += 2000

		samples = data[14:-4]
		for i in range(len(samples)):
			byte = samples[i]
			if byte in [0x79, 0x7b, 0x7d, 0x7e, 0x7f, 0x80, 0x81,
					0x82, 0x83, 0x84, 0x85, 0x86, 0x87]:
				pass
			elif byte == 0x7a:
				prof["slowwarn"].append(i)
			elif byte == 0x7c:
				prof["bookmark"].append(i)
			else:
				if byte > 127.5:
					byte -= 256
				prof["profile"].append(prof["profile"][-1]
						- byte*0.3048)
		return prof



	def get_profile(self, start=True, last=None):
		command = [0x08, 0xa5]
		if not start:
			command[0]= 0x09
			# If we got nothing at last call to get_profile, we're
			# at the end of the ringbuffer.
			if self.atringbufend:
				return None
		else:
			self.atringbufend = False
			
		self.send_command(command)

		# read packets up to 32 bytes for profile data
		# don't know how many, so read until EOF
		data = []
		while 1:
			retc = self.read_serial(1,EXTRAANSWERTIME)
			# if at end of profile data, we get no more input.
			if len(retc) == 0:
				break
		
			if ord(retc) != command[0]:
				raise ReadError, "Unexpected profile answer."
			crc = ord(retc)
			buflen = ord(self.read_serial())
			
			# if buflen is 0, we're at the end of the ringbuffer.
			# note this and ignore rest of the input.
			if buflen < 1:
				self.atringbufend = True
				self._serial.flushInput()
				break

			crc = crc^buflen
			if buflen<0 or buflen>32:
				raise ReadError, "Unexpected bufflen: %s." \
						% buflen
			buf = map(ord, self.read_serial(buflen))
			for byte in buf:
				crc = crc^byte
			retc = ord(self.read_serial())
			if crc != retc:
				raise ChecksumException, "Checksum mismatch."
			data.extend(buf)
		
		data.reverse()

		# check if there is any data in the profile.
		if len(data) == 0:
			return None

		# the data we have read up to end of the ringbuffer is bogus.
		# just ignore the profile if at ringbuffer end.
		if self.atringbufend:
			return None

		if self.model in [SPYDER, SPYDER_OLD, SPYDER_NEW]:
			prof = self.make_profile_spyder(data)
		else:
			prof = self.make_profile_vyper(data)

		# check if we have read past the stop date.
		# if no stop date was given, just return profile, else
		# compare profile date to requested stop date.
		if not last:
			return prof
		else:
			lastdate = time.strptime(last, "%Y-%m-%dT%H:%M")
			profdatestr = "%4d-%02d-%02dT%02d:%02d" % \
				(prof["year"], prof["month"], prof["day"],
						prof["hr"], prof["min"])
			profdate = time.strptime(profdatestr,"%Y-%m-%dT%H:%M") 
			if time.mktime(lastdate) < time.mktime(profdate):
				return prof
			else:
				return None


