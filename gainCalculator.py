#!/usr/bin/python3

import sys
import os
import copy
import json
from dateutil.parser import *
from datetime import *

checklist = ['2017-08-10T12:00:00']
cycleschecklist = False#['reserved_instance']
tagschecklist = False
class GainCalculator():
    class SavingCycle ():
        gainCalculator = None
        startDate = None
        endDate = None
        eventType = ""
        CAUId = ""
        saving = 0
        theoricalCosts = {}
        depth = -1
        _id = 0
        effectiveCycle = True

        def __init__(self, gainCalculator, startDate, eventType, CAUId, cycleId, effectiveCycle):
            self.gainCalculator = gainCalculator
            self.startDate = startDate
            self.eventType = eventType
            self.CAUId = CAUId
            self._id = cycleId
            self.effectiveCycle = effectiveCycle
            self.theoricalCosts = {}
            self.saving = 0
            self.depth = -1

        def getTheoricalCost(self, tagGroup, date):
            timeShift = (((date - self.startDate).seconds) / 3600) + 1
            theoricalCost = self.gainCalculator.getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted(self.CAUId, tagGroup, date, self, self.depth)
            return theoricalCost * (1 ** timeShift)

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
                datesWithCAU[curDate] = list(listCAU)
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
                if ts >= cycle.startDate.timestamp() and ts < cycle.endDate.timestamp() and cycle.effectiveCycle:
                    if cycle.CAUId not in cyclesMap[isodate]:
                        cyclesMap[isodate][cycle.CAUId] = []
                    cyclesMap[isodate][cycle.CAUId].append(cycle)

        self.savingCyclesByDate = cyclesMap
        return self.savingCyclesByDate

    def getSavingCyclesAt(self, isodate, CAUId):
        if isodate not in self.savingCyclesByDate or CAUId not in self.savingCyclesByDate[isodate]:
            return []
        return self.savingCyclesByDate[isodate][CAUId]

    # Création des event scopes (start date & endDate liés par un meme type d'event)
    def processEvents(self):
        eventCyclesMapping = { # each cycle type associated with its start / end event name. False end event = one shot cycle
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
                    if cycleId in curScopes and curScopes[cycleId].effectiveCycle == effectiveSavingEvent:
                        print("Events processing error : can't handle 2 successive start or end without corresponding start event")
                        break

                    start = curScopes[cycleId] if cycleId in curScopes else \
                            self.SavingCycle(self, cur['date'], cycleType, cur['CAU'], cur['id'], effectiveSavingEvent)

                    if cycleId in curScopes or cycleEvents[1] == False: # we're on an end or one shot event : prepare new scope
                        newScope = start
                        newScope.endDate = cur['date'] if cycleEvents[1] != False else self.endPeriodDate
                        if cycleId in curScopes:
                            del curScopes[cycleId]
                    # store new cycle start event (not in one shot case)
                    if cycleEvents[1] != False:
                        if newScope: # we just ended a cycle : update startDate / endDate
                            start = self.SavingCycle(self, newScope.endDate, newScope.eventType, newScope.CAUId, cur['id'], (not newScope.effectiveCycle))
                        curScopes[cycleId] = start
                    break
            if newScope:
                self.eventScopes.append(newScope)

        for scopeId in curScopes:
            unfinishedEvent = curScopes[scopeId]
            unfinishedEvent.endDate = self.endPeriodDate
            self.eventScopes.append(unfinishedEvent)
        self.eventScopes.sort(key= lambda cur : cur.startDate.timestamp())

    def getTheoriticalTagGroups_IfCostSavingActionHadNotBeenConducted(self, CAUId, dateTime, savingCycle):
        tagGroupsList = set()
        theoricalDate = savingCycle.startDate - timedelta(hours=1)
        i = 0
        # In case of missing datas ... Is it rly worth ? 
        while theoricalDate.isoformat() not in self.costUnitsByDate:
            if i > 23:
                return tagGroupsList
            theoricalDate -= timedelta(hours=1)
            i += 1
        # retrieve tagGroups at this exact dateTime
        listCAU = self.costUnitsByDate[dateTime.isoformat()]
        if CAUId in listCAU:
            tagGroupsDict = listCAU[CAUId]
            for tagGroup in tagGroupsDict:
                tagGroupsList.add(tagGroup)
        # tagGroups already linked to the savingCycle (but not necessarily there atm)
        for tagGroup in savingCycle.theoricalCosts:
            tagGroupsList.add(tagGroup)
        # look for finished tag groups
        listCAU = self.costUnitsByDate[theoricalDate.isoformat()]
        if CAUId not in listCAU:
            return tagGroupsList
        tagGroupsDict = listCAU[CAUId]
        for tagGroup in tagGroupsDict:
            tagGroupsList.add(tagGroup)
        return tagGroupsList

    def getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted(self, CAUId, TagGroup, dateTime, savingCycle, i):
        curSavingCycles = self.getSavingCyclesAt(dateTime.isoformat(), CAUId)
        # theorical cost already stored ; simply return it
        if TagGroup in savingCycle.theoricalCosts: 
            lastDate = (dateTime - timedelta(hours = 1)).isoformat()
            lastCycles = self.getSavingCyclesAt(lastDate, CAUId)
            # If current cycle's parent ended on last date ; synchronize cur theorical cost with those of ended cycle
            if len(lastCycles) > (i + 1) and lastCycles[(i + 1)] == savingCycle:
                savingCycle.theoricalCosts[TagGroup] = lastCycles[i].theoricalCosts[TagGroup]
            return savingCycle.theoricalCosts[TagGroup]

        i2 = i
        # check for each cycle theorical cost in the stack, starting by current one. Theorical cost = Cost one hour before the cycle start date
        theoricalCostUnit = False
        while (i2 >= 0):
            curCycle = curSavingCycles[i2]
            theoricalDate = curCycle.startDate - timedelta(hours=1)
            theoricalDateSavingCycles = self.getSavingCyclesAt(theoricalDate.isoformat(), CAUId)
            # Check if this date is inside any ended event at dateTime. If so, just call recursively on the event in question
            lastCycle = theoricalDateSavingCycles[-1] if len(theoricalDateSavingCycles) > 0 else False
            if lastCycle is not False and lastCycle.endDate.timestamp() <= dateTime.timestamp():
                curCycle.theoricalCosts[TagGroup] = self.getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted(CAUId, TagGroup, lastCycle.startDate, lastCycle, len(theoricalDateSavingCycles) - 1)
                return curCycle.theoricalCosts[TagGroup]

            # If asked tagGroup has a cost 1h before cur cycle start date ; get it 
            if theoricalDate.isoformat() in self.costUnitsByDate and CAUId in self.costUnitsByDate[theoricalDate.isoformat()] and \
                TagGroup in self.costUnitsByDate[theoricalDate.isoformat()][CAUId]: 
                theoricalCostUnit = self.costUnitsByDate[theoricalDate.isoformat()][CAUId][TagGroup]['cost']
                break
            i2 -= 1

        if theoricalCostUnit is False:
            savingCycle.theoricalCosts[TagGroup] = 0
            return savingCycle.theoricalCosts[TagGroup]
        savingCycle.theoricalCosts[TagGroup] = theoricalCostUnit
        return savingCycle.theoricalCosts[TagGroup]

    def getSavings(self):
        self.processEvents()
        # sortie de la fonction getSavings : 
        result = { "savings": [], "costs": [], "savingCycles": [], "eventNames": [] }
        sortedDates = self.getSortedDatesWithCostsCAU(self.costs) # also sets self.costUnitsByDate
        self.mapSortedDatesToSavingCycles(sortedDates, self.eventScopes) # sets self.savingCyclesByDate

        for dateTime in sortedDates: # loop over each dates sorted
            isodate = dateTime['isodate']
            for CAU in dateTime['costItemsCAU']: # every CAU containing cost items at this datetime
                currentSavingCycles = self.getSavingCyclesAt(isodate, CAU)
                theoricalSavings = {} # savings sorted by cycleId then tagGroup
                tagGroupsByCycle = {} # tagGroups sorted by cycleId
                savingCycleNb = 0

                for savingCycle in currentSavingCycles:
                    if savingCycle.depth == -1:
                        result['savingCycles'].append(savingCycle)
                    savingCycle.depth = savingCycleNb
                    if savingCycle.eventType not in result['eventNames']:
                        result['eventNames'].append(savingCycle.eventType) # Just for the sake of output process
                    theoricalSavings[savingCycle._id] = {}
                    # list of tagGroups at this CAU + datetime, whether being OR would have been being effective without savingCycle action
                    tagGroupsByCycle[savingCycle._id] = self.getTheoriticalTagGroups_IfCostSavingActionHadNotBeenConducted(CAU, parse(isodate), savingCycle)
                    for tagGroup in tagGroupsByCycle[savingCycle._id]:
                        # real cost for given CAU + tagGroup juste before savingCycle beginning
                        theoricalCost = savingCycle.getTheoricalCost(tagGroup, parse(isodate))
                        # if isodate in checklist and (cycleschecklist is False or savingCycle.eventType in cycleschecklist) and \
                        #     (tagschecklist is False or tagGroup in tagschecklist):
                        #     print("{} depth {} (effective {}) has theorical cost of {} for {}".format(savingCycle.eventType, savingCycle.depth, savingCycle.effectiveCycle, theoricalCost, tagGroup))
                        if CAU in self.costUnitsByDate[isodate] and tagGroup in self.costUnitsByDate[isodate][CAU]: # TagGroup toujours présent à l'heure actuelle
                            costAndUsageDataItem = self.costUnitsByDate[isodate][CAU][tagGroup]
                            costAndUsageDataItem['saving'] = 0
                            theoricalSavings[savingCycle._id][tagGroup] = theoricalCost - costAndUsageDataItem['cost']
                        else: # TagGroup disparu : son dernier cout = 100% bénéfice
                            theoricalSavings[savingCycle._id][tagGroup] = theoricalCost

                    savingCycleNb += 1
                # every theorical savings calculated ; just subtract them
                i = 0
                nbCycles = len(currentSavingCycles)
                for savingCycle in currentSavingCycles:
                    for tagGroup in tagGroupsByCycle[savingCycle._id]:
                        saving = theoricalSavings[savingCycle._id][tagGroup]
                        if i < (nbCycles - 1) and tagGroup in theoricalSavings[currentSavingCycles[(i + 1)]._id]:
                            saving -= theoricalSavings[currentSavingCycles[(i + 1)]._id][tagGroup]
                        if CAU in self.costUnitsByDate[isodate]:
                            costAndUsageDataItem = self.costUnitsByDate[isodate][CAU][tagGroup] if tagGroup in self.costUnitsByDate[isodate][CAU] else False
                            if costAndUsageDataItem:
                                costAndUsageDataItem['saving'] += saving
                        savingCycle.saving += saving
                        # if isodate in checklist and (cycleschecklist is False or savingCycle.eventType in cycleschecklist) and \
                        #     (tagschecklist is False or tagGroup in tagschecklist):
                        #     print("#>#>#> SAVING  AT " + isodate + " FOR " + tagGroup + " is  :"  + str(saving) + " / " + savingCycle.eventType)
                        result['savings'].append({
                            'CAU': CAU,
                            'tagGroup': tagGroup,
                            'date': isodate,
                            'type': savingCycle.eventType,
                            'saving': saving,
                            'savingCycleId': savingCycle._id, # On associe l'id du saving cycle au costItem
                        })
                    i += 1
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
            'startDate': scope.startDate.isoformat(),
            'endDate': scope.endDate.isoformat(),
            'type': scope.eventType,
            'CAU': scope.CAUId,
            'saving': scope.saving,
            'id': scope._id
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
            print("startDate: {}, endDate: {}, type: {}, CAU: {}, effective: {}".format(cur.startDate, cur.endDate, cur.eventType, cur.CAUId, cur.effectiveCycle))
        print('')
