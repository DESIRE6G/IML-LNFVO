import sys
import os
import ipaddress
import csv
from scapy.all import *
from scapy.utils import rdpcap, wrpcap

ETHER_TYPE_D6G  = 0xD6D6
ETHER_TYPE_IPV4 = 0x0800

ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY   = 0

class D6G(Packet):
  name = "D6G Header"
  fields_desc = [
    ShortField("serviceId", 10),
    ShortField("locationId", 10),
    ByteField("hhflag", 0),
    ShortField("nextNF", 10),
    ShortField("nextHeader", 0),
  ]

def create_d6g_pkt():
  pkt = Ether(
      src = "00:11:22:33:44:55",
      dst = "00:11:22:33:44:66",
      type = ETHER_TYPE_IPV4
      #type = ETHER_TYPE_D6G
      )
  #pkt /= D6G(
  #    serviceId = 30,
  #    locationId = 40,
  #    nextNF = 42,
  #    nextHeader = ETHER_TYPE_IPV4
  #    )
  pkt /= IP(
      src = "10.30.7.213",
      dst = "10.10.10.44"
      )
  pkt /= ICMP(
      type = ICMP_ECHO_REQUEST
      )
  pkt /= "XXX"

  return pkt

def main():
  pkt = create_d6g_pkt()
  wrpcap("test1.pcap", pkt)

if __name__ == '__main__':
  main()
