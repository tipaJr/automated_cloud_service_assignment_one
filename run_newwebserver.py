import subprocess
import time
import webbrowser
import boto3
from botocore.exceptions import ClientError
import logging

ec2 = boto3.resource('ec2')
s3 = boto3.client('s3')
s3_resource = boto3.resource('s3')

# https://docs.aws.amazon.com/boto3/latest/guide/s3-example-creating-buckets.html
def create_bucket(bucket_name, region='us-east-1'):
    try:
        bucket_config = {}
        s3_client = boto3.client('s3', region_name=region)
        if region != 'us-east-1':
            bucket_config['CreateBucketConfiguration'] = {'LocationConstraint': region}

        s3_client.create_bucket(Bucket=bucket_name, **bucket_config)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def html_script(instance_id, availability_zone):
    return f"""
    <html>
    <head><title>Automated Cloud Services Assignment 1</title></head>
    <body>
    <h1>Welcome to Eugene Tipas Web Server</h1>
    <p>Instance ID: {instance_id}</p>
    <p>Availability Zone: {availability_zone}</p>
    <img src="image_cloud_services_assignment.jpeg" alt="Uploaded Image" width="200">
    </body>
    </html>
    """

def cleanup_function(ec2_instance_object, s3_object):

    # aws boto 3 docs
    print("Initiating clean up")

    ec2_instance_object.terminate()
    ec2_instance_object.wait_until_terminated()
    print("✅ ec2 instance successfully terminated.")

    s3_object.objects.all().delete()
    s3_object.delete()
    print("✅ s3 bucket successfully deleted.")

    print("\n==================================================================================================")
    print("✨ cleanup function ran successfully, ec2 instances and buckets were deleted ✨")
    print("====================================================================================================")

print("\n creating EC2 Instance")
print(" -> locating AMI and configuring instance details")

instances = ec2.create_instances(
    ImageId='ami-02dfbd4ff395f2a1b',
    MinCount=1,
    MaxCount=1,
    InstanceType='t2.micro',
    KeyName='automated_cloud_services_assignment_one',
    SecurityGroupIds=['sg-0d053a60c4d1db66f'],
    IamInstanceProfile={'Name': 'EC2-S3-IAM-Role'},
    UserData="#!/bin/bash\nyum update -y"
)

mainInstance = instances[0]
print(f" -> instance created (ID: {mainInstance.id}). waiting for it to enter the 'running' state")

# https://docs.aws.amazon.com/boto3/latest/reference/services/ec2/instance/wait_until_running.html
mainInstance.wait_until_running()
mainInstance.reload()
print("✅ ec2 Instance is now running")

bucket_name = f"eugene-tipa-{mainInstance.id}"
print("\nsetting up S3 Bucket and Assets")
print(f" creating bucket: {bucket_name}")
create_bucket(bucket_name=bucket_name)

print(" -> Creating index.html locally")
# https://discuss.python.org/t/general-question-using-python-html-file-in-local-folder/88230
with open("index.html", "w") as f:
    f.write(html_script(instance_id=mainInstance.id, availability_zone=mainInstance.placement["AvailabilityZone"]))

print(" -> uploading index.html and image to S3")
s3.upload_file("index.html", bucket_name, "index.html")
s3.upload_file("image_cloud_services_assignment.jpeg", bucket_name, "image_cloud_services_assignment.jpeg")
print("✅ s3 setup complete")

key_file_path = "automated_cloud_services_assignment_one.pem"

print("\n waiting for eC2 SSH service to initialize...")
time.sleep(60)
print("\n ✅ SSH service is ready")

print("\n configuring remote web server")
check_script = """#!/usr/bin/python3
import subprocess

def check_server():
    try:
     cmd = 'ps -A | grep httpd'
     subprocess.run(cmd, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
     print("success: web server is up and running")
    except subprocess.CalledProcessError:
     print("error: web server failed")

if __name__ == '__main__':
    check_server()
"""
print(" -> Creating check_webserver.py locally")
with open("check_webserver.py", "w") as f:
    f.write(check_script)

scp_command = f"scp -i {key_file_path} -o StrictHostKeyChecking=no check_webserver.py ec2-user@{mainInstance.public_ip_address}:."
print(f"triggering command: \n{scp_command}")
try:
    subprocess.run(scp_command, shell=True, timeout=90, check=True)
    print("✅ script uploaded successfully.")
except subprocess.TimeoutExpired:
    print("❌ error with the command above")

linux_commands = f"""
sudo yum install -y httpd
sudo systemctl start httpd
sudo systemctl enable httpd
sudo aws s3 cp s3://{bucket_name}/index.html /var/www/html/
sudo aws s3 cp s3://{bucket_name}/image_cloud_services_assignment.jpeg /var/www/html/
chmod 700 check_webserver.py
python3 check_webserver.py
"""

ssh_command = f"ssh -t -i {key_file_path} -o StrictHostKeyChecking=no ec2-user@{mainInstance.public_ip_address} '{linux_commands}'"
print(f"triggering ssh command: \n{ssh_command}")
try:
    subprocess.run(ssh_command, shell=True, timeout=90, check=True)
    print("✅ apache installed successfully and downloaded s3 files")
except subprocess.TimeoutExpired:
    print("❌ error with the command above")

website_url = f"http://{mainInstance.public_ip_address}"
print("\nOpening web browser to verify deployment")
webbrowser.open(website_url)

print("✅ DEPLOYMENT SUCCESSFUL ✅\n\n")

print("\n====================================================================================================================================================================================\n")
print(f"the web server is currently running. You can view it in your browser or at this url: {website_url}.")
print("when you are finished, type 'cleanup' and press Enter to delete the ec2 and s3 resources.")
print("\n====================================================================================================================================================================================")

user_input = input("\ntype 'cleanup' to terminate or any other key to leave running: ")

if user_input.strip().lower() == 'cleanup':
    cleanup_function(mainInstance, s3_resource.Bucket(bucket_name))
else:
    print("exiting: the ec2 instance and s3 bucket were left running.")
