import json
import boto3
import os
import shutil
from zipfile import ZipFile

def install():
    # Download Terraform from S3 bucket
    os.chdir('/tmp')
    s3 = boto3.client('s3')
    s3.download_file('terraform-plugins-bucket-ap-southeast-1', 'terraform_0.12.24_linux_amd64.zip', 'terraform.zip')
    
    # Extract and remove zip file
    with ZipFile('terraform.zip', 'r') as zipObj:
        zipObj.extractall()
    os.remove('terraform.zip')
    
    # Make terraform executable
    os.system('chmod +x terraform')
    os.system('./terraform -version')
    
    os.chdir('/var/task')
    
def awsprovider():
    # Get environment variables from lambda
    access_key = os.environ['ACCESS_KEY']
    secret_key = os.environ['SECRET_KEY']
    region = os.environ['AWS_REGION']
    
    # Generate provider.tf.json for AWS
    provider_dict = {"provider": {"aws": {"access_key": access_key,"profile": "default","region": region,"secret_key": secret_key,"version": "~\u003e 2.53.0"}}}
    provider_body = json.dumps(provider_dict)
    provider_file = open("/tmp/provider.tf.json", "w")
    provider_file.write(provider_body)
    provider_file.close()
    
    os.chdir('/var/task')
    
def terraformapply():
    os.chdir('/tmp')
    os.system('./terraform version')
    # os.system('./terraform init -get-plugins=false -plugin-dir=/tmp/.terraform/plugins')
    # thinking about saving the plugin in S3 to have a fixed plugin version tested compatible with terraform version
    os.system('./terraform init -lock=false')
    os.system('./terraform apply -auto-approve')
    
def cleanup():
    # To delete everything inside /tmp
    # Can be improved by not doing cleanup for reusing to be able to shorten execution time of succeeding runs
    for filename in os.listdir('/tmp'):
        file_path = os.path.join('/tmp', filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
                print("File ", file_path, " was deleted")
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
                print("Folder ", file_path, "  deleted.")
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))