#!/usr/bin/env python

import sys
from os import system

dataType = {'ri': "cp ./teevity_format/for_poc/ri_only_events.csv ./teevity_format/teevity_events.csv && cp ./teevity_format/for_poc/ri_only_savings.csv ./teevity_format/teevity_savings.csv",
            'no_event':"cp ./teevity_format/for_poc/void_events.csv ./teevity_format/teevity_events.csv && cp ./teevity_format/for_poc/void_savings.csv ./teevity_format/teevity_savings.csv",
            'both':"cp ./teevity_format/for_poc/both_events.csv ./teevity_format/teevity_events.csv && cp ./teevity_format/for_poc/both_savings.csv ./teevity_format/teevity_savings.csv",
            'cloudC':"cp ./teevity_format/for_poc/cloudC_only_events.csv ./teevity_format/teevity_events.csv && cp ./teevity_format/for_poc/cloudC_only_savings.csv ./teevity_format/teevity_savings.csv",
            'same_time':"cp ./teevity_format/for_poc/event_same_time_events.csv ./teevity_format/teevity_events.csv && cp ./teevity_format/for_poc/event_same_time_savings.csv ./teevity_format/teevity_savings.csv",
            'iops_iner':"cp ./teevity_format/for_poc/iops_iner_events.csv ./teevity_format/teevity_events.csv && cp ./teevity_format/for_poc/iops_iner_savings.csv ./teevity_format/teevity_savings.csv",
            'iops_outer':"cp ./teevity_format/for_poc/iops_outer_events.csv ./teevity_format/teevity_events.csv && cp ./teevity_format/for_poc/iops_outer_savings.csv ./teevity_format/teevity_savings.csv",
#            'oneweek':"cp ./api/mocks/oneweek_cost.py ./api/costs.py && cp ./api/mocks/oneweek_event.py ./api/events.py",
#            'sametime':"cp ./teevity_format/for_poc/ri_only_events ./teevity_format/teevity_events && cp ./teevity_format/for_poc/ri_only_savings ./teevity_format/teevity_savings"
#            'ended_onoff':"cp ./api/mocks/ended_onoff_cost.py ./api/costs.py && cp ./api/mocks/ended_onoff_event.py ./api/events.py",
#            '3events':"cp ./api/mocks/3events_cost.py ./api/costs.py && cp ./api/mocks/3events_event.py ./api/events.py",
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
