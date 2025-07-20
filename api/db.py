import os
from dotenv import load_dotenv
import boto3

# Load environment variables from .env file
load_dotenv()

# Check if AWS_REGION is loaded
aws_region = os.getenv("AWS_REGION")
if aws_region is None:
    print("Error: AWS_REGION is not loaded properly!")
else:
    print(f"AWS_REGION is loaded correctly: {aws_region}")

# Check if other environment variables are loaded
user_table_name = os.getenv("USER_TABLE_NAME")
rating_table_name = os.getenv("RATING_TABLE_NAME")
report_table_name = os.getenv("REPORT_TABLE_NAME")
task_table_name = os.getenv("TASK_TABLE_NAME")

# Print loaded values to debug
print(f"USER_TABLE_NAME: {user_table_name}")
print(f"RATING_TABLE_NAME: {rating_table_name}")
print(f"REPORT_TABLE_NAME: {report_table_name}")
print(f"TASK_TABLE_NAME: {task_table_name}")

# DynamoDB resource initialization
dynamodb = boto3.resource("dynamodb", region_name=aws_region)

# Test DynamoDB connection by listing tables
try:
    tables = dynamodb.tables.all()
    print("Tables in DynamoDB:", list(tables))  # Print all tables in DynamoDB
except Exception as e:
    print(f"Error connecting to DynamoDB: {e}")

# S3 client initialization
s3 = boto3.client("s3", region_name=aws_region)

# Tables initialization
user_table = dynamodb.Table(user_table_name)
rating_table = dynamodb.Table(rating_table_name)
report_table = dynamodb.Table(report_table_name)
task_table = dynamodb.Table(task_table_name)
