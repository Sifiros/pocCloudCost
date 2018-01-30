#!/usr/bin/env python

import sys
from os import system

CSV_PATH = './teevity_format/csv/'
mocks = {
    'ri': (CSV_PATH + 'ri_only_savings.csv', CSV_PATH + 'ri_only_events.csv'),
    'no_event': (CSV_PATH + 'void_savings.csv', CSV_PATH + 'void_events.csv'),
    'both': (CSV_PATH + 'both_savings.csv', CSV_PATH + 'both_events.csv'),
    'cloudC': (CSV_PATH + 'cloudC_only_savings.csv', CSV_PATH + 'cloudC_only_events.csv'),
    'same_time': (CSV_PATH + 'event_same_time_savings.csv', CSV_PATH + 'event_same_time_events.csv'),
    'iops_iner': (CSV_PATH + 'iops_iner_savings.csv', CSV_PATH + 'iops_iner_events.csv'),
    'iops_outer': (CSV_PATH + 'iops_outer_savings.csv', CSV_PATH + 'iops_outer_events.csv'),
    'tiny1': (CSV_PATH + 'simple_costs.csv', CSV_PATH + 'simple_events.csv'),
    'tiny2': (CSV_PATH + '2parentsdead.csv', CSV_PATH + '2parentsdead.csv'),   
}

def usage():
    print("Usage : {} mockName\n".format(sys.argv[0]))
    sys.stdout.write("mockName can be : " + str(list(mocks.keys())))
    print()

def exec(files):
    cmd = "./cloudCost --costs-file {} --events-file {} --sum-by-hour --sum-by-cau --only-raw-fields eventNames -o ui/datas.json".format(files[0], files[1])
    return system(cmd)

if len(sys.argv) < 2:
    usage()
    exit(1)

option = sys.argv[1]
files = mocks[option]
if exec(files) == 0:
    system("chromium ./ui/ui.html || firefox ./ui/ui.html || chrome ./ui/ui.html")
exit(0)

usage()
