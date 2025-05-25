import asyncio
import os
import re
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

class PlaywrightBrowser:
    """A simplified browser interaction manager using Playwright"""

    def __init__(self, headless=True):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.headless = headless

    async def initialize(self):
        """Initialize the browser if not already done"""
        if self.page is not None:
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        self.page = await self.context.new_page()

    async def navigate_to(self, url: str):
        """Navigate to a URL"""
        await self.initialize()
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            print(f"Navigation error: {str(e)}")

    async def get_page_html(self):
        """Get the HTML content of the current page"""
        return await self.page.content()

    async def close(self):
        """Close browser and clean up resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


class PlaywrightSearch:
    """Web search implementation using Playwright"""

    def __init__(self, search_provider: str = 'bing'):
        """Initialize the search agent"""
        self.browser = PlaywrightBrowser(headless=False)
        self.search_provider = search_provider

    async def search(self, query: str, num_results: int = 10) -> List[Dict[str, str]]:
        """Perform a web search and return results"""
        try:
            # Navigate to search engine
            search_url = f'https://www.{self.search_provider}.com/search?q={query}'
            await self.browser.navigate_to(search_url)
            
            # Get the HTML content
            html = await self.browser.get_page_html()
            
            # Extract search results
            if self.search_provider == 'bing':
                search_results = self._extract_bing_results(html, num_results)
            elif self.search_provider == 'duckduckgo':
                search_results = self._extract_duckduckgo_results(html, num_results)
            else:
                search_results = []
                
            return search_results
        except Exception as e:
            print(f"Search error: {str(e)}")
            return []
        finally:
            await self.browser.close()

    def _extract_bing_results(self, html: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Extract search results from Bing HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        # Process Bing search results
        result_elements = soup.find_all('li', class_='b_algo')

        for result_element in result_elements:
            if len(results) >= max_results:
                break

            title = None
            url = None
            description = None

            # Find title and URL
            title_header = result_element.find('h2')
            if title_header:
                title_link = title_header.find('a')
                if title_link and title_link.get('href'):
                    url = title_link['href']
                    title = title_link.get_text(strip=True)

            # Find description
            caption_div = result_element.find('div', class_='b_caption')
            if caption_div:
                p_tag = caption_div.find('p')
                if p_tag:
                    description = p_tag.get_text(strip=True)

            # Add valid results
            if url and title:
                results.append({
                    "url": url,
                    "title": title,
                    "description": description or ""
                })

        return results

    def _extract_duckduckgo_results(self, html_content: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Extract search results from DuckDuckGo HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []

        # Find all result containers
        result_elements = soup.find_all('article', {'data-testid': 'result'})

        for result_element in result_elements:
            if len(results) >= max_results:
                break
                
            # URL
            url_element = result_element.find('a', {'data-testid': 'result-extras-url-link'})
            url = url_element['href'] if url_element else None

            # Title
            title_element = result_element.find('a', {'data-testid': 'result-title-a'})
            title = title_element.get_text(strip=True) if title_element else None

            # Description (Snippet)
            description_element = result_element.find('div', {'data-result': 'snippet'})
            if description_element:
                # Remove date spans if present
                date_span = description_element.find('span', class_=re.compile(r'MILR5XIV'))
                if date_span:
                    date_span.decompose()
                description = description_element.get_text(strip=True)
            else:
                description = None

            if url and title:
                results.append({
                    "url": url,
                    "title": title,
                    "description": description or ""
                })

        return results


# Tool function to be registered with the Tools class
async def web_search(
    search_term: str, 
    explanation: str = ""
) -> str:
    """
    Search the web for real-time information about any topic. 
    Use this tool when you need up-to-date information that might not be available in your training data, or when you need to verify current facts. 
    The search results will include relevant snippets and URLs from web pages. 
    This is particularly useful for questions about current events, technology updates, or any topic that requires recent information
    
    Args:
        search_term (str): The search term to look up on the web. Be specific and include relevant keywords for better results. For technical queries, include version numbers or dates if relevant.
        explanation (str): One sentence explanation as to why this tool is being used, and how it contributes to the goal
        
    Returns:
        str: Formatted search results
    """
    search_agent = PlaywrightSearch(search_provider="bing")
    
    try:
        results = await search_agent.search(search_term, num_results=10)
        
        if not results:
            return f"No results found for: {search_term}"
        
        # Format results
        formatted_results = f"Search results for: {search_term}\n\n"
        
        for i, result in enumerate(results, 1):
            formatted_results += f"{i}. {result['title']}\n"
            formatted_results += f"   URL: {result['url']}\n"
            if result.get('description'):
                formatted_results += f"   Description: {result['description']}\n"
            formatted_results += "\n"
            
        return formatted_results
    
    except Exception as e:
        return f"Error performing web search: {str(e)}"


# Function to register this tool with the Tools class
def register_playwright_search_tool(tools_instance):
    """Register the Playwright search tool with the Tools instance"""
    tools_instance.register_function(
        web_search,
        {
            'type': 'function',
            'function': {
                'name': 'web_search',
                'description': 'Search the web for real-time information about any topic. Use this tool when you need up-to-date information that might not be available in your training data, or when you need to verify current facts. The search results will include relevant snippets and URLs from web pages. This is particularly useful for questions about current events, technology updates, or any topic that requires recent information.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'search_term': {
                            'type': 'string',
                            'description': 'The search term to look up on the web. Be specific and include relevant keywords for better results. For technical queries, include version numbers or dates if relevant.'
                        },
                        'explanation': {
                            'type': 'string',
                            'description': 'One sentence explanation as to why this tool is being used, and how it contributes to the goal.'
                        }
                    },
                    'required': ['search_term']
                }
            }
        }
    )


async def test():
    urls =[
        "https://microsoft.github.io/autogen/stable//index.html",
        "https://python.langchain.com/docs/introduction/",
        "https://docs.cursor.com/welcome",
        "https://docs.anthropic.com/en/api/overview",
    ]
    browser = PlaywrightBrowser(headless=False)
    await browser.initialize()
    for url in urls:
        await browser.navigate_to(url)
        browser.browser
        break
    await browser.close()

if __name__ == "__main__":
    asyncio.run(test())