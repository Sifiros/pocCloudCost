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
    lowAverage = 0
    expAverage = 0
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
            self.pushEventScope('iops', curScopes['iops'], self.endPeriodDate)

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
        for eventScope in self.eventScopes: # calculating average costs for each event scope
            eventScope['costs'] = {}
            nbs = {}

            for cost in self.costs:
                costDate = parse(cost['date'])
                if costDate.timestamp() > eventScope['startDate'].timestamp() and \
                   costDate.timestamp() < eventScope['endDate'].timestamp(): # costdate included in cur event scope : getting costs
                    for res in cost['costs']:
                        if res not in eventScope['costs']:
                            eventScope['costs'][res] = int(cost['costs'][res])
                            nbs[res] = 1
                        else:
                            eventScope['costs'][res] += int(cost['costs'][res])
                            nbs[res] += 1

            # averages
            eventScope['totalCosts'] = 0
            for cur in eventScope['costs']:
                eventScope['costs'][cur] /= nbs[cur]
                eventScope['totalCosts'] += eventScope['costs'][cur]


    def printEventScopes(self):
        for cur in self.eventScopes:
            print(cur)

    def getEventContext():
        pass

    def getCostScope(self):
        pass

    def calcRI():
        pass

