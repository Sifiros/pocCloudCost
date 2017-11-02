#!/usr/bin/python3

import sys
import os

class GainCalculator():

    currentCycleGain = 0
    lowCycleCost = 0
    expCycleCost = 0
    currentScope = []

    def printCurrentScope():
        currentScope = getCloudCost()
        for x in currentScope:
            print(x)

    def getEventContext();
        pass

    def getCostScope():
        pass

    def getCloudCost():
        return [{
		date: 'utc1',
		costs: {
			s3: '25',
			ec2: ...
		}
	}, {
		date: 'utc2',
		costs: {
			s3: '20',
			ec2: ...
		}
	}]

    def calcRI():
        pass

    def calcIOPS():
        pass

    def calcStopStart():
        pass
