#!/usr/bin/python2
# vim: set fileencoding=utf-8 :

import csv
import copy
from datetime import timedelta
from dateutil.parser import *
from os import system
import random

# gérer par nombre d'instance et séparer ec2 et ebs

fname = "teevity_savings.csv"
efname = "teevity_events.csv"

CAUs = ['PROD/ProjectA/Frontend', 'PROD/ProjectA/Backend', 'PROD/ProjectB/Frontend', 'PROD/ProjectB/Backend', \
        'DEV/ProjectA/Frontend', 'DEV/ProjectA/Backend', 'DEV/ProjectB/Frontend', 'DEV/ProjectB/Backend']

# start - end
hour_offOn = [19, 8]
hour_Iops = [1, 12]

# number of hours that will be generated
iteration_number = 48

# Number of resources divided by what on Shutdown event
instance_divider = 3
ri_percent_multiplier = 0.50
iops_percet_multiplier = 0.80    # EX : 0.80 represent 20% of reduction

#hardcode
account = '492743284828'
startDate = '2017-08-10-13:00'
region = 'eu-west-1'

# is Reserved or not
operation =  ['Reserved', 'OnDemand']

# Unit / hour pricing
usageCost = {'m4.2xlarge' : 8.0, 'bytes-out': 0.3, 'r3.8xlarge': 80.0, 't2.micro' : 0.6}

# Number of resources at start
resourceRef = {'m4.2xlarge' : 7, 'bytes-out': 3, 'r3.8xlarge': 3, 't2.micro' : 16}
resourceUsed = {'m4.2xlarge' : 7, 'bytes-out': 3, 'r3.8xlarge': 3, 't2.micro' : 16}

eventType = {'Ri': 'RIStart', \
             'start': 'reStart', 'shut' : 'Shutdown', \
             'iopUP' : 'increase_iops', 'iopDown' : 'decrease_iops'}

#random.randrange(start, stop, step)
def get_object_list():
    rowList = []
    usedCAUList = []
    for x in usageCost:
        newRow = {'Account':account, 'Region':region}
        newRow['UsageType'] = x
        newRow['Cost'] = usageCost[x] * resourceRef[x]
        if x == 'bytes-out':
            newRow['Operation'] = 'datatransfert'
            newRow['Product'] = 'ec2'
        else:
            newRow['Operation'] = operation[1]
            newRow['Product'] = 'ec2_instance'
        newRow['CAU'] = CAUs[random.randrange(0, 8, 1)]
        usedCAUList.append(newRow['CAU'])
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
            isThisEventAlreadySet = {e:False for e in usedCauSet}
            isIOPSAlreadySet = {el:False for el in usedCauSet}
            isRIAlreadyTriggered = False

            for currentRow in rowList:
                currentRow['Date'] = currentTime.isoformat()
                
                # RI spawn at the exact middle of the testFile
                # Trigger and write RI event
                if i == (iteration_number) / 2:
                    currentRow['Operation'] = operation[0]
                    currentRow['Cost'] = currentRow['Cost'] * ri_percent_multiplier
                    if isRIAlreadyTriggered == False:
                        isRIAlreadyTriggered = True
                        for CAUType in usedCauSet:
                            eventRow = {'Date' : currentTime.isoformat(), 'CAU': CAUType, 'Type': eventType['Ri']}
                            event_writer.writerow(eventRow)

                # Trigger and write ShutDown event
                if currentTime.hour == hour_offOn[0] and currentRow['Product'] == 'ec2_instance':
                    resourceUsed[currentRow['UsageType']] /= instance_divider
                    resourceUsed[currentRow['UsageType']] -= 1
                    currentRow['Cost'] = usageCost[currentRow['UsageType']] * resourceUsed[currentRow['UsageType']]
                    if currentRow['Operation'] == operation[0]: # if RI on reduce the pricing
                        currentRow['Cost'] = currentRow['Cost'] * ri_percent_multiplier

                    if isThisEventAlreadySet[currentRow['CAU']] == False:
                        isThisEventAlreadySet[currentRow['CAU']] = True
                        eventRow = {'Date' : currentTime.isoformat(), 'CAU': currentRow['CAU'], 'Type': eventType['shut']}
                        event_writer.writerow(eventRow)

                # Trigger and write ReStart event
                if currentTime.hour == hour_offOn[1] and currentRow['Product'] == 'ec2_instance':
                    resourceUsed[currentRow['UsageType']] = resourceRef[currentRow['UsageType']] # reset initial resource nbr
                    currentRow['Cost'] = usageCost[currentRow['UsageType']] * resourceUsed[currentRow['UsageType']]

                    if currentRow['Operation'] == operation[0]: # if RI on reduce the pricing
                        currentRow['Cost'] = currentRow['Cost'] * ri_percent_multiplier
                    if currentTime.hour >= hour_Iops[0] and currentTime.hour < hour_Iops[1]:
                        currentRow['Cost'] = currentRow['Cost'] * iops_percet_multiplier
                        
                    if isThisEventAlreadySet[currentRow['CAU']] == False:
                        isThisEventAlreadySet[currentRow['CAU']] = True
                        eventRow = {'Date' : currentTime.isoformat(), 'CAU': currentRow['CAU'], 'Type': eventType['start']}
                        event_writer.writerow(eventRow)

               # Trigger and write iops_down event
                if currentTime.hour == hour_Iops[0]:
                    currentRow['Cost'] = currentRow['Cost'] * iops_percet_multiplier
                    if isIOPSAlreadySet[currentRow['CAU']] == False:
                        isIOPSAlreadySet[currentRow['CAU']] = True
                        eventRow = {'Date' : currentTime.isoformat(), 'CAU': currentRow['CAU'], 'Type': eventType['iopDown']}
                        event_writer.writerow(eventRow)

                # Trigger and write iops_up event
                if currentTime.hour == hour_Iops[1]:
                    currentRow['Cost'] = usageCost[currentRow['UsageType']] * resourceUsed[currentRow['UsageType']]
                    if currentRow['Operation'] == operation[0]:
                        currentRow['Cost'] = currentRow['Cost'] * ri_percent_multiplier
                    if isIOPSAlreadySet[currentRow['CAU']] == False:
                        isIOPSAlreadySet[currentRow['CAU']] = True
                        eventRow = {'Date' : currentTime.isoformat(), 'CAU': currentRow['CAU'], 'Type': eventType['iopUP']}
                        event_writer.writerow(eventRow)


                # Some Cost randomization                       
                #currentRow['Cost'] = currentRow['Cost'] * random.uniform(0.98, 1.02)
                if currentRow['Cost'] != 0:
                    writer.writerow(currentRow)

            currentTime += timedelta(hours=1)
            i += 1

random.seed(None)

ret = system("cp ./save.csv ./teevity_savings.csv")
ret2 = system("cp ./save_events.csv ./teevity_events.csv")
file = open(fname, "rb")
ev_file = open(efname, "rb")
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