import boto3

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb', region_name='ap-northeast-1')

# Define the table name
table_name = 'sph-skill-swap'

# Scan the table to get items (users)
response = dynamodb.scan(
    TableName=table_name,
    ProjectionExpression='id, full_name, skill'
)

# Loop through each user and add missing fields
for user in response['Items']:
    user_id = user['id']['S']
    full_name = user.get('full_name', {}).get('S', '')
    skill = user.get('skill', {}).get('S', '')

    # Check if lowercase fields already exist
    if 'full_name_lc' not in user or 'skill_lc' not in user:
        # Add lowercase fields
        full_name_lc = full_name.lower()
        skill_lc = skill.lower()

        # Update DynamoDB record
        dynamodb.update_item(
            TableName=table_name,
            Key={'id': {'S': user_id}},
            UpdateExpression="SET full_name_lc = :full_name_lc, skill_lc = :skill_lc",
            ExpressionAttributeValues={
                ':full_name_lc': {'S': full_name_lc},
                ':skill_lc': {'S': skill_lc}
            }
        )
        print(f"Updated user {user_id} with lowercase fields.")
