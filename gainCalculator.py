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
    # savingCycles sorted by date then CAU
    savingCyclesByDate = False
    # costUnits sorted by date, CAU then tagGroup
    costUnitsByDate = False

    # Constructor
    def __init__(self, costs, events):
        self.costs = costs
        for cost in self.costs:
            cost['date'] = parse(cost['date'])
            if cost['date'].timestamp() > self.endPeriodDate.timestamp():
                self.endPeriodDate = cost['date']
        self.costs.sort(key= lambda cur : cur['date'].timestamp())

        self.events = events
        for event in self.events:
            event['id'] = event['type'] + '_' + event['date'] + '_' + event['CAU']
            event['date'] = parse(event['date'])

    def createEventsDict(self, islist):
        return ({
            'offon': [] if islist else None,
            'iops': [] if islist else None,
            'reserved_instance': [] if islist else None,
            'destroy_ebs_volume': [] if islist else None
        })

    def getSortedDatesWithCostsCAU(self, costDataItems):
        self.costUnitsByDate = {}
        datesWithCAU = {}
        datesList = []
        for costItem in costDataItems:
            curDate = costItem['date'].isoformat()
            if curDate not in datesWithCAU:
                datesWithCAU[curDate] = [costItem['CAU']]
                datesList.append({'isodate': curDate, 'costItemsCAU': datesWithCAU[curDate]})
            elif costItem['CAU'] not in datesWithCAU[curDate]:
                datesWithCAU[curDate].append(costItem['CAU'])

            # Filling tagGroups
            if curDate not in self.costUnitsByDate:
                self.costUnitsByDate[curDate] = {}
            if costItem['CAU'] not in self.costUnitsByDate[curDate]:
                self.costUnitsByDate[curDate][costItem['CAU']] = {}
            self.costUnitsByDate[curDate][costItem['CAU']][costItem['tagGroup']] = costItem

        datesList.sort(key= lambda cur : parse(cur['isodate']).timestamp())
        return datesList

    def mapSortedDatesToSavingCycles(self, sortedDateItems, savingCycles):
        cyclesMap = {}
        for dateItem in sortedDateItems:
            isodate = dateItem['isodate']
            ts = parse(dateItem['isodate']).timestamp()
            cyclesMap[isodate] = {}

            for cycle in savingCycles:
                if ts >= cycle['startDate'].timestamp() and ts < cycle['endDate'].timestamp() and cycle['custodianEffective']:
                    if cycle['CAU'] not in cyclesMap[isodate]:
                        cyclesMap[isodate][cycle['CAU']] = []
                    cyclesMap[isodate][cycle['CAU']].append(cycle)
                else:
                    print("{} not after {} ({})".format(isodate, cycle['startDate'].isoformat(), 'true' if cycle['custodianEffective'] else 'false'))

        return cyclesMap


    # Création des event scopes (start date & endDate liés par un meme type d'event)
    def processEvents(self):
        eventCyclesMapping = {
            'offon': ('reStart', 'Shutdown'),
            'iops': ('increase_iops', 'decrease_iops'),
            'destroy_ebs_volume': ('destroy_ebs_volume', False),
            'reserved_instance': ('RIStart', False)
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
                            ({'startDate': cur['date'], 'custodianEffective': effectiveSavingEvent, 'id': cur['id'], 'type': cycleType, 'CAU': cur['CAU']})

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
        self.eventScopes.sort(key= lambda cur : cur['startDate'].timestamp())

    def getTheoriticalSpendTagGroups_IfCostSavingActionHadNotBeenConducted(self, CAUId, dateTime, savingCycle):
        tagGroupsList = set()
        theoricalDate = savingCycle['startDate'] - timedelta(hours=1)
        i = 0
        while theoricalDate.isoformat() not in self.costUnitsByDate:
            if i > 23:
                return tagGroupsList
            theoricalDate -= timedelta(hours=1)
            i += 1
        listCAU = self.costUnitsByDate[theoricalDate.isoformat()]
        if CAUId not in listCAU:
            return tagGroupsList
        tagGroupsDict = listCAU[CAUId]
        for tagGroup in tagGroupsDict:
            tagGroupsList.add(tagGroup)
        return tagGroupsList

    def getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted(self, CAUId, TagGroup, dateTime, savingCycle):
        if 'theoricalCost' not in savingCycle:
            savingCycle['theoricalCost'] = {}
        if TagGroup in savingCycle['theoricalCost']:
            return savingCycle['theoricalCost'][TagGroup]

        theoricalDate = savingCycle['startDate'] - timedelta(hours=1)
        i = 0
        while theoricalDate.isoformat() not in self.costUnitsByDate or \
            CAUId not in self.costUnitsByDate[theoricalDate.isoformat()] or \
            TagGroup not in self.costUnitsByDate[theoricalDate.isoformat()][CAUId]:
            if i > 23:
                print("Cannot get theorical cost of saving cycle {} at {}".format(savingCycle['type'], dateTime.isoformat()))
                return 0
            theoricalDate -= timedelta(hours=1)
            i += 1

        savingCycle['theoricalCost'][TagGroup] = self.costUnitsByDate[theoricalDate.isoformat()][CAUId][TagGroup]['cost']
        return savingCycle['theoricalCost'][TagGroup]

    # Renvoie chaque event ses metrics de savings pour chaque date ayant un cost
    # Nécessite l'appel préalable de processEvents (création des eventscopes)
    # TODO: -> event scope on off doit sarreter en fin de week
    def getSavings(self):
        # sortie de la fonction : 
        result = { 
            "savings": [],
            "costs": [],
            "savingCycles": [],
            "eventNames": []
        }
        # Also sets self.costUnitsByDate : 
        sortedDates = self.getSortedDatesWithCostsCAU(self.costs)
        self.savingCyclesByDate = self.mapSortedDatesToSavingCycles(sortedDates, self.eventScopes)
        # print("saving cycles by date = " + str(self.savingCyclesByDate))
        # print("costUnits by date / CAU / tagGroup : " + str(self.costUnitsByDate))
        lastSavingCycles = {} # contains saving cycles of last datetime, by CAU

        for dateTime in sortedDates:
            isodate = dateTime['isodate']
            print(">{}".format(isodate))
            for CAU in dateTime['costItemsCAU']: # every CAU containing cost items at this datetime
                print("\n\t{}".format(CAU))
                currentSavingCycles = self.savingCyclesByDate[isodate][CAU] if CAU in self.savingCyclesByDate[isodate] else []
                theoricalSavings = {} # savings sorted by cycleId then tagGroup
                tagGroupsByCycle = {} # tagGroups sorted by cycleId
                print("\tsavingcycles : {}".format(currentSavingCycles))
                for savingCycle in currentSavingCycles:
                    print("\t\t{}".format(savingCycle['id']))
                    if 'theoricalCost' not in savingCycle:
                        result['savingCycles'].append(savingCycle)
                        savingCycle['saving'] = 0
                    if savingCycle['type'] not in result['eventNames']:
                        result['eventNames'].append(savingCycle['type'])
                    theoricalSavings[savingCycle['id']] = {}
                    # list of tagGroups at this CAU + datetime, whether being OR would have been being effective without savingCycle action
                    tagGroupsByCycle[savingCycle['id']] = self.getTheoriticalSpendTagGroups_IfCostSavingActionHadNotBeenConducted(CAU, parse(isodate), savingCycle)
                    print("\t\tfound taggroups : {}".format(str(tagGroupsByCycle[savingCycle['id']])))
                    for tagGroup in tagGroupsByCycle[savingCycle['id']]:
                        print("\t\t\t{}".format(tagGroup))
                        # real cost for given CAU + tagGroup juste before savingCycle beginning
                        theoricalCost = self.getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted(CAU, tagGroup, parse(isodate), savingCycle)
                        if tagGroup in self.costUnitsByDate[isodate][CAU]: # TagGroup toujours présent à l'heure actuelle
                            costAndUsageDataItem = self.costUnitsByDate[isodate][CAU][tagGroup]
                            costAndUsageDataItem['saving'] = 0
                            theoricalSavings[savingCycle['id']][tagGroup] = theoricalCost - costAndUsageDataItem['cost']
                        else: # TagGroup disparu : son dernier cout = 100% bénéfice
                            theoricalSavings[savingCycle['id']][tagGroup] = theoricalCost

                # every theorical savings calculated ; just subtract them
                i = 0
                nbCycles = len(currentSavingCycles)
                for savingCycle in currentSavingCycles:
                    for tagGroup in tagGroupsByCycle[savingCycle['id']]:
                        saving = theoricalSavings[savingCycle['id']][tagGroup]
                        if i < (nbCycles - 1) and tagGroup in theoricalSavings[currentSavingCycles[(i + 1)]['id']]:
                            saving -= theoricalSavings[currentSavingCycles[(i + 1)]['id']][tagGroup]
                        costAndUsageDataItem = self.costUnitsByDate[isodate][CAU][tagGroup] if tagGroup in self.costUnitsByDate[isodate][CAU] else False
                        if costAndUsageDataItem:
                            costAndUsageDataItem['saving'] += saving
                        savingCycle['saving'] += saving
                        print("Saving of {} at {} by {}".format(saving, isodate, savingCycle['type']))
                        result['savings'].append({
                            'CAU': CAU,
                            'tagGroup': tagGroup,
                            'date': isodate,
                            'type': savingCycle['type'],
                            'saving': saving,
                            'savingCycleId': savingCycle['id'], # On associe l'id du saving cycle au costItem
                        })
                    i += 1

                # On ajoute chaque coût traité pour l'heure donnée au résultat
                addedTagGroups = {}
                for CAU in self.costUnitsByDate[isodate]:
                    for tagGroup in self.costUnitsByDate[isodate][CAU]:
                        costAndUsageDataItem = self.costUnitsByDate[isodate][CAU][tagGroup] if tagGroup in self.costUnitsByDate[isodate][CAU] else False
                        if costAndUsageDataItem and (tagGroup + isodate) not in addedTagGroups:
                            result['costs'].append({
                                'CAU': costAndUsageDataItem['CAU'],
                                'tagGroup': costAndUsageDataItem['tagGroup'],
                                'date': isodate,
                                'cost': costAndUsageDataItem['cost'],
                                'matchingEventTypes': False if not currentSavingCycles else True,
                                'saving': costAndUsageDataItem['saving'] if 'saving' in costAndUsageDataItem else 0
                            })
                            print("#> cost at {} = {}".format(isodate, costAndUsageDataItem['cost']))
                            addedTagGroups[(tagGroup + isodate)] = True

                # calculation end ; store current saving cycles
                lastSavingCycles[CAU] = currentSavingCycles

        result['savingCycles']  = list(map(lambda scope: ({
            'startDate': scope['startDate'].isoformat(),
            'endDate': scope['endDate'].isoformat(),
            'type': scope['type'],
            'CAU': scope['CAU'],
            'saving': scope['saving'],
            'id': scope['id']
        }), result['savingCycles']))
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
