#!/usr/bin/python2
# vim: set fileencoding=utf-8 :

import csv
from datetime import timedelta
from dateutil.parser import *
from os import system
import random

fname = "teevity_savings.csv"
exemple = {'Account': '492743234823', 'Region': 'eu-west-1', 'UsageType': 'm4.2xlarge', \
           'Product': 'ec2_instance', 'Cost': '3', 'Date': '2017-08-10-19:00', 'Operation': 'Reserved', \
           'CAU (aka ResourceGroup)': 'PROD/ProjectA/Frontend'}

CAUs = ['PROD/ProjectA/Fontend', 'PROD/ProjectA/Backend', 'PROD/ProjectB/Fontend', 'PROD/ProjectB/Backend', \
        'DEV/ProjectA/Fontend', 'DEV/ProjectA/Backend', 'DEV/ProjectB/Fontend', 'DEV/ProjectB/Backend']

iteration_number = 1000
account = '492743284828'
startDate = '2017-08-10-00:00'
region = 'eu-west-1'
usageCost = {'m4.2xlarge' : 8, 'bytes-out': 0.3, 'r3.8xlarge': 80}
operation =  ['Reserved', 'OnDemand']


#random.randrange(start, stop, step)
def start_writing(filename, fieldnames):
    newRow = {'Account':account, 'Region':region}
    with open(filename, 'a+') as wfile:
        i = 0
        writer = csv.DictWriter(wfile, fieldnames)
        currentTime = parse(startDate)
        currentUsageType = ""

        while i < iteration_number:
            usageRand = random.randrange(0, 3, 1)
            for j, x in enumerate(usageCost):
                print("enumerate => {}".format(j))
                if j == usageRand:
                    newRow['UsageType'] = x
                    newRow['Cost'] = usageCost[x]
                    if x == 'bytes-out':
                        newRow['Operation'] = 'datatransfert'
                        newRow['Product'] = 'ec2'
                    else:
                        newRow['Operation'] = operation[(usageRand + 1) % 2]
                        newRow['Product'] = 'ec2_instance'
            CAURand = random.randrange(0, 8, 1)
            newRow['CAU'] = CAUs[CAURand]
            if ((random.random() * 100) % 3) == 0:
                currentTime += timedelta(hours=1)
            newRow['Date'] = currentTime.isoformat()
            print(currentTime)
            writer.writerow(newRow)
            i = i + 1

file = open(fname, "rb")
random.seed(None)
system("cp ./save.csv ./teevity_savings.csv")
try:
    reader = csv.DictReader(file)
    fieldnames = reader.fieldnames
    print("tab identifiers => {}".format(fieldnames))
    print("")
finally:
    file.close()
    start_writing(fname, fieldnames)