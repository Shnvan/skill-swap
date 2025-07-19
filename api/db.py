import os
import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# DynamoDB resource
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION"))

# S3 client
s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION"))

# Tables
user_table = dynamodb.Table(os.getenv("USER_TABLE_NAME"))
rating_table = dynamodb.Table(os.getenv("RATING_TABLE_NAME"))
report_table = dynamodb.Table(os.getenv("REPORT_TABLE_NAME"))
task_table = dynamodb.Table(os.getenv("TASK_TABLE_NAME"))

