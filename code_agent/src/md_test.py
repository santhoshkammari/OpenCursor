from rich.console import Console
from rich.markdown import Markdown

md = Markdown("""[langchain is so good](https://python.langchain.com/docs/introduction/)""")

console = Console()
console.print(md)