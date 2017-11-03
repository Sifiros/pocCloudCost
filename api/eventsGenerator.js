const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

var i = 0;
var costs = []
var events = []


rl.on('line', function(costs) {
	costs = JSON.parse(costs)
	console.log('#> ' + costs.length)
	processCost(costs[i], costs)
	i++;
});


function processCost(curCost, costs) {
	console.log('#> ' + costs.length)
	var curEvent = {date: curCost.date, type: '', affectedResources: {}}
	askEventFor(curCost.date, curCost.costs, function (event) {
		curEvent.type = event;
		curEvent.affectedResources = {}
		
		events.push(curEvent);
		if (i < costs.length)
			processCost(costs[i++], costs)
		else {
			console.log(JSON.stringify(events))
			rl.close();
		}
	})
}


function askEventFor(date, curCost, cb) {
	const resource = 'ec2'
	console.log('Évènments disponibles :\tstart_instance\tshutdown_instance\tmodify_ebs_iops\tdestroy_ebs_volume');
	rl.question('Quel evenement pour le cout de ' + curCost[resource] + " pour la ressource " + resource + " le " +  new Date(date).toLocaleString() + " ?", cb);
}