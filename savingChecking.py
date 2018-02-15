#!/usr/bin/python2.7

##
## Sum up saving results, look for inconsistencies
## Needs "./calcSavings" as input (run ./calcSavings | ./savingChecking.py)
##

from savingCalculator.DatasAggregate import DatasAggregate, SavingCycle
import json
from decimal import *
from datetime import datetime
from dateutil.parser import *
import sys
import unittest

def totimestamp(dt, epoch=datetime(1970,1,1)):
    td = dt - epoch
    return (td.microseconds + (td.seconds + td.days * 86400) * 10**6) / 10**6 

class SavingChecking():
    # DatasAggregate
    datas = None
    savings = []

    def __init__(self, algoOutput):
        self.savings = algoOutput['raw']['savings']
        self.datas = DatasAggregate(algoOutput['raw']['costs'])
        self.datas.setSavingCycles(list(map(lambda cur:
            SavingCycle(self.datas, parse(cur['startDate']), cur['type'], cur['CAU'], cur['id'], True, parse(cur['endDate']))
        , algoOutput['raw']['savingCycles'])))
        self.datas.aggregate()

    def run(self):
        summaryCosts = self.summarizeCosts(self.datas.costs)
        summarySavings = self.summarizeSavings(self.savings)

        print(str(len(self.datas.costs)) +" cost metrics loaded between "+ summaryCosts['start'].strftime("%Y-%m-%d %H:%M") + 
                " and  "+ summaryCosts['end'].strftime("%Y-%m-%d %H:%M") + " (" + str(summaryCosts['duration']) + " days) across " + str(len(summaryCosts['CAU'])) + " CAU : " + str(summaryCosts['CAU']))
        print("Total real cost during this period : %d" % summaryCosts['totalCost'])
        print("Total savings : %d (%.2f%% of costs across %d CAU : %s)" %
            (summarySavings['total'], (summarySavings['total'] / summaryCosts['totalCost']) * 100,
            len(summarySavings['CAU']), str(summarySavings['CAU']))
        )
        # Print saving by event type
        for event in summarySavings['totalByEvent']:
            print("\t%s = %d (%.2f%% of savings)" % (
                event, summarySavings['totalByEvent'][event],
                (summarySavings['totalByEvent'][event] / summarySavings['total']) * 100
            ))
        print("")
        nbErrors = self.lookForInconsistencies(summarySavings)
        if nbErrors == 0:
            print("PASSED:\tEvery sum of real cost with saving is equal to corresponding unoptimized cost.")
            print("> No inconsistency found !")
        else:
            print("\n\nFAILURE:\t%d (against %d datetimes) inconsistencies found." % (nbErrors, len(self.datas.sortedDatesWithCAU)))
        return (nbErrors)

    def lookForInconsistencies(self, summarySavings):
        nbErrors = 0
        theoricalCosts = {} # By cycle id then tagGroup
        getcontext().prec = 5
        for item in self.datas.sortedDatesWithCAU:
            isodate = item['isodate']
            totalCost = Decimal(0)
            totalSaving = Decimal(0)
            totalTheoricalCost = Decimal(0)

            savings = summarySavings['byDates'][isodate] if isodate in summarySavings['byDates'] else {}

            costs = self.datas.costUnitsByDate[isodate]
            for CAU in costs:
                for tagGroup in costs[CAU]:
                    savingCycles = self.datas.savingCyclesByDate[isodate][CAU] if isodate in self.datas.savingCyclesByDate and CAU in self.datas.savingCyclesByDate[isodate] else []
                    if len(savingCycles) == 0:
                        totalTheoricalCost += Decimal(costs[CAU][tagGroup]['cost'])
                        theoricalCosts[tagGroup] = costs[CAU][tagGroup]['cost']            
                    totalCost += Decimal(costs[CAU][tagGroup]['cost'])

            for CAU in savings:
                for tagGroup in savings[CAU]:
                    savingCycles = self.datas.savingCyclesByDate[isodate][CAU] if isodate in self.datas.savingCyclesByDate and CAU in self.datas.savingCyclesByDate[isodate] else []
                    cost = self.datas.costUnitsByDate[isodate]
                    cost = cost[CAU][tagGroup]['cost'] if CAU in cost and tagGroup in cost[CAU] else False
                    curSaving = savings[CAU][tagGroup]
                    saving = 0
                    if cost is False: # saving d'un ancien tag group
                        saving = curSaving['saving']
                        totalTheoricalCost += Decimal(saving)
                    else:
                        saving = curSaving['saving']
                        totalTheoricalCost += Decimal(theoricalCosts[tagGroup] if tagGroup in theoricalCosts else 0)

                    totalSaving += Decimal(saving)

            # Last step : check sums
            tot = totalSaving + totalCost
            theoricalTot = totalTheoricalCost
            if tot != theoricalTot:
                op = "lower" if tot < theoricalTot else "bigger"
                print("On %s, sum of real cost and calculated saving (%.2f + %.2f = %.2f) is %s than unoptimized cost (%2.f) !" %
                    (isodate, totalCost, totalSaving, tot, op, theoricalTot))
                nbErrors += 1
        return nbErrors

    def summarizeSavings(self, savings):
        allCAU = set()
        summary = {
            'byDates': {},
            'totalByEvent': {},
            'total': 0,
            'CAU': []
        }

        for saving in savings:
            # Add curent date
            if saving['date'] not in summary['byDates']:
                summary['byDates'][saving['date']] = {}
            # Add current CAU to current date
            if saving['CAU'] not in summary['byDates'][saving['date']]:
                summary['byDates'][saving['date']][saving['CAU']] = {}
            if saving['tagGroup'] not in summary['byDates'][saving['date']][saving['CAU']]:
                summary['byDates'][saving['date']][saving['CAU']][saving['tagGroup']] = saving
            else: # saving already stored for this cau/taggroup = we're on another event
                summary['byDates'][saving['date']][saving['CAU']][saving['tagGroup']]['saving'] += saving['saving']
            # Add current event type to all events
            if saving['type'] not in summary['totalByEvent']:
                summary['totalByEvent'][saving['type']] = 0

            summary['totalByEvent'][saving['type']] += saving['saving']
            summary['total'] += saving['saving']
            allCAU.add(saving['CAU'])

        summary['CAU'] = list(allCAU)
        return summary

    def summarizeCosts(self, costs):
        allCAU = set()
        summary = {
            "start": False,
            "end": False,
            "duration": False,
            "totalCost": 0,
            "CAU": []
        }
        for cost in costs:
            if (summary['start'] and totimestamp(cost['date']) < totimestamp(summary['start'])) or not summary['start']:
                summary['start'] = cost['date']
            if (summary['end'] and totimestamp(cost['date']) > totimestamp(summary['end'])) or not summary['end']:
                summary['end'] = cost['date']
            summary['totalCost'] += cost['cost']
            allCAU.add(cost['CAU'])
        
        summary['duration'] = (summary['end'] - summary['start']).days
        summary['CAU'] = list(allCAU)
        return summary


def main():
    datas = json.loads(sys.stdin.read())

    savingChecking = SavingChecking(datas)
    savingChecking.run()

if __name__ == "__main__":
    sys.exit(main())
