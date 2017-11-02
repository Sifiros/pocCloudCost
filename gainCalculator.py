#!/usr/bin/python3

import sys
import os

class GainCalculator():

    currentCycleGain = 0
    lowCycleCost = 0
    expCycleCost = 0
    currentScope = []

    def __init__(self):
        self.currentScope = self.getCloudCost()
        self.printCurrentScope()


    def printCurrentScope(self):
        print("test")
        for x in self.currentScope:
            print(x)

    def getEventContext(self):
        pass

    def getCostScope(self):
        pass

    def getCloudCost(self):
        return  [{"costs":{"ec2":"40"},"date":"2017-12-06T09:00:00.000Z"},{"costs":{"ec2":"10"},"date":"2017-12-06T21:00:00.000Z"},{"costs":{"ec2":"40"},"date":"2017-12-07T09:00:00.000Z"},{"costs": {"ec2":"10"},"date":"2017-12-07T21:00:00.000Z"},{"costs":{"ec2":"40"},"date":"2017-12-08T09:00:00.000Z"},{"costs":{"ec2":"10"},"date":"2017-12-08T21:00:00.000Z"},{"costs":{"ec2":"40"},  "date":"2017-12-09T09:00:00.000Z"},{"costs":{"ec2":"10"},"date":"2017-12-09T21:00:00.000Z"},  {"costs":{"ec2":"40"},"date":"2017-12-10T09:00:00.000Z"},{"costs":{"ec2":"10"},"date":"2017-12-10T21:00:00.000Z"},{"costs":{"ec2":"40"},"date":"2017-12-13T09:00:00.000Z"},{"costs": {"ec2":"10"},"date":"2017-12-13T21:00:00.000Z"}]

    def calcRI(self):
        pass

    def calcIOPS(self):
        pass

    def calcStopStart(self):
        pass
