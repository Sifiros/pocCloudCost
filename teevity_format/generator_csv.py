#!/usr/bin/python2
# vim: set fileencoding=utf-8 :

import csv
from datetime import timedelta
from dateutil.parser import *
from os import system
import random

fname = "teevity_savings.csv"
efname = "teevity_events.csv"

CAUs = ['PROD/ProjectA/Fontend', 'PROD/ProjectA/Backend', 'PROD/ProjectB/Fontend', 'PROD/ProjectB/Backend', \
        'DEV/ProjectA/Fontend', 'DEV/ProjectA/Backend', 'DEV/ProjectB/Fontend', 'DEV/ProjectB/Backend']

iteration_number = 1000
account = '492743284828'
startDate = '2017-08-10-12:00'
region = 'eu-west-1'
usageCost = {'m4.2xlarge' : 8.0, 'bytes-out': 0.3, 'r3.8xlarge': 80.0, 't2.micro' : 0.1}
operation =  ['Reserved', 'OnDemand']
eventType = {'Ri': 'RIStart', 'start': 'reStart', 'shut' : 'Shutdown'}

#random.randrange(start, stop, step)
def get_object_list():
    rowList = []
    usedCAUList = []
    for x in usageCost:
        newRow = {'Account':account, 'Region':region}
        newRow['UsageType'] = x
        newRow['Cost'] = usageCost[x]
        if x == 'bytes-out':
            newRow['Operation'] = 'datatransfert'
            newRow['Product'] = 'ec2'
        else:
            newRow['Operation'] = operation[1]
            newRow['Product'] = 'ec2_instance'
            newRow['CAU'] = CAUs[random.randrange(0, 8, 1)]
            usedCAUList.append(newRow['CAU'])
            if x == 'm4.2xlarge':
                rowList.append(newRow)
                rowList.append(newRow)
            rowList.append(newRow)
    CAUListSet = set(usedCAUList)
    return rowList, CAUListSet

def start_writing(filename, fieldnames, event_filename, event_fieldnames):
    with open(filename, 'a+') as wfile:
        event_file = open(event_filename, 'a+')
        event_writer = csv.DictWriter(event_file, event_fieldnames)
        writer = csv.DictWriter(wfile, fieldnames)
        rowList, usedCauSet = get_object_list()
        currentTime = parse(startDate)

        i = 0
        while i < iteration_number:
            isRIAlreadyTriggered = False
            isShutDownAlreadyTriggered = False
            isReStartAlreadyTriggered = False

            for currentRow in rowList:
                currentRow['Date'] = currentTime.isoformat()

                # Trigger and write RI event
                if i == (iteration_number) / 2:
                    currentRow['Operation'] = operation[0]
                    currentRow['Cost'] = currentRow['Cost'] * 0.5
                    if isRIAlreadyTriggered == False:
                        isRIAlreadyTriggered = True
                        for CAUType in usedCauSet:
                            eventRow = {'Date' : currentTime.isoformat(), 'CAU': CAUType, 'Type': eventType['Ri']}
                            event_writer.writerow(eventRow)

                # Trigger and write ShutDown event
                if currentRow['UsageType'] == 'm4.2xlarge' and currentTime.hour == 19:
                    currentRow['Cost'] = currentRow['Cost'] * 0.70
                    if isShutDownAlreadyTriggered == False:
                        isShutDownAlreadyTriggered = True
                        eventRow = {'Date' : currentTime.isoformat(), 'CAU': currentRow['CAU'], 'Type': eventType['shut']}
                        event_writer.writerow(eventRow)

                # Trigger and write ReStart event
                if currentRow['UsageType'] == 'm4.2xlarge' and currentTime.hour == 8:
                    currentRow['Cost'] = usageCost['m4.2xlarge']
                    if isReStartAlreadyTriggered == False:
                        isReStartAlreadyTriggered = True
                        eventRow = {'Date' : currentTime.isoformat(), 'CAU': currentRow['CAU'], 'Type': eventType['start']}
                        event_writer.writerow(eventRow)

                # Some Cost randomization                       
                currentRow['Cost'] = currentRow['Cost'] * random.uniform(0.9, 1.1)
                writer.writerow(currentRow)

            currentTime += timedelta(hours=1)
            i += 1

file = open(fname, "rb")
ev_file = open(efname, "rb")
random.seed(None)

ret = system("cp ./save.csv ./teevity_savings.csv")
ret2 = system("cp ./save_events.csv ./teevity_events.csv")
if ret == 0 and ret2 == 0:
    try:
        reader = csv.DictReader(file)
        event_reader = csv.DictReader(ev_file)
        fieldnames = reader.fieldnames
        event_fieldnames = event_reader.fieldnames
    finally:
        file.close()
        ev_file.close()
        start_writing(fname, fieldnames, efname, event_fieldnames)