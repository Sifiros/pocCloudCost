#!/usr/bin/python3

import sys
import os
import json
from dateutil.parser import *
from datetime import *

checklist = ['2017-08-12T08:00:00']
cycleschecklist = False#['reserved_instance']
tagschecklist = False
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

    def getSortedDatesWithCostsCAU(self, costDataItems):
        self.costUnitsByDate = {}
        datesWithCAU = {}
        datesList = []
        listCAU = []

        for costItem in costDataItems:
            curDate = costItem['date'].isoformat()
            if costItem['CAU'] not in listCAU:
                listCAU.append(costItem['CAU'])
            if curDate not in datesWithCAU:
                datesWithCAU[curDate] = list(listCAU)#[costItem['CAU']]
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

    def getTheoriticalTagGroups_IfCostSavingActionHadNotBeenConducted(self, CAUId, dateTime, savingCycle):
        tagGroupsList = set()
        theoricalDate = savingCycle['startDate'] - timedelta(hours=1)
        i = 0
        while theoricalDate.isoformat() not in self.costUnitsByDate:
            if i > 23:
                return tagGroupsList
            theoricalDate -= timedelta(hours=1)
            i += 1
        # current tag groups
        listCAU = self.costUnitsByDate[dateTime.isoformat()]
        if CAUId in listCAU:
            tagGroupsDict = listCAU[CAUId]
            for tagGroup in tagGroupsDict:
                tagGroupsList.add(tagGroup)
        # Add saving cycle tag groups
        if 'theoricalCost' in savingCycle:
            for tagGroup in savingCycle['theoricalCost']:
                tagGroupsList.add(tagGroup)
        # look for finished tag groups
        listCAU = self.costUnitsByDate[theoricalDate.isoformat()]
        if CAUId not in listCAU:
            return tagGroupsList
        tagGroupsDict = listCAU[CAUId]
        for tagGroup in tagGroupsDict:
            tagGroupsList.add(tagGroup)
        return tagGroupsList

    def projectTheoricalCost(self, baseCost, shiftHours):
        return (baseCost * 1 ** shiftHours)

    def getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted(self, CAUId, TagGroup, dateTime, savingCycle, i):
        if 'theoricalCost' not in savingCycle:
            savingCycle['theoricalCost'] = {}
        if TagGroup in savingCycle['theoricalCost']:
            # Synchronize (check if current cycle parent just ended)
            lastDate = (dateTime - timedelta(hours = 1)).isoformat()
            if CAUId in self.savingCyclesByDate[lastDate] and len(self.savingCyclesByDate[lastDate][CAUId]) > (i + 1) and \
                self.savingCyclesByDate[lastDate][CAUId][(i + 1)] == savingCycle and \
                (i == 0 or self.savingCyclesByDate[dateTime.isoformat()][CAUId][(i - 1)] != self.savingCyclesByDate[lastDate][CAUId][i]):
                savingCycle['theoricalCost'][TagGroup] = self.savingCyclesByDate[lastDate][CAUId][i]['theoricalCost'][TagGroup]
            return savingCycle['theoricalCost'][TagGroup]

        curSavingCyclesStack = self.savingCyclesByDate[dateTime.isoformat()][CAUId]
        i2 = i
        # check for each cycle theorical cost in the stack, starting by current one. Theorical cost = Cost one hour before the cycle start date
        theoricalCostUnit = False
        while (i2 >= 0):
            curCycle = curSavingCyclesStack[i2]
            theoricalDate = curCycle['startDate'] - timedelta(hours=1)
            # Check if this date is inside any ended event at dateTime. If so, just call recursively on the event in question
            lastCycle = self.savingCyclesByDate[theoricalDate.isoformat()][CAUId][-1] if CAUId in self.savingCyclesByDate[theoricalDate.isoformat()] else False
            if lastCycle is not False and lastCycle['endDate'].timestamp() <= dateTime.timestamp():
                curCycle['theoricalCost'][TagGroup] = self.getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted(CAUId, TagGroup, lastCycle['startDate'], lastCycle, len(self.savingCyclesByDate[theoricalDate.isoformat()][CAUId]) - 1)
                return curCycle['theoricalCost'][TagGroup]

            if theoricalDate.isoformat() in self.costUnitsByDate and CAUId in self.costUnitsByDate[theoricalDate.isoformat()] and \
                TagGroup in self.costUnitsByDate[theoricalDate.isoformat()][CAUId]: # specified taggroup has a cost 1h before start date
                theoricalCostUnit = self.costUnitsByDate[theoricalDate.isoformat()][CAUId][TagGroup]['cost']
                break
            i2 -= 1

        if theoricalCostUnit is False:
            savingCycle['theoricalCost'][TagGroup] = lambda date: 0
            return savingCycle['theoricalCost'][TagGroup]
        savingCycle['theoricalCost'][TagGroup] = lambda date : theoricalCostUnit if date is False else self.projectTheoricalCost(theoricalCostUnit, ((date - savingCycle['startDate']).seconds) / 3600)
        return savingCycle['theoricalCost'][TagGroup]

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
        lastSavingCycles = {} # contains saving cycles of last datetime, by CAU
        for dateTime in sortedDates:
            isodate = dateTime['isodate']
            for CAU in dateTime['costItemsCAU']: # every CAU containing cost items at this datetime
                currentSavingCycles = self.savingCyclesByDate[isodate][CAU] if CAU in self.savingCyclesByDate[isodate] else []
                theoricalSavings = {} # savings sorted by cycleId then tagGroup
                tagGroupsByCycle = {} # tagGroups sorted by cycleId
                savingCycleNb = 0
                for savingCycle in currentSavingCycles:
                    if 'theoricalCost' not in savingCycle:
                        result['savingCycles'].append(savingCycle)
                        savingCycle['saving'] = 0
                    if savingCycle['type'] not in result['eventNames']:
                        result['eventNames'].append(savingCycle['type'])
                    theoricalSavings[savingCycle['id']] = {}
                    # list of tagGroups at this CAU + datetime, whether being OR would have been being effective without savingCycle action
                    tagGroupsByCycle[savingCycle['id']] = self.getTheoriticalTagGroups_IfCostSavingActionHadNotBeenConducted(CAU, parse(isodate), savingCycle)
                    for tagGroup in tagGroupsByCycle[savingCycle['id']]:
                        # real cost for given CAU + tagGroup juste before savingCycle beginning
                        theoricalCost = self.getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted(CAU, tagGroup, parse(isodate), savingCycle, savingCycleNb)
                        theoricalCost = theoricalCost(parse(isodate))
                        if CAU in self.costUnitsByDate[isodate] and tagGroup in self.costUnitsByDate[isodate][CAU]: # TagGroup toujours présent à l'heure actuelle
                            costAndUsageDataItem = self.costUnitsByDate[isodate][CAU][tagGroup]
                            costAndUsageDataItem['saving'] = 0
                            theoricalSavings[savingCycle['id']][tagGroup] = theoricalCost - costAndUsageDataItem['cost']
                        else: # TagGroup disparu : son dernier cout = 100% bénéfice
                            theoricalSavings[savingCycle['id']][tagGroup] = theoricalCost

                    savingCycleNb += 1
                # every theorical savings calculated ; just subtract them
                i = 0
                nbCycles = len(currentSavingCycles)
                for savingCycle in currentSavingCycles:
                    for tagGroup in tagGroupsByCycle[savingCycle['id']]:
                        saving = theoricalSavings[savingCycle['id']][tagGroup]
                        if i < (nbCycles - 1) and tagGroup in theoricalSavings[currentSavingCycles[(i + 1)]['id']]:
                            saving -= theoricalSavings[currentSavingCycles[(i + 1)]['id']][tagGroup]
                        if CAU in self.costUnitsByDate[isodate]:
                            costAndUsageDataItem = self.costUnitsByDate[isodate][CAU][tagGroup] if tagGroup in self.costUnitsByDate[isodate][CAU] else False
                            if costAndUsageDataItem:
                                costAndUsageDataItem['saving'] += saving
                        savingCycle['saving'] += saving
                        # if isodate in checklist and (cycleschecklist is False or savingCycle['type'] in cycleschecklist) and \
                        #     (tagschecklist is False or tagGroup in tagschecklist):
                        #     print("#>#>#> SAVING  AT " + isodate + " FOR " + tagGroup + " is  :"  + str(saving) + " / " + savingCycle['type'])
                        result['savings'].append({
                            'CAU': CAU,
                            'tagGroup': tagGroup,
                            'date': isodate,
                            'type': savingCycle['type'],
                            'saving': saving,
                            'savingCycleId': savingCycle['id'], # On associe l'id du saving cycle au costItem
                        })
                    i += 1
                # calculation end ; store current saving cycles
                lastSavingCycles[CAU] = currentSavingCycles
            # FIN boucle sur chaque CAU pour l'heure actuelle. On ajoute au résultat chaque coût traité
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
                        addedTagGroups[(tagGroup + isodate)] = True

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
