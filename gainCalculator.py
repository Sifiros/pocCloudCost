#!/usr/bin/python3

import sys
import os
import json
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

    def createEventsDict(self, islist):
        return ({
            'onoff': [] if islist else None,
            'iops': [] if islist else None,
            'reserved_instance': [] if islist else None,
            'destroy_ebs_volume': [] if islist else None
        })

    def printCurrentScope(self):
        print('----------- Events : (' + str(len(self.events)) + ')')
        for x in self.events:
            print(x)
        print('----------- Costs : (' + str(len(self.costs)) + ')')
        for x in self.costs:
            print(x)

    def processEvents(self):
        curScopes = self.createEventsDict(False)
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
                self.pushEventScope(cur['type'], {'startDate': cur['date'], 'effective': True, 'affectedResources': cur['affectedResources']}, self.endPeriodDate)
            elif cur['type'] == 'reserved_instance':
                if curScopes['reserved_instance'] and curScopes['reserved_instance']['effective'] == False:
                    self.pushEventScope('reserved_instance', curScopes['reserved_instance'], cur['date'])
                curScopes['reserved_instance'] = {'startDate': cur['date'], 'effective': True, 'affectedResources': cur['affectedResources']}

        if curScopes['onoff']:
            self.pushEventScope('onoff', curScopes['onoff'], self.endPeriodDate)
        if curScopes['iops']:
            self.pushEventScope('iops', curScopes['iops'], self.endPeriodDate)
        if curScopes['reserved_instance']:
            self.pushEventScope('reserved_instance', curScopes['reserved_instance'], self.endPeriodDate)

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
                        cost['costs'][res] = int(cost['costs'][res])
                        if res not in eventScope['costs']:
                            eventScope['costs'][res] = cost['costs'][res]
                            nbs[res] = 1
                        else:
                            eventScope['costs'][res] += cost['costs'][res]
                            nbs[res] += 1

            # averages
            eventScope['totalCosts'] = 0
            for cur in eventScope['costs']:
                eventScope['costs'][cur] /= nbs[cur]
                eventScope['totalCosts'] += eventScope['costs'][cur]

    def mergeResourceCosts(self, period):
        for cur in period:
            tot = 0
            for resourceCost in cur['costs']:
                tot += cur['costs'][resourceCost]
            cur['costs'] = tot
        return period

    def getUnoptimizedCosts(self, period):
        lastUnoptimized = 0
        byDates = {}
        for cur in period:
            cur['date'] = cur['date'].isoformat()
            if cur['matchingEventTypes'] == False:
                lastUnoptimized = cur
                unoptimized = cur['costs']
            else:
                unoptimized = lastUnoptimized['costs']
            byDates[cur['date']] = unoptimized
        return byDates

    def eventSavingsForPeriod(self, period):
        period = self.mergeResourceCosts(list(period))
        unoptimizedCosts = self.getUnoptimizedCosts(period)
        events = self.createEventsDict(True)
        for metric in period:
            for cur in events:
                hasEvent = metric['matchingEventTypes'] and (cur in metric['matchingEventTypes'])
                newSaving = {'saving': 0, 'date': metric['date']}

                if hasEvent == False:
                    events[cur].append(newSaving)
                else:
                    newSaving['saving'] = unoptimizedCosts[metric['date']] - metric['costs']
                    events[cur].append(newSaving)


        fileToWrite = open('./eventSavings.json', 'w')
        fileToWrite.write(json.dumps({
            'events': events,
            'costs': period
        }))
        return events

     #return an object filled with resources used between date1 and date3
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

    def printPeriodJson(self, period):
        glob = []

        # list base creation
        for x in period:
            for rsc in x['costs']:
                if len(glob) == 0:
                    glob.append({rsc: {
                        'prices' : [],
                        'nonEventCost':0
                        }})
                else:
                    for elem in glob:
                        if (list(elem.keys())[:1])[0] != rsc:
                            glob.append({rsc: {
                                'prices' : [],
                                }})
                            break

        # list filling
        for elem in glob:
            for x in period:
                for rsc in x['costs']:
                    if rsc == list(elem.keys())[:1][0]:
                        elem[rsc]['prices'].append({
                            'date' : x['date'].isoformat(),
                            'price' : x['costs'][rsc],
                            'matchingEventTypes' : x['matchingEventTypes']
                            })
                        if x['matchingEventTypes'] == False:
                           elem[rsc]['nonEventCost'] = int(x['costs'][rsc])

        # write object to file
        fileToWrite = open('./data.json', 'w')
        fileToWrite.write(json.dumps(glob))

    def printPeriodStats(self, period):
        print('----- Period analyze results : (' + str(len(period)) + ')')
        nbAffected = {}
        affectedCosts = {}
        nbBasic = {}
        basicCosts = {}
        currentRealCost = 0
        unoptimizedTheoricalCost = 0
        lowCost = 0
        upCost = 0
        upCount = 0
        # JSON GRAPH Intelligence

        nbAffectedCosts = 0
        for curCost in period:
            print(curCost)
            if curCost['matchingEventTypes']:
                nbAffectedCosts += 1

            for resource in curCost['costs'] :
                nbs = nbAffected if curCost['matchingEventTypes'] != False else nbBasic
                costSums = affectedCosts if curCost['matchingEventTypes'] != False else basicCosts
                currentRealCost += int(curCost['costs'][resource])
                if curCost['matchingEventTypes'] != False:
                    lowCost = int(curCost['costs'][resource])
                else:
                    upCost = int(curCost['costs'][resource])
                    upCount += 1


                curCost['costs'][resource] = int(curCost['costs'][resource])
                costSums[resource] = (curCost['costs'][resource] + costSums[resource]) if resource in costSums else curCost['costs'][resource]
                nbs[resource] = (nbs[resource] + 1 ) if resource in nbs else 1

        print('')
        percentage = round(((nbAffectedCosts / len(period)) * 100), 2) if len(period) != 0 else 0
        print(str(nbAffectedCosts) + ' / ' + str(len(period)) + ' (' + str(percentage) + '%) cost metrics have been affected by events \n')
        print("current date ===========> {}\n".format(curCost['date'].isoformat()))

        unoptimizedTheoricalCost = ((upCost - lowCost) * upCount) + currentRealCost

        for res in nbAffected:
            affectedCosts[res] = round((affectedCosts[res] / int(nbAffected[res])), 2)
            print('Average cost/h for ' + res + ' during event periods : ' + str(affectedCosts[res]) + '\n')
        for res in nbBasic:
            basicCosts[res] = round((basicCosts[res] / int(nbBasic[res])), 2)
            print('Average cost/h for ' + res + ' during non-event periods : ' + str(basicCosts[res]) + '\n')
        print('You have paid {} with optimization'.format(currentRealCost))
        print('You would have paid {} without'.format(unoptimizedTheoricalCost))
        print('That represent {} of economy on this period'.
                format(unoptimizedTheoricalCost - currentRealCost))


    def printEventScopes(self):
        print('----------- Events scopes : ')
        for cur in self.eventScopes:
            print(cur)
        print('')

    def getEventContext():
        pass

    def getCostScope(self):
        pass

    def calcRI():
        pass

