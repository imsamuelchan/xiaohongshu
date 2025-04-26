import os
import requests
import json
import argparse
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get API key from environment variables
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise ValueError("No API_KEY found in .env file")

FIRECRAWL_API_URL = "https://api.firecrawl.dev/scrape"

def scrape_website(url: str, selector: Optional[str] = None, 
                  wait_for: Optional[str] = None, 
                  scroll_to_bottom: bool = False) -> Dict[str, Any]:
    """
    Scrape a website using the Firecrawl API
    
    Args:
        url: The URL to scrape
        selector: Optional CSS selector to wait for before capturing content
        wait_for: Optional time in milliseconds to wait after page load
        scroll_to_bottom: Whether to scroll to the bottom of the page
        
    Returns:
        Dictionary containing the scraped data
    """
    logger.info(f"Scraping URL: {url}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # Build the request payload
    payload = {
        "url": url,
        "options": {}
    }
    
    # Add optional parameters if provided
    if selector:
        payload["options"]["waitForSelector"] = selector
        logger.info(f"Waiting for selector: {selector}")
        
    if wait_for:
        payload["options"]["waitFor"] = wait_for
        logger.info(f"Wait time configured: {wait_for}ms")
        
    if scroll_to_bottom:
        payload["options"]["scrollToBottom"] = True
        logger.info("Will scroll to bottom of page")
    
    try:
        # Make the API request
        response = requests.post(
            FIRECRAWL_API_URL,
            headers=headers,
            json=payload
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            logger.info("Successfully retrieved data from Firecrawl API")
            result = response.json()
            
            # Save the HTML content to a file for inspection
            with open("scraped_content.html", "w", encoding="utf-8") as f:
                f.write(result.get("html", ""))
            logger.info("Saved HTML content to 'scraped_content.html'")
            
            # Save full response to a JSON file
            with open("firecrawl_response.json", "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info("Saved full response to 'firecrawl_response.json'")
            
            return result
        else:
            logger.error(f"Error: API request failed with status code {response.status_code}")
            logger.error(f"Response: {response.text}")
            return {"error": f"API request failed: {response.text}"}
            
    except Exception as e:
        logger.error(f"Error making request to Firecrawl API: {str(e)}")
        return {"error": str(e)}

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Scrape websites using Firecrawl API")
    
    parser.add_argument("url", help="The URL to scrape")
    parser.add_argument("--selector", help="CSS selector to wait for before capturing content")
    parser.add_argument("--wait", help="Time in milliseconds to wait after page load")
    parser.add_argument("--scroll", action="store_true", help="Scroll to the bottom of the page")
    
    return parser.parse_args()

def main():
    """Main function to run the scraper"""
    args = parse_arguments()
    
    result = scrape_website(
        url=args.url,
        selector=args.selector,
        wait_for=args.wait,
        scroll_to_bottom=args.scroll
    )
    
    if "error" not in result:
        print("\nScraping completed successfully!")
        print(f"HTML length: {len(result.get('html', ''))}")
        print(f"Status code: {result.get('statusCode')}")
        print(f"Content type: {result.get('contentType')}")
        print("\nCheck 'scraped_content.html' and 'firecrawl_response.json' for the results.")
    else:
        print(f"\nScraping failed: {result.get('error')}")

if __name__ == "__main__":
    main() 