from openai import OpenAI

client = OpenAI(
    base_url='http://192.168.170.76:11434/v1/',
    api_key='ollama',
)

chat_completion = client.chat.completions.create(
    messages=[{
        'role': 'user',
        'content': 'Say this is a test',
    }],
    model='qwen2.5:7b-instruct',
)

print(chat_completion)