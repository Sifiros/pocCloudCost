

const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

var costs = [];


function askCost() {
	var curResource = ''
	var cost = {costs: {}}
	function processDate(day) {
		day = day.split(' ');
		cost.date = new Date(2017, 11, day[0], day[1], 0).toISOString();
		curResource = ''
	}
	function processResourceName(resource) {
		curResource = resource
	}
	function processCost(cost, out) {
		out.costs[curResource] = cost
		costs.push(out)
		return true
	}

	rl.question('Day ? ("day" "hour")(none to stop) ', (date) => {
		if (date == 'none') {
			rl.close();
			generate();
			return ;
		}
		processDate(date);
		rl.question('Resource ?', res => {
			processResourceName(res);
			rl.question('Cost ?', res => processCost(res, cost) && askCost())
		})
	});

	return (true);
}

function generate() {
	console.log(JSON.stringify(costs))
}

askCost();