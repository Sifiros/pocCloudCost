function TeevityChart(blockId, title, datasets) {
	this.disabledDatasets = []
	var conf = prepareDatasets(datasets);
	this.datasets = conf.datasets
	this.lines = conf.lines
	this.config = prepareChartConfig(title, this.datasets)
	this.chart = initChart(blockId, this.config)

	this.addNewDataset = function(dataset) {
		if (!Array.isArray(dataset))
			dataset = [dataset]
		var conf = prepareDatasets(dataset);
		Array.prototype.push.apply(this.datasets, conf.datasets);
		Array.prototype.push.apply(this.lines, conf.lines);
		this.toggleDataset()
	}

	this.setDatasetPrices = function(datasetLabel, prices) {
		this.addMetric(prices.map(mapMetricToData), datasetLabel);
	}

	this.addMetric = function(metric, datasetLabel) {
		for (var dataset of this.datasets) {
			if (dataset.label == datasetLabel) {
				if (!Array.isArray(metric))
					dataset.data.push(metric)
				else
					Array.prototype.push.apply(dataset.data, metric)
				return true;
			}
		}
		return false
	}

	this.toggleDataset = function(datasetLabel) {
		if (datasetLabel) {
			var idx = this.disabledDatasets.indexOf(datasetLabel)
			if (idx != -1)
				this.disabledDatasets.splice(idx, 1);
			else
				this.disabledDatasets.push(datasetLabel);
		}

		this.chart.destroy();
		this.config = prepareChartConfig(title, this.datasets, this.disabledDatasets, this.lines)
		this.chart = initChart(blockId, this.config);
		this.refresh();
	}

	this.refresh = function() {
		this.chart.update();
	}
}


/*
 * Chart init functions
 */
function initChart(blockId, config) {
	var ctx = document.getElementById(blockId).getContext("2d");
	var myLine = new Chart(ctx, config);

	return myLine;
}

function prepareDatasets(datasetConfig) {
    function randomColor(opacity) {
        function randomColorFactor() {
            return Math.round(Math.random() * 255);
        }
        return 'rgba(' + randomColorFactor() + ',' + randomColorFactor() + ',' + randomColorFactor() + ',' + (opacity || '.3') + ')';
    }
	var datasets = [];
	var lines = [];
	for (dataset of datasetConfig) {
		const borderColor = dataset.borderColor || randomColor(0.4)
		const backgroundColor = dataset.backgroundColor || randomColor(0.6)

		datasets.push({
			label: dataset.label,
			borderColor: borderColor,
			backgroundColor: backgroundColor,
			data: (dataset.data ? dataset.data.map(mapMetricToData) : []),
			fill: typeof dataset.fill != 'undefined'  ? dataset.fill : false
		});
	}

	return ({
		datasets: datasets,
		lines: lines
	})
}

function mapMetricToData(metric) {
	return ({
		x: moment(metric.date).toDate(),
		y: metric.value
	})
}

function prepareChartConfig(chartTitle, allDatasets, excludeDatasets = [], lines = []) {
	var datasets = allDatasets.filter(function(cur) {
		return !excludeDatasets.some(function(exc) {
			return exc == cur.label
		})
	});
	return ({
		type: 'line',
		data: {
			datasets: datasets
		},
		options: {
			responsive: true,
			title:{
				display:true,
				text: chartTitle
			},
			scales: {
				xAxes: [{
					type: "time",
					display: true,
					scaleLabel: {
						display: true,
						labelString: 'Date'
					}
				}],
				yAxes: [{
					display: true,
					scaleLabel: {
						display: true,
						labelString: 'Saving',
					}, ticks: {max: 45}
					// stacked: true
				}]
			},
		    "horizontalLine": lines
		}
	})
}
