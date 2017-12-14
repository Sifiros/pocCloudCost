#!/usr/bin/python3

import sys
import os
import json
from dateutil.parser import *
from datetime import *

class GainCalculator():
    nextId = 0
    costs = []
    events = []
    endPeriodDate = datetime.now()

    eventScopes = []

    # Constructor
    def __init__(self, costs, events):
        self.costs = costs
        for cost in self.costs:
            cost["CAU"] = "foo"
            cost['tagGroup'] = "onch"
            cost['date'] = parse(cost['date'])
            if cost['date'].timestamp() > self.endPeriodDate.timestamp():
                self.endPeriodDate = cost['date']
            ##eggreg
            tot = 0
            for k in cost['costs']:
                tot += cost['costs'][k]
            cost['costs'] = tot

        self.events = events
        for event in self.events:
            event['CAU'] = 'foo'
            event['id'] = event['date'] + '_' + event['CAU'] + '_' + event['type'] #self.getNewId()
            event['date'] = parse(event['date'])

    def getNewId(self):
        self.nextId += 1
        return (self.nextId - 1)

    def createEventsDict(self, islist):
        return ({
            'offon': [] if islist else None,
            'iops': [] if islist else None,
            'reserved_instance': [] if islist else None,
            'destroy_ebs_volume': [] if islist else None
        })

    # Création des event scopes (start date & endDate liés par un meme type d'event)
    def processEvents(self):
        eventCyclesMapping = {
            'offon': ('start_instance', 'shutdown_instance'),
            'iops': ('increase_iops', 'decrease_iops'),
            'destroy_ebs_volume': ('destroy_ebs_volume', False),
            'reserved_instance': ('reserved_instance', False)
        }
        curScopes = {}
        for cur in self.events:
            newScope = False
            for cycleType in eventCyclesMapping: # looking for cycle including cur event
                cycleEvents = eventCyclesMapping[cycleType]
                if cur['type'] in cycleEvents: # we've found cycle corresponding to this event
                    cycleId = cycleType + '_' + cur['CAU']
                    effectiveSavingEvent = cycleEvents[1] == False or cycleEvents[1] == cur['type']
                    # can't handle 2 successive same event of the same cycle (except for one shot event)
                    if cycleId in curScopes and curScopes[cycleId]['custodianEffective'] == effectiveSavingEvent:
                        print("Events processing error : can't handle 2 successive start or end without corresponding start event")
                        break

                    start = curScopes[cycleId] if cycleId in curScopes else \
                            ({'startDate': cur['date'], 'custodianEffective': effectiveSavingEvent, 'affectedResources': cur['affectedResources'], 'id': cur['id'], 'type': cycleType, 'CAU': cur['CAU']})

                    if cycleId in curScopes or cycleEvents[1] == False: # we're on an end or one shot event : prepare new scope
                        newScope = start
                        newScope['endDate'] = cur['date'] if cycleEvents[1] != False else self.endPeriodDate
                        if cycleId in curScopes:
                            del curScopes[cycleId]
                    # store new cycle start event (not in one shot case)
                    if cycleEvents[1] != False:
                        if newScope: # we just ended a cycle : update startDate / endDate
                            start = dict(newScope)
                            start['startDate'] = start['endDate']
                            start['custodianEffective'] = not start['custodianEffective']
                            start['id'] = cur['id']
                            del start['endDate']
                        curScopes[cycleId] = start
                    break
            if newScope:
                self.eventScopes.append(newScope)

        for scopeId in curScopes:
            unfinishedEvent = curScopes[scopeId]
            unfinishedEvent['endDate'] = self.endPeriodDate
            self.eventScopes.append(unfinishedEvent)

    # Récupère les event scope matchant date
    def getCurrentSavingCycles(self, date, CAU):
        eventTypes = [];
        found = False
        for eventScope in self.eventScopes:
            if date.timestamp() >= eventScope['startDate'].timestamp() and \
               date.timestamp() < eventScope['endDate'].timestamp() and eventScope['custodianEffective'] and \
               eventScope['CAU'] == CAU:
                eventTypes.append(eventScope)
                found = True
        if found: 
            eventTypes.sort(key= lambda scope : scope['startDate'].timestamp())
            return eventTypes
        return False



    # Renvoie chaque event ses metrics de savings pour chaque date ayant un cost
    # Nécessite l'appel préalable de processEvents (création des eventscopes)
    # TODO: -> event scope on off doit sarreter en fin de week
    def getSavings(self):
        # sortie de la fonction : 
        result = { 
            "savings": [],
            "costs": [],
            "eventScopes": [],
            "eventNames": []
        }
        costs = list(self.costs)
        lastScopes = {} # scopes applied on last cost metric sorted by CAU, required to detect whenever a scope ends before a child one
        lastCost = {} # required for scope theorical costs (real cost before a scope beginning)

        for costAndUsageDataItem in costs:
            costAndUsageDataItem['saving'] = 0 # contiendra le total de bénéfice de tous les event scopes s'y appliquant
            metricId = costAndUsageDataItem['CAU'] + costAndUsageDataItem['tagGroup']
            if metricId not in lastCost:
                lastCost[metricId] = costAndUsageDataItem['costs']
            curDate = costAndUsageDataItem['date']
            currentSavingCycles = self.getCurrentSavingCycles(curDate, costAndUsageDataItem['CAU'])
            currentScopes = currentSavingCycles if currentSavingCycles else []
            curSavings = {}
            i = 0
            for curScope in currentScopes:
                if 'theoricalCost' not in curScope: # First scope appearance : init theoricalCost / saving
                    if curScope['type'] not in result['eventNames']:
                        result['eventNames'].append(curScope['type'])
                    curScope['theoricalCost'] = {}
                    curScope['saving'] = 0
                    result['eventScopes'].append(curScope)

                if metricId not in curScope['theoricalCost']: 
                    curScope['theoricalCost'][metricId] = lastCost[metricId]
                else: # sync theorical costs (in case of parent scope ending)
                    curScope['theoricalCost'][metricId] = lastScopes[curScope['CAU']][i]['theoricalCost'][metricId]
                # Theorical saving between scope theorical cost and current real cost
                curSavings[curScope['type']] = (curScope['theoricalCost'][metricId] - costAndUsageDataItem['costs'])
                i += 1

            nbScopes = len(currentScopes)
            for k, v in enumerate(currentScopes):
                saving = curSavings[v['type']]
                if k < (nbScopes - 1): # substract next theorical saving for the current real one
                    saving -= curSavings[currentScopes[(k + 1)]['type']]
                # saving = bénéfice de l'eventScope pour le costMetric actuel
                result['savings'].append({
                    'CAU': v['CAU'],
                    'tagGroup': costAndUsageDataItem['tagGroup'],
                    'date': curDate.isoformat(),
                    'type': v['type'],
                    'saving': saving
                })
                # v['saving'] = Bénéfice total de l'eventScope appliqué à tous les costMetric de même CAU
                v['saving'] += saving
                # bénéfice de tous les scopes appliqués au costMetric actuel
                costAndUsageDataItem['saving'] += saving

            result['costs'].append({
                'CAU': costAndUsageDataItem['CAU'],
                'tagGroup': costAndUsageDataItem['tagGroup'],
                'date': curDate.isoformat(),
                'cost': costAndUsageDataItem['costs'],
                'matchingEventTypes': False if not currentSavingCycles else True,
                'saving': costAndUsageDataItem['saving']
            })

            lastCost[metricId] = costAndUsageDataItem['costs']
            lastScopes[costAndUsageDataItem['CAU']] = list(currentScopes) if currentScopes != False else []

        result['eventScopes']  = list(map(lambda scope: ({
            'startDate': scope['startDate'].isoformat(),
            'endDate': scope['endDate'].isoformat(),
            'type': scope['type'],
            'CAU': scope['CAU'],
            'saving': scope['saving']
        }), result['eventScopes']))
        self.storeToFile(result)
        return result

    def storeToFile(self, data):
        with open('./ui/eventSavings.json', 'w') as fileToWrite:
            fileToWrite.write('datas = ' + json.dumps(data))
        fileToWrite.close()

    #
    # Debug Print Functions
    #

    def printCurrentScope(self):
        print('----------- Events : (' + str(len(self.events)) + ')')
        for x in self.events:
            print(x)
        print()
        # print('----------- Costs : (' + str(len(self.costs)) + ')')
        # for x in self.costs:
        #     print(x)
        print()

    def printEventScopes(self):
        print('----------- Events scopes : ')
        for cur in self.eventScopes:
            print(cur)
        print('')
