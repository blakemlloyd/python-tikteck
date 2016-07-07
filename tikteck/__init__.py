# Python module for control of Tikteck bluetooth LED bulbs
#
# Copyright 2016 Matthew Garrett <mjg59@srcf.ucam.org>
#
# This code is released under the terms of the MIT license. See the LICENSE file
# for more details.

import BDAddr
from BluetoothSocket import BluetoothSocket, hci_devba
import socket
import sys
import time

from Crypto.Cipher import AES

def hex_to_str(hex):
    return str(bytearray(hex))

def encrypt(key, data):
  key = hex_to_str(reversed(key))
  k = AES.new(key, AES.MODE_ECB)
  data = reversed(list(k.encrypt(hex_to_str(reversed(data)))))
  rev = []
  for d in data:
    rev.append(ord(d))
  return rev
 
def generate_sk(name, password, data1, data2):
  name = name.ljust(16, chr(0))
  password = password.ljust(16, chr(0))
  key = [ord(a) ^ ord(b) for a,b in zip(name,password)]
  data = data1[0:8]
  data += data2[0:8] 
  return encrypt(key, data)

def key_encrypt(name, password, data):
  name = name.ljust(16, chr(0))
  password = password.ljust(16, chr(0))
  key = [ord(a) ^ ord(b) for a,b in zip(name,password)]
  return encrypt(data, key) 

def encrypt_packet(sk, mac, packet):
    temp_buffer = [mac[0], mac[1], mac[2], mac[3], 0x01, packet[0], packet[1], packet[2], 15, 0, 0, 0, 0, 0, 0, 0]
    temp_buffer = encrypt(sk, temp_buffer)

    for i in range(15):
      temp_buffer[i] = temp_buffer[i] ^ packet[i+5]
    temp_buffer = encrypt(sk, temp_buffer)

    for i in range(2):
       packet[i+3] = temp_buffer[i]

    temp_buffer = [0, mac[0], mac[1], mac[2], mac[3], 0x01, packet[0], packet[1], packet[2], 0, 0, 0, 0, 0, 0, 0] 
    temp_buffer2 = []
    for i in range(15):
        if i == 0:
          temp_buffer2 = encrypt(sk, temp_buffer)
          temp_buffer[0] = temp_buffer[0] + 1
        packet[i+5] ^= temp_buffer2[i]

    return packet

def send_packet(sock, handle, data):
  packet = bytearray([0x12, handle, 0x00])
  for item in data:
    packet.append(item)
  sock.send(packet)
  data = sock.recv(32)
  response = []
  for d in data:
    response.append(ord(d))
  return response

def read_packet(sock, handle):
  packet = bytearray([0x0a, handle, 0x00])
  sock.send(packet)
  data = sock.recv(32)
  response = []
  for d in data:
    response.append(ord(d))
  return response

class tikteck:
  def __init__(self, mac, name, password):
    self.mac = mac
    self.macarray = mac.split(':')
    self.name = name
    self.password = password
    self.packet_count = 2012
    self.red = 0xff
    self.blue = 0xff
    self.green = 0xff
    self.bright = 0xff

  def set_sk(self, sk):
    self.sk = sk

  def connect(self):
    my_addr = hci_devba(0) # get from HCI0
    dest = BDAddr.BDAddr(self.mac)
    addr_type = BDAddr.TYPE_LE_PUBLIC
    self.sock = BluetoothSocket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    self.sock.bind_l2(0, my_addr, cid=4, addr_type=BDAddr.TYPE_LE_RANDOM)
    self.sock.connect_l2(0, dest, cid=4, addr_type=addr_type)

    data = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0, 0, 0, 0, 0, 0, 0, 0]
    enc_data = key_encrypt(self.name, self.password, data)
    packet = [0x0c]
    packet += data[0:8]
    packet += enc_data[0:8]
    send_packet(self.sock, 0x1b, packet)
    time.sleep(0.3)
    data2 = read_packet(self.sock, 0x1b)
    self.sk = generate_sk(self.name, self.password, data[0:8], data2[2:10])

  def send_packet(self, msgid, command, data):
    packet = [0] * 20
    packet[0] = self.packet_count & 0xff
    packet[1] = self.packet_count >> 8 & 0xff
    packet[5] = msgid & 0xff
    packet[6] = msgid & 0xff | 0x80
    packet[7] = command
    packet[8] = 0x69
    packet[9] = 0x69
    packet[10] = data[0]
    packet[11] = data[1]
    packet[12] = data[2]
    packet[13] = data[3]
    mac = [int(self.macarray[5], 16), int(self.macarray[4], 16), int(self.macarray[3], 16), int(self.macarray[2], 16), int(self.macarray[1], 16), int(self.macarray[0], 16)]
    enc_packet = encrypt_packet(self.sk, mac, packet)
    self.packet_count += 1
    if self.packet_count > 65535:
      self.packet_count = 1
    print enc_packet
    response = send_packet(self.sock, 0x15, enc_packet)
    print response

  def set_state(self, red, green, blue, brightness):
    self.red = red
    self.green = green
    self.blue = blue
    self.bright = brightness
    self.send_packet(0xffff, 0xc1, [red, green, blue, brightness])

  def set_default_state(self, red, green, blue, brightness):
    self.send_packet(0xffff, 0xc4, [red, green, blue, brightness])

  def set_rainbow(self, brightness, speed, mode, loop):
    self.send_packet(0xffff, 0xca, [brightness, mode, speed, loop]) 

  def set_mosquito(self, brightness):
    self.send_packet(0xffff, 0xcb, [brightness, 0, 0, 0]) 
