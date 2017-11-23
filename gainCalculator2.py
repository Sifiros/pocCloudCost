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

    # Permet de trier une liste  d'event scope par priorité
    def getEventScopePriority(self, scope):
        return scope['startDate'].timestamp()
        priorities = ({
            "reserved_instance": 1,
            "onoff": 10,
            "iops": 10,
            "destroy_ebs_volume": 10
        })
        if (scope['type']) not in priorities:
            return 10
        return priorities[(scope['type'])]

    # Récupère les event scope matchant date
    def getMatchingEventTypes(self, date):
        eventTypes = [];
        found = False
        for eventScope in self.eventScopes:
            if date.timestamp() >= eventScope['startDate'].timestamp() and \
               date.timestamp() < eventScope['endDate'].timestamp() and eventScope['custodianEffective']:
                eventTypes.append(eventScope)
                found = True
        if found: # FIX PRIORITY ???
            eventTypes.sort(key=self.getEventScopePriority)
            return eventTypes
        return False

    # Renvoit un dictionnaire de chaque date avec son coût non optimisé théorique
    # Associe aussi chaque coût (de period) avec les events scopes liés dans cost['matchingEventTypes']
    def getUnoptimizedCosts(self, period):
        lastUnoptimized = 0
        byDates = {}
        for cur in period:
            # cur['date'] = cur['date'].isoformat()
            cur['matchingEventTypes'] = self.getMatchingEventTypes(cur['date'])
            if cur['matchingEventTypes'] == False:
                lastUnoptimized = cur
                unoptimized = cur['costs']
            else:
                unoptimized = lastUnoptimized['costs']
            byDates[cur['date']] = unoptimized
        return byDates



    def balanceSavingPercents(self, scopes, targetScope, costs, unoptimized, totalSaving):
        targetPassed = False
        wholeSaving = (float(totalSaving) / unoptimized)
        toBalance = []

        for scope in scopes:
            if scope == targetScope:
                targetPassed = True
            elif 'saving' in scope and targetPassed:
                toBalance.append(scope)

        if len(toBalance) == 0: # no more scope after this : giving him whole remaining saving
            targetScope['saving'] = wholeSaving
        else:
            targetScope['saving'] = wholeSaving


    # Renvoie chaque event ses metrics de savings pour chaque date ayant un cost
    # Nécessite l'appel préalable de processEvents (création des eventscopes)
    # TODO: -> event scope on off doit sarreter en fin de week
    #       -> event / costs décalés d'une heure matin / soir
    def getSavings(self):
        costs = list(self.costs)
        costs = self.mergeResourceCosts(list(costs))
        unoptimizedCosts = self.getUnoptimizedCosts(costs)
        events = self.createEventsDict(True)
        for metric in costs:
            curDate = metric['date']
            eventsApplied = [] # Liste des noms d'event comprenant la date actuelle

            if metric['matchingEventTypes'] != False: # Cout actuel compris dans au moins un scope
                totalSaving = unoptimizedCosts[curDate] - metric['costs']
                # print(" at " + str(metric["date"]) + " : saving =  " + str(totalSaving) + " divided into " + str(metric["matchingEventTypes"]))
                idx = 0
                for curScope in metric['matchingEventTypes']:
                    if 'saving' not in curScope: 
                        # print("at " + str(idx) + " / " + str(len(metric['matchingEventTypes'])) + " / " + str(metric['date']) + " : " + curScope['type'] + " || totalSaving = " + str(totalSaving) + " || curCost = " + str(metric['costs']))
                        self.balanceSavingPercents(metric['matchingEventTypes'], curScope, metric['costs'], unoptimizedCosts[curDate], totalSaving)
                        # curScope['saving'] = float(float(totalSaving) / unoptimizedCosts[curDate])
                        # print("SAVING PERCENTS = " + str(curScope["saving"]) + " (currently equals to " + str((unoptimizedCosts[curDate] * curScope['saving'])) + " saving)")
                    idx += 1
                    curSaving = (unoptimizedCosts[curDate] * curScope['saving'])
                    if (totalSaving - curSaving) < 0:
                        curSaving = totalSaving
                    totalSaving = totalSaving - curSaving
                    # print("at " + str(metric['date']) + " REMAINS " + str(totalSaving) + " SAVINGS / " + curScope["type"] + " SAVES " + str(curSaving) + " // cost : " +  str(metric['costs']) + " / unoptimized : " + str(unoptimizedCosts[curDate]))
                    events[curScope['type']].append({
                        'saving': curSaving,
                        'date': curDate
                    })
                    eventsApplied.append(curScope['type'])
            # for curEvent in events:
            #     if curEvent not in eventsApplied:
            #         events[curEvent].append({'saving': 0, 'date': curDate})
        # fileToWrite = open('./eventSavings.json', 'w')
        # fileToWrite.write(json.dumps({
        #     'events': events,
        #     'costs': costs
        # }))
        return events

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
