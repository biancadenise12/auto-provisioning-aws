import json
import boto3
import os
import terraform

def main(event, context):
    print(event)
    input_data = json.loads(event['body'])
    
    # convert into json and write in /tmp/input.json:
    input_data_str = json.dumps(input_data)
    input_data_file = open("/tmp/input.json", "w")
    input_data_file.write(input_data_str)
    input_data_file.close()
    
    terraform.install()
    
    if (input_data["provider"] == "aws"):
        os.system('cp /var/task/awsresources.tf /tmp/')
        terraform.awsprovider()
        terraform.terraformapply()
    elif (input_data["provider"] == "azure"):
        print("Azure")
    elif (input_data["provider"] == "gcp"):
        print("Google Cloud")
    
    os.chdir('/tmp')
    terraform.cleanup()