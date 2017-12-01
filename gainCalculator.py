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

    eventScopes = []


    # Constructor
    def __init__(self, costs, events):
        self.costs = costs
        for cost in self.costs:
            cost['date'] = parse(cost['date'])
            if cost['date'].timestamp() > self.endPeriodDate.timestamp():
                self.endPeriodDate = cost['date']
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

    def pushEventScope(self, eventType, scope, dateEnd):
        self.eventScopes.append({
            'type': eventType,
            'startDate': scope['startDate'],
            'endDate': dateEnd,
            'effectiveDuration': ((dateEnd.timestamp() - scope['startDate'].timestamp()) / 60),
            'custodianEffective': scope['effective'],
            'affectedResources': scope['affectedResources']
        })

    # Création des event scopes (start date & endDate liés par un meme type d'event)
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

    ### Costs
    # Merge des couts de ressource en un total
    def mergeResourceCosts(self, period):
        for cur in period:
            tot = 0
            for resourceCost in cur['costs']:
                tot += cur['costs'][resourceCost]
            cur['costs'] = tot
        return period

    # Récupère les event scope matchant date
    def getMatchingEventTypes(self, date):
        eventTypes = [];
        found = False
        for eventScope in self.eventScopes:
            if date.timestamp() >= eventScope['startDate'].timestamp() and \
               date.timestamp() < eventScope['endDate'].timestamp() and eventScope['custodianEffective']:
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
        costs = list(self.costs)
        costs = self.mergeResourceCosts(list(costs))
        eventSavings = self.createEventsDict(True)
        eventScopes = self.createEventsDict(True)
        lastScopes = [] # scopes applied on last cost metric, required to detect whenever a scope ends before a child one
        lastCost = costs[0]['costs'] if len(costs) > 0 else 0 # required for scope theorical costs (real cost before a scope beginning)

        for metric in costs:
            curDate = metric['date']
            metric['matchingEventTypes'] = self.getMatchingEventTypes(curDate)
            eventsApplied = [] # Liste des noms d'event comprenant la date actuelle
            currentScopes = metric['matchingEventTypes']

            if currentScopes != False: # Cout actuel compris dans au moins un scope
                savings = {}
                i = 0
                for curScope in currentScopes:
                    # a parent scope disappeared ; must sync theorical costs :
                    if len(lastScopes) > (i + 1) and curScope == lastScopes[(i + 1)]: 
                        curScope['theoricalCost'] = lastScopes[i]['theoricalCost'] # disappeared scope theorical cost

                    if 'theoricalCost' not in curScope: # First scope appearance : init theoricalCost / totalSaving
                        curScope['theoricalCost'] = lastCost
                        curScope['totalSaving'] = 0
                        eventScopes[curScope['type']].append(curScope)
                    # Theorical saving between scope theorical cost and current real cost
                    savings[curScope['type']] = (curScope['theoricalCost'] - metric['costs'])
                    eventsApplied.append(curScope['type'])
                    i += 1

                nbScopes = len(currentScopes)
                for k, v in enumerate(currentScopes):
                    saving = savings[v['type']]
                    if k < (nbScopes - 1): # substract next theorical saving for the current real one
                        saving -= savings[currentScopes[(k + 1)]['type']]
                    eventSavings[v['type']].append({
                        'saving': saving,
                        'date': curDate.isoformat()
                    })
                    v['totalSaving'] += saving
            # Set to 0 every non-applied event's saving for current date
            for curEvent in eventSavings:
                if curEvent not in eventsApplied:
                    eventSavings[curEvent].append({'saving': 0, 'date': curDate.isoformat()})

            lastCost = metric['costs']
            lastScopes = list(currentScopes) if currentScopes != False else []

        for name in eventScopes:
            eventScopes[name] = list(map(lambda scope: ({
                "startDate": scope["startDate"].isoformat(),
                "endDate": scope["endDate"].isoformat(),
                "totalSaving": scope["totalSaving"]
            }), eventScopes[name]))
        result = {
            "eventSavings": eventSavings,
            "costs": costs,
            "eventScopes": eventScopes
        }
        self.storeToFile(result)
        return result


    def storeToFile(self, data):
        for cost in data['costs']:
            cost['matchingEventTypes'] = False if not cost['matchingEventTypes'] else True
            cost['date'] = cost['date'].isoformat()

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
