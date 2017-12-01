#!/usr/bin/env python

import sys
from os import system

dataType = {'ri':"cp ./api/mocks/ri_only_cost.py ./api/costs.py && cp ./api/mocks/ri_only_event.py ./api/events.py",
            'no_event':"cp ./api/mocks/no_events_cost.py ./api/costs.py && cp ./api/mocks/no_events_event.py ./api/events.py",
            'both':"cp ./api/mocks/both_cost.py ./api/costs.py && cp ./api/mocks/both_event.py ./api/events.py",
            'cloudC':"cp ./api/mocks/cloudC_only_cost.py ./api/costs.py && cp ./api/mocks/cloudC_only_event.py ./api/events.py",
            'sametime':"cp ./api/mocks/both_sametime_cost.py ./api/costs.py && cp ./api/mocks/both_sametime_event.py ./api/events.py",
            'oneweek':"cp ./api/mocks/oneweek_cost.py ./api/costs.py && cp ./api/mocks/oneweek_event.py ./api/events.py",
            'ended_onoff':"cp ./api/mocks/ended_onoff_cost.py ./api/costs.py && cp ./api/mocks/ended_onoff_event.py ./api/events.py",
            }

def usage():
    print("Usage : {} dataType\n".format(sys.argv[0]))
    sys.stdout.write("dataType can be :")
    for x in dataType:
        sys.stdout.write(' - ' + x)
    print()

def after_copy(ret):
    if ret == 0:
        ret = system("python3 ./cloudCost > /dev/null")
        if ret == 0:
            system("chromium ./ui/ui.html || firefox ./ui/ui.html || chrome ./ui/ui.html")
    else:
        print("Error: some files may be missing")



if len(sys.argv) < 2:
    usage()
    exit(1)

option = sys.argv[1]

for x in dataType:
    if x == option:
        ret = system(dataType[x])
        after_copy(ret)
        exit(0)

usage()
