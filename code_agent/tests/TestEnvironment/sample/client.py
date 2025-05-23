from mcp.client import Client

client = Client("localhost", 8000)

response = client.call("greet", "Alice")
print(response)
