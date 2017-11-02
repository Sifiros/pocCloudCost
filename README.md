# pocCloudCost
Teevity cloud cost poc


# TeevityAPI

## GetCostDatas
```python
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
```

## GetEvents
Available events :

	- start_instance
	- shutdown_instance
	- modify_ebs_iops
	- destroy_ebs_volume

```python
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
```