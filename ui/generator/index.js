import angular from 'angular';
                
const app = angular.module('app', []);

angular.module('app')
.controller('MyCtrl', function ($scope, $rootScope) {
	$scope.form = {
        startDate: '',
        startCost: 70,
        duration: 30,

        dateRI: false,
        reductionRI: 50,

        dateOnOff: false,
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
        .on('changeDate', function(e) {
            $scope.form.startDate = moment(e.target.value, "MM/DD/YYYY").toISOString()
        })

        $('#dateRI').datepicker()
        .on('changeDate', function(e) {
            $scope.form.dateRI = moment(e.target.value, "MM/DD/YYYY").toISOString()
        })

        $('#dateOnOff').datepicker()
        .on('changeDate', function(e) {
            $scope.form.dateOnOff = moment(e.target.value, "MM/DD/YYYY").toISOString()
        })
    }

    $scope.onValid = (e) => {
        console.log('generate with ' + JSON.stringify($scope.form))
        var form = {...$scope.form}
        form.reductionRI /= 100.0
        form.reductionWeekOnOff = ((form.reductionWeekOnOff - 100.0) / 100.0)
        form.reductionWeekEndOnOff = ((form.reductionWeekEndOnOff - 100.0) / 100.0)

        var stats = generate(form)
        console.log('COSTS '  + JSON.stringify(stats))
        $scope.form.costJson = JSON.stringify(stats.costs)
        $scope.form.eventJson = JSON.stringify(stats.events)
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
    var riAppliedCost = curCost;
    var onOffStatus = true

    var cur = moment(form.startDate)
    var endDate = moment(cur).add(form.duration, 'days')
    while (!cur.isSame(endDate)) {
        if (form.dateRI && cur.isSameOrAfter(form.dateRI) && !riApplied) {
            riApplied = true;
            console.log('Application RI le ' + cur.format('DD MMMM YYYY') + ' : prix ' + curCost + ' -> ' + (curCost * form.reductionRI))
            curCost = riAppliedCost = (curCost * form.reductionRI)
            addEvent(cur, 'reserved_instance');
        }

        if (form.dateOnOff && cur.isSameOrAfter(form.dateOnOff)) {
            var curShutdownDate = moment(cur).hour(form.timeOffWeek)
            var day = cur.day();
            var isWeekend = (day == 6) || (day == 0) || (day == 5 && cur.isSameOrAfter(curShutdownDate));

            if (isWeekend) {
                if (onOffStatus) { // En weekend alors que c'est On : on éteint
                    addEvent(cur, 'shutdown_instance')
                    curCost *= form.reductionWeekEndOnOff
                    onOffStatus = false
                    console.log('week end le ' + cur.format('DD MMMM YYYY H:mm') + ' : prix = ' + curCost + " ( " + form.reductionWeekEndOnOff  + " )")
                }
            } else {
                var curStartDate = moment(cur).hour(form.timeOnWeek)
                if (!onOffStatus && cur.isBetween(curStartDate, curShutdownDate)) { // En semaine et en journée : doit etre allumé
                    console.log(cur.format('DD MMMM YYYY H:mm') + ' est entre '  +curStartDate.format('DD MMMM YYYY H:mm') + ' // ' + curShutdownDate.format('DD MMMM YYYY H:mm'))
                    addEvent(cur, 'start_instance')
                    curCost = riAppliedCost
                    onOffStatus = true
                } else if (onOffStatus) { // En semaine et hors journée : faut éteindre
                    addEvent(cur, 'shutdown_instance')
                    curCost *= form.reductionWeekOnOff
                    onOffStatus = false
                }
            }
        }

        costs.push({
            costs: {ec2: curCost},
            date: cur.toISOString()
        })

        cur.add(1, 'hours')
    }

    return {
        costs: costs,
        events: events
    }
}