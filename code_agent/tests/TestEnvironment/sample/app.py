class OllamaClient:
    def __init__(self, model):
        self.model = model

    def send_message(self, messages):
        from ollama import chat
        response = chat(model=self.model, messages=messages)
        return response.content

# Usage
client = OllamaClient('llama3.1')
response = client.send_message([
    {'role': 'user', 'content': 'Why is the sky blue?'}
])
print(response)