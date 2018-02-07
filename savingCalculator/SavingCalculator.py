# coding=utf8
import sys
import os
import copy
import json
from savingCalculator.DatasAggregate import DatasAggregate
from dateutil.parser import *
from datetime import *

checklist = ['2017-08-10T12:00:00']
cycleschecklist = False#['reserved_instance']
tagschecklist = False
class SavingCalculator():
    # DatasAggregate instance. 
    datas = None

    def __init__(self, costs, events):
        self.datas = DatasAggregate(costs, events)
        self.datas.aggregate()

    def getTheoriticalTagGroups_IfCostSavingActionHadNotBeenConducted(self, CAUId, dateTime, savingCycle):
        tagGroupsList = set()
        theoricalDate = savingCycle.startDate - timedelta(hours=1)
        i = 0
        # In case of missing datas ... Is it rly worth ? 
        while theoricalDate.isoformat() not in self.datas.costUnitsByDate:
            if i > 23:
                return tagGroupsList
            theoricalDate -= timedelta(hours=1)
            i += 1
        # retrieve tagGroups at this exact dateTime
        listCAU = self.datas.costUnitsByDate[dateTime.isoformat()]
        if CAUId in listCAU:
            tagGroupsDict = listCAU[CAUId]
            for tagGroup in tagGroupsDict:
                tagGroupsList.add(tagGroup)
        # tagGroups already linked to the savingCycle (but not necessarily there atm)
        for tagGroup in savingCycle.theoricalCosts:
            tagGroupsList.add(tagGroup)
        # look for finished tag groups
        listCAU = self.datas.costUnitsByDate[theoricalDate.isoformat()]
        if CAUId not in listCAU:
            return tagGroupsList
        tagGroupsDict = listCAU[CAUId]
        for tagGroup in tagGroupsDict:
            tagGroupsList.add(tagGroup)
        return tagGroupsList


    def getSavings(self):
        # sortie de la fonction getSavings : 
        result = { "savings": [], "costs": [], "savingCycles": [], "eventNames": [], 'dates': [] }

        for dateTime in self.datas.sortedDatesWithCAU: # loop over each sorted dates
            isodate = dateTime['isodate']
            result['dates'].append(isodate)
            for CAU in dateTime['costItemsCAU']: # every CAU containing cost items at this datetime
                currentSavingCycles = self.datas.getSavingCyclesAt(isodate, CAU)
                theoricalSavings = {} # theorical savings group by cycleId then tagGroup (theoricalSavings[cycleId][tagGroup] = int)
                tagGroupsByCycle = {} # tagGroups group by cycleId
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
                        #     print("{} depth {} (effective {}) has theorical cost of {} for {}".format(savingCycle.eventType, savingCycle.depth, savingCycle.activeCycle, theoricalCost, tagGroup))
                        if CAU in self.datas.costUnitsByDate[isodate] and tagGroup in self.datas.costUnitsByDate[isodate][CAU]: # TagGroup toujours présent à l'heure actuelle
                            costAndUsageDataItem = self.datas.costUnitsByDate[isodate][CAU][tagGroup]
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
                        if CAU in self.datas.costUnitsByDate[isodate]:
                            costAndUsageDataItem = self.datas.costUnitsByDate[isodate][CAU][tagGroup] if tagGroup in self.datas.costUnitsByDate[isodate][CAU] else False
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
                            'depth': i
                        })
                    i += 1
            # FIN boucle sur chaque CAU pour l'heure actuelle. On ajoute au résultat chaque coût traité
            addedTagGroups = {}
            for CAU in self.datas.costUnitsByDate[isodate]:
                for tagGroup in self.datas.costUnitsByDate[isodate][CAU]:
                    costAndUsageDataItem = self.datas.costUnitsByDate[isodate][CAU][tagGroup] if tagGroup in self.datas.costUnitsByDate[isodate][CAU] else False
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
        return result

    def storeToFile(self, data, path):
        with open(path, 'w') as fileToWrite:
            fileToWrite.write('datas = ' + json.dumps(data))
        fileToWrite.close()
