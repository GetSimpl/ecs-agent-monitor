import boto3

ENVIRONMENTS = ['staging', 'unicorn', 'sandbox', 'production']

NON_PRODUCTION_NOTIFICATIONS_ARN_MUMBAI = 'arn:aws:sns:ap-south-1:725827686899:non-prod-mumbai'
PRODUCTION_NOTIFICATIONS_ARN_MUMBAI = 'arn:aws:sns:ap-south-1:725827686899:production'
NON_PRODUCTION_NOTIFICATIONS_ARN_SINGAPORE = 'arn:aws:sns:ap-southeast-1:725827686899:unicorn'

NOTIFICATIONS_ARN = {
'unicorn': NON_PRODUCTION_NOTIFICATIONS_ARN_SINGAPORE,
'staging': NON_PRODUCTION_NOTIFICATIONS_ARN_MUMBAI,
'sandbox': NON_PRODUCTION_NOTIFICATIONS_ARN_MUMBAI,
'production': PRODUCTION_NOTIFICATIONS_ARN_MUMBAI
}

def alarm_name_for(ec2_instance_id):
  return "ecs_agent_alarm_"+ec2_instance_id

def get_client_for(resource, environment):
  if environment == 'unicorn':
    region = 'ap-southeast-1'
  else:
    region = 'ap-south-1'
  return boto3.session.Session(region_name=region).client(resource)

def ensure_alarm_exists(ec2_instance_id, environment, cloudwatch):
  try:
    cloudwatch.Alarm(alarm_name_for(ec2_instance_id))
  except:
    cloudwatch.put_metric_alarm(
      AlarmName=alarm_name_for(ec2_instance_id),
      ComparisonOperator='LessThanThreshold',
      EvaluationPeriods=3,
      MetricName='ECS Agent Connected',
      Namespace='ECSAgent',
      Period=60,
      Statistic='Average',
      Threshold=1.0,
      ActionsEnabled=True,
      OKActions=[
        NOTIFICATIONS_ARN[environment]
      ],
      AlarmActions=[
        NOTIFICATIONS_ARN[environment]
      ],
      AlarmDescription='Alarm whenever ECS Agent Connected drops below 1',
      Dimensions=[
        {
          'Name': 'Environment',
          'Value': environment
        },
        {
          'Name': 'InstanceID',
          'Value': ec2_instance_id
        }
      ]
    )

def check_environment(environment, ecs_client, cloudwatch):
  if environment == 'unicorn':
    cluster_name = environment + '-cluster'
  else:
    cluster_name = 'cluster-' + environment
  print "Finding instances in " + cluster_name
  resp = ecs_client.list_container_instances(
    cluster=cluster_name
  )
  instances = resp[u'containerInstanceArns']
  try:
    nxt_tok = resp[u'nextToken']
    while True:
      resp = ecs_client.list_container_instances(
        cluster=cluster_name,
        nextToken=nxt_tok
      )
      instances += resp[u'containerInstanceArns']
      nxt_tok = resp[u'nextToken']
  except KeyError:
    pass
  resp = ecs_client.describe_container_instances(
    cluster=cluster_name,
    containerInstances=instances
  )

  for inst in resp[u'containerInstances']:
    ec2_instance_id = str(inst[u'ec2InstanceId'])
    print "checking instance " + ec2_instance_id
    ensure_alarm_exists(ec2_instance_id, environment, cloudwatch)
    if inst[u'agentConnected']:
      cloudwatch.put_metric_data(
        Namespace='ECSAgent',
        MetricData=[{
          'MetricName': 'ECS Agent Connected',
          'Dimensions': [
            {
              'Name': 'Environment',
              'Value': environment
            },
            {
              'Name': 'InstanceID',
              'Value': ec2_instance_id
            }
          ],
          'Value': 1
        }]
      )
    else:
      cloudwatch.put_metric_data(
        Namespace='ECSAgent',
        MetricData=[{
          'MetricName': 'ECS Agent Connected',
          'Dimensions': [
            {
              'Name': 'Environment',
              'Value': environment
            },
            {
              'Name': 'InstanceID',
              'Value': ec2_instance_id
            }
          ],
          'Value': 0
        }]
      )

  print "finished checking " + cluster_name

def execute(event={}, context=None):
  for environment in ENVIRONMENTS:
    ecs_client = get_client_for("ecs", environment)
    cloudwatch = get_client_for("cloudwatch", environment)
    check_environment(environment, ecs_client, cloudwatch)

if __name__ == "__main__":
  execute()