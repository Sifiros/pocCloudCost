#!/usr/bin/python3

import sys
import os
from dateutil.parser import *
from datetime import *

class GainCalculator():
    costs = []
    events = []
    endPeriodDate = datetime.now()

    currentCycleGain = 0
    lowCycleCost = 0
    expCycleCost = 0
    eventScopes = []

    def __init__(self, costs, events):
        self.costs = costs
        self.events = events

    def printCurrentScope(self):
        for x in self.events:
            print(x)

    def processEvents(self):
        curScopes = {
            'onoff': None,
            'iops': None
        }
        for cur in self.events:
            if cur['type'] == 'shutdown_instance': # associer events aux instanceid
                if curScopes['onoff'] and curScopes['onoff']['effective'] == False:
                    self.pushEventScope('onoff', curScopes['onoff'], parse(cur['date']))
                curScopes['onoff'] = {'startDate': cur['date'], 'effective': True}
            elif cur['type'] == 'start_instance':
                if curScopes['onoff'] and curScopes['onoff']['effective'] is True:
                    self.pushEventScope('onoff', curScopes['onoff'], parse(cur['date']))
                curScopes['onoff'] = {'startDate': cur['date'], 'effective': False}
            elif cur['type'] == 'modify_ebs_iops':
                if curScopes['iops']:
                    self.pushEventScope('iops', curScopes['iops'], parse(cur['date']))
                curScopes['iops'] = {'startDate': cur['date'], 'effective': True}
            elif cur['type'] == 'destroy_ebs_volume':
                self.pushEventScope('destroy_ebs', {'startDate': cur['date'], 'effective': True}, self.endPeriodDate)

        if curScopes['onoff']:
            self.pushEventScope('onoff', curScopes['onoff'], self.endPeriodDate)
        if curScopes['iops']:
            self.pushEventScope('iops', curScopes['iops'], parse(cur['date']))

    def pushEventScope(self, eventType, scope, dateEnd):
        scope['startDate'] = parse(scope['startDate'])
        self.eventScopes.append({
            'type': eventType,
            'startDate': scope['startDate'],
            'endDate': dateEnd,
            'effectiveDuration': ((dateEnd.timestamp() - scope['startDate'].timestamp()) / 60),
            'custodianEffective': scope['effective']
        })

    def processCostInEvent(self):

        expCounter = 0
        expTimeActivity = 0
        lowCounter = 0
        expTimeActivity = 0


        for cost in self.costs:
            for event in self.eventScopes:
                costDate = parse(cost['date'])
                if costDate.timestamp() > event['startDate'].timestamp() and \
                   costDate.timestamp() < event['endDate'].timestamp():
                       event['ressourceInfo'] = cost['costs']
                       print(event['ressourceInfo'])
                       for x in event['ressourceInfo']:
                           if event['custodianEffective'] is False:
                               self.expCycleCost += int(event['ressourceInfo'][x]) * (event['effectiveDuration'] / 60)
                               expCounter += 1
                           else:
                               self.lowCycleCost += int(event['ressourceInfo'][x]) * (event['effectiveDuration'] / 60)
                               lowCounter += 1
        self.expCycleCost = self.expCycleCost / expCounter
        self.lowCycleCost = self.lowCycleCost / lowCounter
        print("expPrice => {} lowPrice => {}".format(self.expCycleCost, self.lowCycleCost))

    def printEventScopes(self):
        for cur in self.eventScopes:
            print(cur)

    def getEventContext():
        pass

    def getCostScope(self):
        pass

    def calcRI():
        pass

