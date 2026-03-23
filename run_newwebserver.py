import boto3

ec2 = boto3.resource('ec2')

instance_list = []

for inst in ec2.instances.all():
    instance_list.append(inst)

instances = ec2.create_instances(
    ImageId='ami-02dfbd4ff395f2a1b',
    MinCount=1,
    MaxCount=1,
    InstanceType='t2.micro',
    KeyName='automated_cloud_services_assignment_one',
    UserData="#!/bin/bash\nyum update -y"
)

mainInstance = instances[0]
mainInstance.wait_until_running()
mainInstance.reload()
print(f"Instance public_ip: {mainInstance.public_ip_address}")