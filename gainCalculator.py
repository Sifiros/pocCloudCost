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
        print('-----------------------------------------------------------')
        for x in self.events:
            print(x)

    def getEventContext():
        pass

    def getCostScope(self):
        pass

    def calcRI():
        pass

    def calcIOPS(self):
        pass

    def calcStopStart(self):
        pass
