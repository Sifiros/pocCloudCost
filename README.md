# pocCloudCost
Teevity cloud cost poc


# TeevityAPI

## GetCostDatas
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
	}
]


## GetEvents
Available events :
	- start_instance
	- shutdown_instance
	- modify_ebs_iops
	- modify_ebs_size

return [{
		date: 'heure1',
		events: {
			shutdown_instance: {
				resource: 'ec2'
				instanceid: '...'
			}
		}
	}, {
		date: 'heure1',
		events: {
			modify_ebs_iops: {
				volumeid: '...'
			}
		}
	}
]