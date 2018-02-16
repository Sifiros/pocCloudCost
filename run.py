#!/usr/bin/python2.7

import sys
from os import system
import argparse
from calcSavings import run

CSV_PATH = './dataMocks/csv/'
mocks = {
    'ri': (CSV_PATH + 'ri_only_savings.csv', CSV_PATH + 'ri_only_events.csv'),
    'no_event': (CSV_PATH + 'void_savings.csv', CSV_PATH + 'void_events.csv'),
    'both': (CSV_PATH + 'both_savings.csv', CSV_PATH + 'both_events.csv'),
    'cloudC': (CSV_PATH + 'cloudC_only_savings.csv', CSV_PATH + 'cloudC_only_events.csv'),
    'same_time': (CSV_PATH + 'event_same_time_savings.csv', CSV_PATH + 'event_same_time_events.csv'),
    'iops_iner': (CSV_PATH + 'iops_iner_savings.csv', CSV_PATH + 'iops_iner_events.csv'),
    'iops_outer': (CSV_PATH + 'iops_outer_savings.csv', CSV_PATH + 'iops_outer_events.csv'),
    'tiny1': (CSV_PATH + 'simple_costs.csv', CSV_PATH + 'simple_events.csv'),
    'tiny2': (CSV_PATH + '2parentsdead_costs.csv', CSV_PATH + '2parentsdead_events.csv'),
    'generated': (CSV_PATH + 'generated_costs.csv', CSV_PATH + 'generated_events.csv')
}

def run_calc(files):
    return run({
        'costs_filepath': files[0],
        'events_filepath': files[1],
        'output_file': 'ui/datas.json',
        'only_raw_fields': 'eventNames',
        'filters_preset': ['sum_by_hour', 'sum_by_cau']
    })

def run_test(files):
    cmd = "./calcSavings.py --costs-file {} --events-file {} | ./savingChecking.py".format(files[0], files[1])
    return system(cmd)

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Easy interface to ./calcSavings.py usage.\nMocks: " + str(list(mocks.keys())) + "\n")
    parser.add_argument("mock", metavar="MOCK", type=str, nargs=1, help="Indicate a mock to be tested")
    parser.add_argument("--test", "-t", action="store_true", help="Only run test for specified mock")

    args = parser.parse_args()
    mock = args.mock[0]
    if mock not in mocks:
        parser.print_help() 
        exit(1)
    files = mocks[mock]
    if args.test is True:
        run_test(files)
    elif run_calc(files) == 0:
        system("chromium ./ui/ui.html || firefox ./ui/ui.html || chrome ./ui/ui.html")
    exit(0)
