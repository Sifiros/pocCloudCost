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
        for cost in self.costs:
            cost['date'] = parse(cost['date'])
        self.events = events
        for event in self.events:
            event['date'] = parse(event['date'])

    def printCurrentScope(self):
        print('----------- Events : (' + str(len(self.events)) + ')')
        for x in self.events:
            print(x)
        print('----------- Costs : (' + str(len(self.costs)) + ')')
        for x in self.costs:
            print(x)

    def processEvents(self):
        curScopes = {
            'onoff': None,
            'iops': None
        }
        for cur in self.events:
            if cur['type'] == 'shutdown_instance': # associer events aux instanceid
                if curScopes['onoff'] and curScopes['onoff']['effective'] == False:
                    self.pushEventScope('onoff', curScopes['onoff'], cur['date'])
                curScopes['onoff'] = {'startDate': cur['date'], 'effective': True, 'affectedResources': cur['affectedResources']}
            elif cur['type'] == 'start_instance':
                if curScopes['onoff'] and curScopes['onoff']['effective'] is True:
                    self.pushEventScope('onoff', curScopes['onoff'], cur['date'])
                curScopes['onoff'] = {'startDate': cur['date'], 'effective': False, 'affectedResources': cur['affectedResources']}
            elif cur['type'] == 'modify_ebs_iops':
                if curScopes['iops']:
                    self.pushEventScope('iops', curScopes['iops'], cur['date'])
                curScopes['iops'] = {'startDate': cur['date'], 'effective': True, 'affectedResources': cur['affectedResources']}
            elif cur['type'] == 'destroy_ebs_volume':
                self.pushEventScope('destroy_ebs', {'startDate': cur['date'], 'effective': True, 'affectedResources': cur['affectedResources']}, self.endPeriodDate)

        if curScopes['onoff']:
            self.pushEventScope('onoff', curScopes['onoff'], self.endPeriodDate)
        if curScopes['iops']:
            self.pushEventScope('iops', curScopes['iops'], self.endPeriodDate)

    def pushEventScope(self, eventType, scope, dateEnd):
        self.eventScopes.append({
            'type': eventType,
            'startDate': scope['startDate'],
            'endDate': dateEnd,
            'effectiveDuration': ((dateEnd.timestamp() - scope['startDate'].timestamp()) / 60),
            'custodianEffective': scope['effective'],
            'affectedResources': scope['affectedResources']
        })

    def processCostInEvent(self):
        for eventScope in self.eventScopes: # calculating average costs for each event scope
            eventScope['costs'] = {}
            nbs = {}

            for cost in self.costs:
                if cost['date'].timestamp() > eventScope['startDate'].timestamp() and \
                   cost['date'].timestamp() < eventScope['endDate'].timestamp(): # costdate included in cur event scope : getting costs
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


    def analyzePeriod(self, date1, date2):
        periodCosts = []

        for cost in self.costs:
            if cost['date'].timestamp() >= date1.timestamp() and \
               cost['date'].timestamp() <= date2.timestamp():
                cost['matchingEventTypes'] = self.getMatchingEventTypes(cost['date'], cost['costs'])
                periodCosts.append(cost)

        return periodCosts


    def getMatchingEventTypes(self, date, resources):
        eventTypes = {};
        found = False
        for eventScope in self.eventScopes:
            if date.timestamp() >= eventScope['startDate'].timestamp() and \
               date.timestamp() <= eventScope['endDate'].timestamp() and eventScope['custodianEffective']:
               for res_hit in eventScope['affectedResources']:
                    if res_hit in resources:
                        found = True
                        eventTypes[eventScope['type']] = True
        return eventTypes if found else False

    def printPeriodStats(self, period):
        print('----- Period analyze results : ')
        nbAffectedCosts = 0
        for curCost in period:
            print(curCost)
            if curCost['matchingEventTypes']:
                nbAffectedCosts += 1
        print('')
        percentage = round(((nbAffectedCosts / len(period)) * 100), 2)
        print(str(nbAffectedCosts) + ' / ' + str(len(period)) + ' (' + str(percentage) + '%) cost metrics have been affected by events ')

    def printEventScopes(self):
        print('----------- Events scopes : ')
        for cur in self.eventScopes:
            print(cur)

    def getEventContext():
        pass

    def getCostScope(self):
        pass

    def calcRI():
        pass

