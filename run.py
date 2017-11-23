#!/usr/bin/env python

import sys
from os import system

def usage():
    print("Usage : {} dataType\n".format(sys.argv[0]))
    print("dataType can be: both, cloudC, no_event, ri")


if len(sys.argv) < 2:
    usage()
    exit(1)

option = sys.argv[1]

if option == "both":
    ret = system("cp ./api/mocks/both_cost.py ./api/costs.py && cp ./api/mocks/both_event.py ./api/events.py")
    if ret == 0:
        ret = system("python3 cloudCost > /dev/null && mv ./eventSavings.json ./ui/")
        if ret == 0:
            system("chromium ./ui/ui.html || firefox ./ui/ui.html || chrome ./ui/ui.html")
    else:
        print("Error: some files may be missing")


elif option == "no_event":
    ret = system("cp ./api/mocks/no_events_cost.py ./api/costs.py && cp ./api/mocks/no_events_event.py ./api/events.py")
    if ret == 0:
        ret = system("python3 ./cloudCost > /dev/null && mv ./eventSavings.json ./ui/")
        if ret == 0:
            system("chromium ./ui/ui.html || firefox ./ui/ui.html || chrome ./ui/ui.html")
    else:
        print("Error: some files may be missing")


elif option == "ri":
    ret = system("cp ./api/mocks/ri_only_cost.py ./api/costs.py && cp ./api/mocks/ri_only_event.py ./api/events.py")
    if ret == 0:
        ret = system("python3 ./cloudCost > /dev/null && mv ./eventSavings.json ./ui/")
        if ret == 0:
            system("chromium ./ui/ui.html || firefox ./ui/ui.html || chrome ./ui/ui.html")
    else:
        print("Error: some files may be missing")


elif option == "cloudC":
    ret = system("cp ./api/mocks/cloudC_only_cost.py ./api/costs.py && cp ./api/mocks/cloudC_only_event.py ./api/events.py")
    if ret == 0:
        ret = system("python3 ./cloudCost > /dev/null && mv ./eventSavings.json ./ui/")
        if ret == 0:
            system("chromium ./ui/ui.html || firefox ./ui/ui.html || chrome ./ui/ui.html")
    else:
        print("Error: some files may be missing")
else:
    usage()
