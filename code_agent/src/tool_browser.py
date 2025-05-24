import asyncio
import json
import os
import re
from typing import Dict, List, Optional, Any
from browser_use import BrowserSession, BrowserProfile,DomService
from playwright.async_api import async_playwright


from bs4 import BeautifulSoup
import rich

class PlaywrightBrowser:
    """A simplified browser interaction manager using Playwright"""

    def __init__(self, headless=False):
        self.browser = None
        self.context = None
        self.headless = headless
        self.session = None
        self.profile = None
        self.page = None
        self.playwright = None

    async def initialize(self):
        """Initialize the browser if not already done"""
        if self.browser is None:
            self.playwright = await async_playwright().start()
            # Launch browser directly rather than using BrowserSession
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox']
            )
            self.context = await self.browser.new_context()
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
        if self.page:
            return await self.page.content()
        return ""
    
    async def get_clickable_elements(self):
        dom_service = DomService(self.page)
        dom_state = await dom_service.get_clickable_elements()
        return dom_state
    
    async def get_search_keyword_index(self):
        """Get the index of the search element in the DOM"""
        dom_state = await self.get_clickable_elements()
        # Look for elements with aria-label="Search" or similar search indicators
        for element_key, element in dom_state.selector_map.items():
            if (element.attributes.get("aria-label") == "Search" or 
                element.attributes.get("placeholder", "").lower().find("search") >= 0 or
                element.attributes.get("id", "").lower().find("search") >= 0 or
                element.attributes.get("name", "").lower().find("search") >= 0 or
                element.attributes.get("title", "").lower().find("search") >= 0):
                return element_key
        return None


    async def click_element_by_index(self, element_key,dom_state=None):
        """Click on an element by its key in the selector map"""
        if element_key is not None:
            dom_state = dom_state or await self.get_clickable_elements()
            if element_key in dom_state.selector_map:
                element = dom_state.selector_map[element_key]
                print(f"Element details: {element}")
                
                try:
                    if hasattr(element, 'attributes') and element.attributes.get('href'):
                        href = element.attributes.get('href')
                        # Handle relative URLs by combining with the current page's base URL
                        if href.startswith('/'):
                            # Extract base URL (protocol + domain)
                            current_url = self.page.url
                            base_url_match = re.match(r'(https?://[^/]+)', current_url)
                            if base_url_match:
                                base_url = base_url_match.group(1)
                                absolute_url = f"{base_url}{href}"
                                await self.navigate_to(absolute_url)
                                print(f"Clicked element with relative href: {href} -> {absolute_url}")
                                return True
                        # Handle absolute URLs directly
                        await self.navigate_to(href)
                        print(f"Clicked element with href: {href}")
                        return True
                    # Try clicking by aria-label attribute
                    elif hasattr(element, 'attributes') and element.attributes.get('aria-label'):
                        aria_label = element.attributes.get('aria-label')
                        selector = f"button[aria-label='{aria_label}']"
                        await self.page.click(selector)
                        print(f"Clicked element with aria-label selector: {selector}")
                        return True
                    # Try clicking by xpath (need to properly format the xpath)
                    elif hasattr(element, 'xpath') and element.xpath:
                        # Make sure xpath starts with // for relative path
                        xpath = element.xpath
                        if not xpath.startswith('//'):
                            xpath = '//' + xpath.lstrip('/')
                        await self.page.click(xpath)
                        print(f"Clicked element with XPath: {xpath}")
                        return True
                    else:
                        print(f"Could not find a way to click element with key {element_key}")
                except Exception as e:
                    print(f"Error clicking element: {str(e)}")
                    
                    # Fallback to direct click by tag and aria-label
                    try:
                        await self.page.click("button[aria-label='Search']")
                        print("Clicked search button using direct selector")
                        return True
                    except Exception as e2:
                        print(f"Fallback click also failed: {str(e2)}")
            else:
                print(f"Element with key {element_key} not found in selector map")
        return False

    
    async def keyboard_press(self, key):
        await self.page.keyboard.press(key)
        await self.page.wait_for_load_state("networkidle", timeout=10000)

    async def keyboard_insert_text(self, text):
        await self.page.keyboard.insert_text(text)
    
    async def keyboard_press_enter(self):
        await self.page.keyboard.press("Enter")
        await self.page.wait_for_load_state("networkidle", timeout=10000)

    async def click_search_k_by_domelement_approach(self):
        """Find and click the search element in the DOM"""
        search_keyword_index = await self.get_search_keyword_index()
        if search_keyword_index is not None:
            return await self.click_element_by_index(search_keyword_index)
        return False
    
    async def click_search_k_by_direct_keyboard_approach(self):
        await self.keyboard_press('Control+k')

    async def close(self):
        """Close browser and clean up resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def search_inside_webpage_using_keyboard_shortcut(self, query: str, url: str = None) -> dict:
        """
        Search within the current webpage using keyboard shortcut (Ctrl+K)
        
        This tool searches within documentation or websites that have search functionality 
        accessible via Ctrl+K keyboard shortcut. It navigates to the URL (if provided),
        activates the search box with Ctrl+K, enters the query, and returns structured results.
        
        Args:
            query (str): The search query to enter
            url (str): Optional URL to navigate to before searching. If not provided, uses current page.
            
        Returns:
            dict: Dictionary of search results with clickable elements
        """
        try:
            # Navigate to URL if provided
            if url!=self.page.url:
                await self.navigate_to(url)
            
            # Get current page URL for resolving relative URLs
            current_url = self.page.url
            base_url_match = re.match(r'(https?://[^/]+)', current_url)
            base_url = base_url_match.group(1) if base_url_match else ""
            
            # Press Ctrl+K to open search
            await self.keyboard_press('Control+k')
            await asyncio.sleep(1)  # Wait for search input to appear
            
            # Enter search query
            await self.keyboard_insert_text(query)
            await asyncio.sleep(1)  # Wait briefly
            
            # Get clickable elements from DOM
            dom_state = await self.get_clickable_elements()
            
            # Convert DOM elements to a nicely formatted dictionary
            results = []
            for idx, element in dom_state.selector_map.items(
                ):
                # Only include visible and interactive elements and in viewport and has href
                if element.is_visible and element.is_interactive and element.is_in_viewport and element.attributes.get("href"):
                    href = element.attributes.get("href", "")
                    
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        absolute_url = f"{base_url}{href}"
                    elif not href.startswith(('http://', 'https://')):
                        # Handle other relative URLs (without leading slash)
                        path_parts = current_url.split('/')
                        if len(path_parts) > 3:  # http://domain.com/path
                            parent_path = '/'.join(path_parts[:-1]) + '/'
                            absolute_url = f"{parent_path}{href}"
                        else:
                            absolute_url = f"{current_url.rstrip('/')}/{href}"
                    else:
                        absolute_url = href
                    
                    result = {
                        "index": idx,
                        "title": element.get_all_text_till_next_clickable_element(),
                        "url": absolute_url,
                        "tag_name": element.tag_name,
                        "description": element.attributes.get("aria-label", ""),
                        "is_top_element": element.is_top_element,
                        "is_in_viewport": element.is_in_viewport
                    }
                    results.append(result)

            return json.dumps({
                "query": query,
                "url": url or self.page.url,
                "total_results": len(results),
                "results": results
            })
        except Exception as e:
            print(f"Error in search_inside_webpage_using_keyboard_shortcut: {str(e)}")
            return {"error": str(e), "query": query, "url": url or self.page.url, "results": []}

    async def search_inside_webpage_using_dom_element(self, query: str, url: str = None) -> dict:
        """
        Search within the current webpage by finding and clicking the search element
        
        This tool is a fallback when keyboard shortcut doesn't work. It searches within 
        documentation or websites by finding the search button/input in the DOM, clicking it,
        entering the query, and returning structured results.
        
        Args:
            query (str): The search query to enter
            url (str): Optional URL to navigate to before searching. If not provided, uses current page.
            
        Returns:
            dict: Dictionary of search results with clickable elements
        """
        try:
            # Navigate to URL if provided
            if url!=self.page.url:
                await self.navigate_to(url)
            
            # Get current page URL for resolving relative URLs
            current_url = self.page.url
            base_url_match = re.match(r'(https?://[^/]+)', current_url)
            base_url = base_url_match.group(1) if base_url_match else ""
            
            # Get search element index
            search_keyword_index = await self.get_search_keyword_index()
            
            # Click on the search element
            success = await self.click_element_by_index(search_keyword_index)
            if not success:
                return {"error": "Failed to click search element", "query": query, "url": url or self.page.url, "results": []}
            
            await asyncio.sleep(1)  # Wait for search input to appear
            
            # Enter search query
            await self.keyboard_insert_text(query)
            await asyncio.sleep(1)  # Wait briefly
            
            
            # Get clickable elements from DOM
            dom_state = await self.get_clickable_elements()
            
            # Convert DOM elements to a nicely formatted dictionary
            results = []
            for idx, element in dom_state.selector_map.items():
                # Only include visible and interactive elements
                if element.is_visible and element.is_interactive:
                    href = element.attributes.get("href", "")
                    
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        absolute_url = f"{base_url}{href}"
                    elif href and not href.startswith(('http://', 'https://')):
                        # Handle other relative URLs (without leading slash)
                        path_parts = current_url.split('/')
                        if len(path_parts) > 3:  # http://domain.com/path
                            parent_path = '/'.join(path_parts[:-1]) + '/'
                            absolute_url = f"{parent_path}{href}"
                        else:
                            absolute_url = f"{current_url.rstrip('/')}/{href}"
                    else:
                        absolute_url = href
                    
                    result = {
                        "index": idx,
                        "title": element.get_all_text_till_next_clickable_element(),
                        "url": absolute_url if href else "",
                        "tag_name": element.tag_name,
                        "description": element.attributes.get("aria-label", ""),
                        "is_top_element": element.is_top_element,
                        "is_in_viewport": element.is_in_viewport
                    }
                    results.append(result)

            
            return json.dumps({
                "query": query,
                "url": url or self.page.url,
                "total_results": len(results),
                "results": results
            })
        except Exception as e:
            print(f"Error in search_inside_webpage_using_dom_element: {str(e)}")
            return {"error": str(e), "query": query, "url": url or self.page.url, "results": []}


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
async def web_search_playwright(
    search_term: str, 
    num_results: int = 10,
    explanation: str = ""
) -> str:
    """
    Search the web using Playwright browser automation.
    
    Args:
        search_term (str): The search query
        num_results (int): Maximum number of results to return
        explanation (str): Explanation for why this search is being performed
        
    Returns:
        str: Formatted search results
    """
    search_agent = PlaywrightSearch(search_provider="bing")
    
    try:
        results = await search_agent.search(search_term, num_results)
        
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
        web_search_playwright,
        {
            'type': 'function',
            'function': {
                'name': 'web_search_playwright',
                'description': 'Search the web for information using Playwright browser automation',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'search_term': {
                            'type': 'string',
                            'description': 'The search query to look up on the web'
                        },
                        'num_results': {
                            'type': 'integer',
                            'description': 'Maximum number of results to return'
                        },
                        'explanation': {
                            'type': 'string',
                            'description': 'Explanation for why this search is being performed'
                        }
                    },
                    'required': ['search_term']
                }
            }
        }
    )

# Function to register browser search tools with the Tools class
def register_browser_search_tools(tools_instance):
    """Register browser search tools with the Tools instance"""
    
    async def search_in_docs_with_keyboard_shortcut(query: str, url: str = None, explanation: str = "") -> dict:
        """
        Search within documentation or website using Ctrl+K keyboard shortcut
        
        This is the primary tool for searching within documentation pages or websites
        that have search functionality accessible via Ctrl+K keyboard shortcut.
        Use this tool when you need to find specific information within a website's documentation.
        
        Args:
            query (str): The search query to enter
            url (str): Optional URL to navigate to before searching. If not provided, uses current page.
            explanation (str): Explanation for why this search is being performed
            
        Returns:
            dict: Dictionary of search results with clickable elements
        """
        browser = PlaywrightBrowser(headless=False)
        try:
            await browser.initialize()
            if url:
                await browser.navigate_to(url)
            results = await browser.search_inside_webpage_using_keyboard_shortcut(query, url)
            return results
        finally:
            await browser.close()
    
    async def search_in_docs_with_dom_element(query: str, url: str = None, explanation: str = "") -> dict:
        """
        Search within documentation or website by finding and clicking the search element
        
        This is a fallback tool when the keyboard shortcut approach doesn't work.
        Use this tool when you need to find specific information within a website's documentation
        and the primary search_in_docs_with_keyboard_shortcut tool fails.
        
        Args:
            query (str): The search query to enter
            url (str): Optional URL to navigate to before searching. If not provided, uses current page.
            explanation (str): Explanation for why this search is being performed
            
        Returns:
            dict: Dictionary of search results with clickable elements
        """
        browser = PlaywrightBrowser(headless=False)
        try:
            await browser.initialize()
            if url:
                await browser.navigate_to(url)
            results = await browser.search_inside_webpage_using_dom_element(query, url)
            return results
        finally:
            await browser.close()
    
    # Register the functions with the Tools instance
    tools_instance.register_function(
        search_in_docs_with_keyboard_shortcut,
        {
            'type': 'function',
            'function': {
                'name': 'search_in_docs_with_keyboard_shortcut',
                'description': 'Search within documentation or website using Ctrl+K keyboard shortcut. This is the primary tool for searching within documentation pages.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'The search query to enter'
                        },
                        'url': {
                            'type': 'string',
                            'description': 'Optional URL to navigate to before searching. If not provided, uses current page.'
                        },
                        'explanation': {
                            'type': 'string',
                            'description': 'Explanation for why this search is being performed'
                        }
                    },
                    'required': ['query']
                }
            }
        }
    )
    
    tools_instance.register_function(
        search_in_docs_with_dom_element,
        {
            'type': 'function',
            'function': {
                'name': 'search_in_docs_with_dom_element',
                'description': 'Search within documentation or website by finding and clicking the search element. Use this as a fallback when the keyboard shortcut approach fails.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'The search query to enter'
                        },
                        'url': {
                            'type': 'string',
                            'description': 'Optional URL to navigate to before searching. If not provided, uses current page.'
                        },
                        'explanation': {
                            'type': 'string',
                            'description': 'Explanation for why this search is being performed'
                        }
                    },
                    'required': ['query']
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
    
    # Test browser navigation
    print("\n=== Testing browser navigation ===")
    browser = PlaywrightBrowser(headless=False)
    await browser.initialize()
    
    # Try each URL until one works
    for url in urls:
        try:
            print(f"Navigating to {url}")
            await browser.navigate_to(url)
            await browser.click_element_by_index(9)
            
            # await browser.keyboard_press('Control+k') 
            # await browser.keyboard_insert_text("function examples")
            # await browser.keyboard_press_enter()
            await asyncio.sleep(5)  # Give time for search input to appear
                
               
        except Exception as e:
            print(f"Error with URL {url}: {str(e)}")
            continue
    
    await browser.close()
    print("\nTests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test())