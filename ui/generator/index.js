import angular from 'angular';

const app = angular.module('app', []);

angular.module('app')
.controller('MyCtrl', function ($scope, $rootScope) {
	$scope.form = {
        startDate: '',
        startCost: 70,
        duration: 30,

        dateRI: false,
        endDateRI: false,
        reductionRI: 50,

        dateIops: false,
        endDateIops: false,
        reductionIops: 15,
        timeIncreaseIops: 9,
        timeDecreaseIops: 21,

        dateOnOff: false,
        endDateOnOff: false,
        reductionWeekOnOff: 30,
        reductionWeekEndOnOff: 70,
        timeOnWeek: 9,
        timeOffWeek: 21,

        costJson: '',
        eventJson: ''
    }

    if (!$scope.init) {
        $scope.init = true;
        $('#period').datepicker()
        .on('changeDate', function(e) { $scope.form.startDate = moment(e.target.value, "MM/DD/YYYY").toISOString() })

        $('#dateRI').datepicker()
        .on('changeDate', function(e) { $scope.form.dateRI = moment(e.target.value, "MM/DD/YYYY").toISOString() })

        $('#endDateRI').datepicker()
        .on('changeDate', function(e) { $scope.form.endDateRI = moment(e.target.value, "MM/DD/YYYY").toISOString() })
        $('#dateOnOff').datepicker()
        .on('changeDate', function(e) { $scope.form.dateOnOff = moment(e.target.value, "MM/DD/YYYY").toISOString() })

        $('#endDateOnOff').datepicker()
        .on('changeDate', function(e) { $scope.form.endDateOnOff = moment(e.target.value, "MM/DD/YYYY").toISOString() })

        $('#dateIncreaseIops').datepicker()
        .on('changeDate', function(e) { $scope.form.dateIops = moment(e.target.value, "MM/DD/YYYY").toISOString() })

        $('#dateDecreaseIops').datepicker()
        .on('changeDate', function(e) { $scope.form.endDateIops = moment(e.target.value, "MM/DD/YYYY").toISOString() })
    }

    $scope.onValid = (e) => {
        console.log('generate with ' + JSON.stringify($scope.form))
        var form = {...$scope.form}
        form.reductionRI /= 100.0
        form.reductionIops /= 100.0
        form.reductionWeekOnOff = form.reductionWeekOnOff / 100.0
        form.reductionWeekEndOnOff = form.reductionWeekEndOnOff / 100.0

        var stats = generate(form)
        console.log('COSTS '  + JSON.stringify(stats))
        $scope.form.costJson = JSON.stringify(stats.costs)
        $scope.form.eventJson = JSON.stringify(stats.events)
    }

		$scope.downloadObjectAsJson = function (exportObj, exportName){
		  console.log("entering download");
		  if (exportObj && exportName) {
		    var dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportObj));
		    var downloadAnchorNode = document.createElement('a');
		    downloadAnchorNode.setAttribute("href",     dataStr);
		    downloadAnchorNode.setAttribute("download", exportName + ".json");
		    downloadAnchorNode.click();
		    downloadAnchorNode.remove();
		  }
		}

});

function generate(form) {
    var events = []
    var costs = []
    function addEvent(date, type) {
        events.push({
            date: moment(date),
            type,
            affectedResources: {ec2: true}
        })
    }

    var curCost = form.startCost
    var riApplied = false
    var onOffStatus = true
    var iopsStatus = false
    var savings = {
        onoff: 0,
        iops: 0
    }

    var cur = moment(form.startDate)
    var endDate = moment(cur).add(form.duration, 'days')
    while (!cur.isSame(endDate)) {
        if (form.dateRI && cur.isSameOrAfter(form.dateRI) && !riApplied) {
            riApplied = true;
            curCost = (curCost * form.reductionRI)
            addEvent(cur, 'reserved_instance');
        }
        savings = {
            "onoff" : 0,
            "iops": 0
        }

        // OffOn
        if (form.dateOnOff && cur.isSameOrAfter(form.dateOnOff) &&
            (!form.endDateOnOff || cur.isBefore(form.endDateOnOff))) {
            var curShutdownDate = moment(cur).hour(form.timeOffWeek)
            var day = cur.day();
            var isWeekend = (day == 6) || (day == 0) || (day == 5 && cur.isSameOrAfter(curShutdownDate));

            if (isWeekend) {
                if (onOffStatus) { // En weekend alors que c'est On : on éteint
                    addEvent(cur, 'shutdown_instance')
                    onOffStatus = false
                }
                savings.onoff = (curCost * form.reductionWeekEndOnOff)
            } else {
                var curStartDate = moment(cur).hour(form.timeOnWeek)
                if (cur.isBetween(curStartDate, curShutdownDate)) { // En semaine et en journée : doit etre allumé
                    if (!onOffStatus) {
                        addEvent(cur, 'start_instance')
                        onOffStatus = true
                    }
                    savings.onoff = 0
                } else if (!cur.isBetween(curStartDate, curShutdownDate)) { // En semaine et hors journée : faut éteindre
                    if (onOffStatus) {
                        addEvent(cur, 'shutdown_instance')
                        onOffStatus = false
                    }
                    savings.onoff = (curCost * form.reductionWeekOnOff)
                }
            }
        }

        // IOPS
        if (form.dateIops && cur.isSameOrAfter(form.dateIops) &&
            (!form.endDateIops || cur.isBefore(form.endDateIops))) {
            var curDecreaseDate = moment(cur).hour(form.timeDecreaseIops)
            var curIncreaseDate = moment(cur).hour(form.timeIncreaseIops)
            var day = cur.day();

            if (cur.isBetween(curIncreaseDate, curDecreaseDate)) { // En journée , on augmente les iops
                if (!iopsStatus) {
                    addEvent(cur, 'increase_iops')
                    iopsStatus = true
                }
                savings.iops = 0
            } else if (!cur.isBetween(curIncreaseDate, curDecreaseDate)) { // Hors journée, on diminue les iops
                if (iopsStatus) {
                    addEvent(cur, 'decrease_iops')
                    iopsStatus = false
                }
                savings.iops = (curCost * form.reductionIops)
            }
        }

        costs.push({
            costs: {ec2: (curCost - savings.onoff - savings.iops)},
            date: cur.toISOString()
        })
        cur.add(1, 'hours')
    }

    return {
        costs: costs,
        events: events
    }
}
