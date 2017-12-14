import csv

class TeevityAPI:
	eventsFilepath = ''
	costsFilepath = ''

	def __init__(self, costsFilepath = './api/savings.csv', eventsFilepath = './api/events.csv'):
		self.eventsFilepath = eventsFilepath
		self.costsFilepath = costsFilepath

	def GetCostDatas(self):
		rows = self.queryCsv(['Date', 'CAU', 'Account', 'Region', 'Product', 'Operation', 'UsageType', 'Cost'], self.costsFilepath)
		rows = list(map(self.mapTeevityCost, rows))
		return rows

	def mapTeevityCost(self, cost):
		return {
			'date': cost['Date'],#parse(cost['Date']).isoformat(),
			'cost': float(cost['Cost']),
			'CAU': cost['CAU'],
			'tagGroup': cost['Account'] + cost['Region'] + cost['Product'] + cost['Operation'] + cost['UsageType']
		}

	def GetEvents(self):
		rows = self.queryCsv(['Date', 'CAU', 'Type'], self.eventsFilepath)
		rows = list(map(self.mapTeevityEvent, rows))
		return rows

	def mapTeevityEvent(self, event):
		# productNameMapping = {
		# 	'Amazon Elastic Compute Cloud': 'ec2'
		# }
		# resourceType = productNameMapping[cost['ProductName']] if cost['ProductName'] in productNameMapping else cost['ProductName']
		return {
			'date': event['Date'],#parse(event['Date']).isoformat(),
			'CAU': event['CAU'],
			'type': event['Type'],
		}

	def queryCsv(self, columns, file):
		rows = []
		try:
			file = open(file, 'r')
			reader = csv.DictReader(file)
		except:
			raise NameError("Unable to parse specified csv file " + file)

		for row in reader:
			curDict = {}
			for column in columns:
				curDict[column] = row[column]
			rows.append(dict(curDict))

		file.close()
		return rows