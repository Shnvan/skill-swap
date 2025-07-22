from api.db import user_table

def check_user(user_id):
    response = user_table.get_item(Key={"id": user_id})
    print(f"Fetched item for {user_id}:")
    print(response)

# Replace with both IDs to test
check_user("test-user-123")
check_user("b95688b0-2642-4d13-84fc-e28cec6225e9")