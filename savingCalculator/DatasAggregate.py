# coding=utf8
from dateutil.parser import *
from datetime import *

def totimestamp(dt, epoch=datetime(1970,1,1)):
    td = dt - epoch
    return (td.microseconds + (td.seconds + td.days * 86400) * 10**6) / 10**6 

class SavingCycle ():
    datas = None
    startDate = None
    endDate = None
    eventType = ""
    CAUId = ""
    saving = 0
    theoricalCosts = {}
    depth = -1
    _id = 0
    activeCycle = True

    def __init__(self, datas, startDate, eventType, CAUId, cycleId, activeCycle, endDate = None):
        self.datas = datas
        self.startDate = startDate
        self.endDate = endDate
        self.eventType = eventType
        self.CAUId = CAUId
        self._id = cycleId
        self.activeCycle = activeCycle
        self.theoricalCosts = {}
        self.saving = 0
        self.depth = -1

    def getTheoricalCost(self, tagGroup, date):
        timeShift = (((date - self.startDate).seconds) / 3600) + 1
        theoricalCost = self.datas.getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted(self.CAUId, tagGroup, date, self, self.depth)
        return theoricalCost * (1 ** timeShift)

# Provided raw costs & events, aggregate those datas in differents structures required by the calculator algorithm
# Turns costs into self.sortedDatesWithCAU + sef.costUnitsByDate
# Turns events into self.savingCycles + self.savingCyclesByDate
# Method getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted calculates theorical cost of a given savingCycle + tagGroup + dateTime 
# Theorical cost of a resource (defined by its tagGroup) = Cost of this tagGroup 1h before the given savingCycle beginning
class DatasAggregate():
    costs = []
    events = []
    endPeriodDate = datetime.now()

    # List of SavingCycles instantiated from input events
    savingCycles = []
    # sorted date with corresponding costs CAU
    sortedDatesWithCAU = []
    # costUnits sorted by date, CAU then tagGroup
    costUnitsByDate = False
    # savingCycles sorted by date then CAU
    savingCyclesByDate = False

    # Can be called from calculator with json read from csv OR from unit tests with calculator output
    def __init__(self, costs, events=None):
        self.savingCycles = []
        self.sortedDatesWithCAU = []
        self.costUnitsByDate = False
        self.savingCyclesByDate = False 
        self.costs = costs
        for cost in self.costs:
            cost['date'] = parse(cost['date'])
            if totimestamp(cost['date']) > totimestamp(self.endPeriodDate):
                self.endPeriodDate = cost['date']
        self.costs.sort(key= lambda cur : totimestamp(cur['date']))

        if events != None:
            self.events = events
            for event in self.events:
                event['id'] = event['type'] + '_' + event['date'] + '_' + event['CAU']
                event['date'] = parse(event['date'])
            self.processEvents()

    def setSavingCycles(self, savingCycles):
        self.savingCycles = savingCycles
        self.savingCycles.sort(key= lambda cur : totimestamp(cur.startDate))

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
                    if cycleId in curScopes and curScopes[cycleId].activeCycle == effectiveSavingEvent:
                        print("Events processing error : can't handle 2 successive start or end without corresponding start event")
                        break

                    start = curScopes[cycleId] if cycleId in curScopes else \
                            SavingCycle(self, cur['date'], cycleType, cur['CAU'], cur['id'], effectiveSavingEvent)

                    if cycleId in curScopes or cycleEvents[1] == False: # we're on an end or one shot event : prepare new scope
                        newScope = start
                        newScope.endDate = cur['date'] if cycleEvents[1] != False else self.endPeriodDate
                        if cycleId in curScopes:
                            del curScopes[cycleId]
                    # store new cycle start event (not in one shot case)
                    if cycleEvents[1] != False:
                        if newScope: # we just ended a cycle : update startDate / endDate
                            start = SavingCycle(self, newScope.endDate, newScope.eventType, newScope.CAUId, cur['id'], (not newScope.activeCycle))
                        curScopes[cycleId] = start
                    break
            if newScope:
                self.savingCycles.append(newScope)

        for scopeId in curScopes:
            unfinishedEvent = curScopes[scopeId]
            unfinishedEvent.endDate = self.endPeriodDate
            self.savingCycles.append(unfinishedEvent)
        self.savingCycles.sort(key= lambda cur : totimestamp(cur.startDate))

    # sets self.sortedDatesWithCAU AND self.costUnitsByDate
    def mapCostsToSortedDatesWithCAU(self, costDataItems):
        self.costUnitsByDate = {}
        self.sortedDatesWithCAU = []
        datesWithCAU = {}
        listCAU = []

        for costItem in costDataItems:
            curDate = costItem['date'].isoformat()
            if costItem['CAU'] not in listCAU:
                listCAU.append(costItem['CAU'])
            if curDate not in datesWithCAU:
                datesWithCAU[curDate] = list(listCAU)
                self.sortedDatesWithCAU.append({'isodate': curDate, 'costItemsCAU': datesWithCAU[curDate]})
            elif costItem['CAU'] not in datesWithCAU[curDate]:
                datesWithCAU[curDate].append(costItem['CAU'])

            # Filling tagGroups
            if curDate not in self.costUnitsByDate:
                self.costUnitsByDate[curDate] = {}
            if costItem['CAU'] not in self.costUnitsByDate[curDate]:
                self.costUnitsByDate[curDate][costItem['CAU']] = {}
            self.costUnitsByDate[curDate][costItem['CAU']][costItem['tagGroup']] = costItem

        self.sortedDatesWithCAU.sort(key= lambda cur : totimestamp(parse(cur['isodate'])))
        return self.sortedDatesWithCAU

    # sets self.savingCyclesByDate
    def mapSortedDatesToSavingCycles(self, sortedDateItems, savingCycles):
        cyclesMap = {}
        for dateItem in sortedDateItems:
            isodate = dateItem['isodate']
            ts = totimestamp(parse(dateItem['isodate']))
            cyclesMap[isodate] = {}

            for cycle in savingCycles:
                if ts >= totimestamp(cycle.startDate) and ts < totimestamp(cycle.endDate) and cycle.activeCycle:
                    if cycle.CAUId not in cyclesMap[isodate]:
                        cyclesMap[isodate][cycle.CAUId] = []
                    cyclesMap[isodate][cycle.CAUId].append(cycle)

        self.savingCyclesByDate = cyclesMap
        return self.savingCyclesByDate

    def getSavingCyclesAt(self, isodate, CAUId):
        if isodate not in self.savingCyclesByDate or CAUId not in self.savingCyclesByDate[isodate]:
            return []
        return self.savingCyclesByDate[isodate][CAUId]

    def aggregate(self):
        self.mapCostsToSortedDatesWithCAU(self.costs)
        self.mapSortedDatesToSavingCycles(self.sortedDatesWithCAU, self.savingCycles) 

    def getTheoriticalSpend_IfCostSavingActionHadNotBeenConducted(self, CAUId, TagGroup, dateTime, savingCycle, i):
        curSavingCycles = self.getSavingCyclesAt(dateTime.isoformat(), CAUId)
        # theorical cost already stored ; simply return it
        if TagGroup in savingCycle.theoricalCosts: 
            lastDate = (dateTime - timedelta(hours = 1)).isoformat()
            lastCycles = self.getSavingCyclesAt(lastDate, CAUId)
            # If current cycle's parent ended on last date ; synchronize cur theorical cost with those of ended cycle
            if len(lastCycles) > (i + 1) and lastCycles[(i + 1)] == savingCycle and TagGroup in lastCycles[i].theoricalCosts:
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
            if lastCycle is not False and totimestamp(lastCycle.endDate) <= totimestamp(dateTime):
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