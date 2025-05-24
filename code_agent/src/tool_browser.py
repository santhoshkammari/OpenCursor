import asyncio
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

class ExtenedDomService(DomService):
    def __init__(self, page):
        super().__init__(page)
        self.clickable_elements = []
        self.page = page
    
    async def get_clickable_elements(self):
        dom_state = await super().get_clickable_elements()
        return dom_state
    
    async def get_clickable_elements_with_text(self):
        dom_state = await self.get_clickable_elements()
        for element in dom_state.selector_map.values():
            if element.text:
                self.clickable_elements.append(element)
        return self.clickable_elements
    
    async def get_clickable_elements_with_text_and_url(self):
        dom_state = await self.get_clickable_elements()
        for element in dom_state.selector_map.values():
            if element.text and element.url:
                self.clickable_elements.append(element)
        return self.clickable_elements
    
    async def get_search_keyword_index(self):
        dom_state = await self.get_clickable_elements()
        rich.print(dom_state.selector_map)
        #aria-label="Search"
        for element_key,element in dom_state.selector_map.items():
            if element.attributes.get("aria-label") == "Search":
                return element_key
        return None
    
    async def get_search_input_element(self):
        """Find the search input element after the search button has been clicked"""
        dom_state = await self.get_clickable_elements()
        print("Looking for search input element among these elements:")
        rich.print(dom_state.selector_map)
        
        # Look for input elements with search-related attributes
        for element_key, element in dom_state.selector_map.items():
            # Check if it's an input element or has input in the tag name
            if (hasattr(element, 'tag_name') and 
                (element.tag_name == "input" or 'input' in str(element.tag_name).lower())):
                print(f"Found potential input element: {element}")
                # Check for common search input attributes
                if (element.attributes.get("type") == "search" or 
                    "search" in element.attributes.get("class", "").lower() or 
                    "search" in element.attributes.get("id", "").lower() or 
                    "search" in element.attributes.get("name", "").lower() or
                    "search" in element.attributes.get("placeholder", "").lower()):
                    return element_key
            
            # Also check if any attribute contains 'search'
            if hasattr(element, 'attributes'):
                for attr_name, attr_value in element.attributes.items():
                    if isinstance(attr_value, str) and 'search' in attr_value.lower():
                        print(f"Found element with search in attributes: {element}")
                        return element_key
        
        # If we couldn't find a search input, try to find any input element
        for element_key, element in dom_state.selector_map.items():
            if hasattr(element, 'tag_name') and element.tag_name == "input":
                print(f"Falling back to first input element: {element}")
                return element_key
                
        return None
    
    async def fill_element(self, element_key, text):
        """Fill a form element with text by its key in the selector map"""
        if element_key is not None:
            dom_state = await self.get_clickable_elements()
            if element_key in dom_state.selector_map:
                element = dom_state.selector_map[element_key]
                print(f"Element details for filling: {element}")
                
                try:
                    # Try filling by aria-label attribute
                    if hasattr(element, 'attributes') and element.attributes.get('aria-label'):
                        aria_label = element.attributes.get('aria-label')
                        selector = f"input[aria-label='{aria_label}']"
                        await self.page.fill(selector, text)
                        print(f"Filled element with aria-label selector: {selector}")
                        return True
                    # Try filling by xpath
                    elif hasattr(element, 'xpath') and element.xpath:
                        # Make sure xpath starts with // for relative path
                        xpath = element.xpath
                        if not xpath.startswith('//'):
                            xpath = '//' + xpath.lstrip('/')
                        await self.page.fill(xpath, text)
                        print(f"Filled element with XPath: {xpath}")
                        return True
                    # Try by id if available
                    elif hasattr(element, 'attributes') and element.attributes.get('id'):
                        id_value = element.attributes.get('id')
                        selector = f"#{id_value}"
                        await self.page.fill(selector, text)
                        print(f"Filled element with ID selector: {selector}")
                        return True
                    else:
                        print(f"Could not find a way to fill element with key {element_key}")
                except Exception as e:
                    print(f"Error filling element: {str(e)}")
                    
                    # Fallback to direct fill by tag and aria-label
                    try:
                        await self.page.fill("input[aria-label='Search']", text)
                        print("Filled search input using direct selector")
                        return True
                    except Exception as e2:
                        print(f"Fallback fill also failed: {str(e2)}")
            else:
                print(f"Element with key {element_key} not found in selector map")
        return False
    
    async def click_element(self, element_key):
        """Click on an element by its key in the selector map"""
        if element_key is not None:
            dom_state = await self.get_clickable_elements()
            if element_key in dom_state.selector_map:
                element = dom_state.selector_map[element_key]
                print(f"Element details: {element}")
                
                try:
                    # Try clicking by aria-label attribute
                    if hasattr(element, 'attributes') and element.attributes.get('aria-label'):
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
            
            # Wait to ensure page is loaded
            await asyncio.sleep(2)
            
            dom_service = ExtenedDomService(browser.page)
            search_keyword_index = await dom_service.get_search_keyword_index()
            
            if search_keyword_index is not None:
                print(f"Found search element with index: {search_keyword_index}")
                rich.print(search_keyword_index)
                
                # Click the search element
                success = await dom_service.click_element(search_keyword_index)
                await asyncio.sleep(2)  # Give time for search input to appear
                
                # Test filling the search input
                if success:
                    # Find the search input element that appears after clicking
                    search_input_index = await dom_service.get_search_input_element()
                    if search_input_index is not None:
                        print(f"Found search input element with index: {search_input_index}")
                        
                        search_text = "function examples"
                        print(f"Filling search input with: '{search_text}'")
                        fill_success = await dom_service.fill_element(search_input_index, search_text)
                        if fill_success:
                            print("Successfully filled search input")
                            await asyncio.sleep(2)  # Give time to see the filled input
                        else:
                            print("Failed to fill search input")
                    else:
                        print("Search input element not found after clicking search button")
                        # Try a direct approach as fallback
                        try:
                            await browser.page.fill("input[type='search']", "function examples")
                            print("Filled search input using direct selector")
                            await asyncio.sleep(2)
                        except Exception as e:
                            print(f"Direct fill approach also failed: {str(e)}")
                
                break  # Exit the loop if we found a search element
            else:
                print("Search element not found, trying next URL")
        except Exception as e:
            print(f"Error with URL {url}: {str(e)}")
            continue
    
    await browser.close()
    print("\nTests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test())