import requests

# 测试修复后的API端点
try:
    response = requests.get("http://localhost:5002/api/user-templates/list")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
