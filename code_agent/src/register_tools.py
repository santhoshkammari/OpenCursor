"""
Module for registering additional tools with the Tools class.
"""

def register_additional_tools(tools_instance):
    """
    Register additional tools with the Tools instance.
    
    Args:
        tools_instance: The Tools instance to register tools with.
    """
    try:
        # Import and register the Playwright search tool
        from .tool_playwright_search import register_playwright_search_tool
        register_playwright_search_tool(tools_instance)
        print("✅ Playwright search tool registered successfully")
    except ImportError:
        try:
            # Try alternative import path
            from tool_playwright_search import register_playwright_search_tool
            register_playwright_search_tool(tools_instance)
            print("✅ Playwright search tool registered successfully (alternative path)")
        except ImportError:
            print("❌ Failed to import Playwright search tool")
            pass 