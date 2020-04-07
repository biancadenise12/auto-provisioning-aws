# Automatic Provisioning of AWS Resources Using AWS API Gateway, AWS Lambda, and Terraform
![api-terraform](/images/api-terraform.png)
## Create Lambda Function
* Author from scratch
* Function Name: auto-provision
* Runtime: Python 3.8
  * It's important to know the [Python Runtime](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html) version to know the execution environment that lambda provides you.
  * It is also important to take note of the available [Environment Variables](https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html). There are reserved variables that you can not use and who knows if you might need some of them during the development of your function.
  * When your function is invoked, Lambda attempts to re-use the execution environment from a previous invocation if one is available. This saves time preparing the execution environment, and allows you to save resources like database connections and temporary files in the execution context to avoid creating them every time your function runs.
    * We can re-use the Terraform installation (in the function: it will search for terraform file if it exist or not) - **FOR IMPROVEMENT**
* Execution Role: Create a new role with basic Lambda permissions

## Attach policy to auto-provision-role (created role)
* AmazonEC2FullAccess

## Create new user
* Username: auto-provision-user
* Access Type: Programmatic Access
* Attach Policy: AmazonEC2FullAccess

## Input Environment Variables in Lambda Function
* ACCESS_KEY = Access key ID (auto-provision user)
* SECRET_KEY = Secret access key (auto-provision user)

## Adjust Function's Settings
* Memory(MB) - set to maximum (adjust after the initial run, find the summary of execution in CloudWatch)
* Timeout (sec) - set it to 1min (maximum timeout of API Gateway is 29sec-just mentioning)

## Create API
1. Build REST API
2. API Name: auto-provision
3. Endpoint: Regional
4. Create Method (POST and GET):
     * Integration Type: Lambda Function
     * Enable Use Lambda Proxy integration
     * Lambda Function: auto-provision
5. Enable CORS
6. Deploy API
7. Copy Invoke URL (Example: https://gejnpptgl5.execute-api.ap-southeast-1.amazonaws.com/prod)

## Create terraform.py
This code includes all defined functions related to terraform such as:
* **install()** - Installing terraform
* **awsprovider()** - Getting terraform access (IAM User) from environment variables defined in lambda and generating AWS provider details
* **terraformapply()** - Executes terraform init and terraform apply
* **cleanup()** - Deleting everything inside `/tmp`
```python
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
```

## Create main.py
This code includes the main logic of the functions to be called depending on the data thrown to the API Gateway.
* First, it reads the event, decodes the event body, then saving it as `/tmp/input.json`
* Then, it installs terraform inside /tmp since this is the only directory with write permission
* It has the logic that checks the provider that will be used. For now, the functions available are for AWS only. This will be improved to make the application cloud-agnostic.
* Finally, it deletes everything inside `/tmp` for consistency. Can be **IMPROVED** by reusing terraform installations to shorten execution time
* Note: Modify Handler when using this function directly:
  * `main.main` (*Format: filename.functionname*)
```python
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
```

## Create awsresources.tf
```terraform
locals {
  json_input = jsondecode(file("input.json"))
}

resource "aws_instance" "server" {
  instance_type = local.json_input.details.size
  ami = local.json_input.details.image
  count = local.json_input.details.number_of_resource
}
```
## Use Postman to test the API
* Copy the API URL
* Use GET or POST Request
![api-error](/images/api-error.PNG)

## Conclusion
* Using the above json body, it is now successfully provisioning an ec2 instance. It shows `504 Bad Gateway` or the error message `Endpoint Request Timeout` because the maximum and the default timeout of the API is 29000 ms or 29 sec while the function's duration is 33300 ms or 33.3 seconds.
* We can resolve this by creating another Lambda function where it acknowledges the request and the response is instantly sent. Just point the API Gateway trigger to this new function which invokes the original function (auto-provision).
    ```python
    import json
    import boto3

    def lambda_handler(event, context):
    
    lambda_client = boto3.client('lambda')
    lambda_client.invoke(FunctionName='auto-provision', InvocationType='Event', Payload = json.dumps(event))
    
    return {
        'statusCode': 200,
        'body': json.dumps('Resources are being created.')
    }
    ```
* The CloudWatch log summary below shows that the maximum memory used is only 330 MB. With this data, we can adjust the memory settings of the function.
    ```log
    REPORT RequestId: 2cddbaca-7927-4812-9d78-7c6edd619679	Duration: 33277.17 ms	Billed Duration: 33300 ms	Memory Size: 3008 MB	Max Memory Used: 330 MB	Init Duration: 251.30 ms
    ```
    
## Errors Encountered
`A conflicting conditional operation is currently in progress against this resource. Please try again.` - This error showed in AWS S3 Console when trying to "rename" a bucket or "move to a new region". Rename/move here means that I deleted the original bucket from us-east-1, then immediately created another bucket in ap-southeast-2 with the same bucket name. Expectedly, the attempt to reuse the bucket name should succeed after about an hour or so. 

