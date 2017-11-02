#!/usr/bin/python3

import sys
import os

class GainCalculator():
    costs = []
    events = []

    currentCycleGain = 0
    lowCycleCost = 0
    expCycleCost = 0
    currentScope = []

    def __init__(self, costs, events):
        self.costs = costs
        self.events = events

    def printCurrentScope(self):
        for x in self.costs:
            print(x)

    def getEventContext():
        pass

    def getCostScope():
        pass

    def calcRI():
        pass

    def calcIOPS():
        pass

    def calcStopStart():
        pass
