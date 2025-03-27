from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup
import time
import random
import logging
import re
import traceback
from datetime import datetime
from urllib.parse import quote_plus

class WebSearchClient:
    """Client for performing web searches and content extraction"""
    
    def __init__(self):
        """Initialize the web search client"""
        self.ddgs = DDGS()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'TE': 'Trailers',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def search(self, query, max_results=5):
        """Perform a search using DuckDuckGo"""
        try:
            logging.info(f"Performing search for query: {query}")
            results = []
            for r in self.ddgs.text(query, max_results=max_results):
                results.append({
                    'title': r.get('title', ''),
                    'body': r.get('body', ''),
                    'href': r.get('href', '')
                })
            logging.info(f"Found {len(results)} search results")
            
            # Format results for use in Gemini client
            if results:
                formatted_results = ""
                for i, result in enumerate(results):
                    formatted_results += f"{i+1}. {result['title']}\n"
                    formatted_results += f"   {result['body']}\n"
                    formatted_results += f"   [Source: {result['href']}]\n\n"
                return formatted_results
            return "No search results found."
        except Exception as e:
            logging.error(f"Error during search: {e}")
            logging.error(traceback.format_exc())
            return "Error performing web search."
    
    def optimize_query(self, model, original_query):
        """Use Gemini to optimize the search query for better results"""
        try:
            logging.info(f"Optimizing query: {original_query}")
            optimization_prompt = f"""Transform this query into an optimal search query:
            Original: "{original_query}"
            
            Rules:
            1. Remove filler words and conversational phrases
            2. Keep key technical terms and specifics
            3. Make it concise and focused
            4. Format for search engines
            5. Return ONLY the optimized query
            
            Optimized query:"""
            
            response = model.generate_content(optimization_prompt)
            optimized_query = response.text.strip()
            
            if not optimized_query:
                logging.warning("Query optimization returned empty result, using original query")
                return original_query
                
            logging.info(f"Query optimization: {original_query} -> {optimized_query}")
            return optimized_query
        except Exception as e:
            logging.error(f"Error optimizing query: {e}")
            logging.error(traceback.format_exc())
            return original_query
    
    def _clean_text(self, text):
        """Clean and normalize text content"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?-]', ' ', text)
        
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _extract_main_content(self, soup):
        """Extract the main content from a webpage"""
        # Common content selectors
        selectors = [
            'main', 'article', '[role="main"]', '#content', '.content',
            '#main', '.main', '#article', '.article', '.post', '#post',
            '.entry', '#entry', '.story', '#story'
        ]
        
        # Try each selector
        for selector in selectors:
            content = soup.select(selector)
            if content:
                return content[0]
        
        # Fallback to body if no main content found
        return soup.body if soup.body else soup
    
    def scrape_webpage(self, url):
        """Scrape the content of a webpage"""
        try:
            logging.info(f"Scraping webpage: {url}")
            # Add a small random delay to avoid rate limiting
            time.sleep(random.uniform(0.5, 1.5))
            
            # Use session for better performance
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside', 'iframe']):
                element.decompose()
            
            # Get main content
            main_content = self._extract_main_content(soup)
            
            # Extract text content
            content_text = main_content.get_text(separator=' ', strip=True)
            content_text = self._clean_text(content_text)
            
            # Extract metadata
            title = soup.title.string if soup.title else ""
            description = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                description = meta_desc.get('content', '')
            
            # Extract links for context
            links = []
            for link in main_content.find_all('a', href=True):
                href = link.get('href')
                if href and not href.startswith('#'):
                    links.append(href)
            
            # Limit text length
            max_chars = 3000
            if len(content_text) > max_chars:
                content_text = content_text[:max_chars] + "..."
            
            logging.info(f"Successfully scraped webpage: {url}")
            return {
                'title': title,
                'description': description,
                'content': content_text,
                'url': url,
                'links': links[:5]  # Keep top 5 relevant links
            }
        except Exception as e:
            logging.error(f"Error scraping webpage {url}: {e}")
            logging.error(traceback.format_exc())
            return {
                'title': '',
                'description': '',
                'content': '',
                'url': url,
                'links': []
            }
    
    def search_and_scrape(self, query, model=None):
        """Perform web search and scrape content"""
        try:
            # Optimize the query for search
            search_query = self._optimize_search_query(query)
            logging.info(f"Optimized search query: {search_query}")
            
            # Get search results
            search_results = self._get_search_results(search_query)
            if not search_results:
                return "No relevant information found online."
            
            # Extract and process content
            all_content = []
            
            # Keep track of processed URLs to avoid duplicates
            processed_urls = set()
            
            for result in search_results[:3]:  # Limit to top 3 results for quality
                url = result.get('link')
                
                if not url or url in processed_urls:
                    continue
                
                processed_urls.add(url)
                
                try:
                    # Get content from URL
                    content = self._get_content_from_url(url)
                    
                    if content:
                        # Clean and summarize the content
                        cleaned_content = self._clean_content(content)
                        
                        # Add source information
                        source_info = f"Source: {result.get('title', 'Unknown')} ({url})"
                        
                        # Add to results
                        all_content.append(f"{source_info}\n{cleaned_content}")
                except Exception as e:
                    logging.error(f"Error processing URL {url}: {e}")
                    continue
            
            if not all_content:
                return "Found search results but couldn't extract relevant content."
            
            # Format the results in a structured way
            formatted_results = "\n\n".join(all_content)
            
            # Generate a summary if a model is provided
            if model:
                try:
                    prompt = f"""Summarize the following web search results to provide relevant information for answering: "{query}"
                    Extract all key facts and data that would be useful for answering the query.
                    
                    Web search results:
                    {formatted_results}
                    
                    Summary:"""
                    
                    response = model.generate_content(prompt)
                    summary = response.text
                    
                    # Add a clear delimiter to separate sources and summary
                    final_result = f"""SUMMARY:
                    {summary}
                    
                    SOURCES:
                    {formatted_results}"""
                    
                    return final_result
                except Exception as e:
                    logging.error(f"Error generating summary: {e}")
            
            return formatted_results
        
        except Exception as e:
            logging.error(f"Error in search_and_scrape: {e}")
            logging.error(traceback.format_exc())
            return "Error performing web search."
    
    def _optimize_search_query(self, query):
        """Optimize the query for web search"""
        # Remove unnecessary words and focus on the core query
        filler_words = ['please', 'could you', 'can you', 'I want to know', 'tell me', 'find', 'search', 'look up']
        optimized = query
        
        for word in filler_words:
            optimized = optimized.replace(word, '')
        
        # Add current year for time-sensitive queries
        time_indicators = ['latest', 'current', 'recent', 'now', 'today']
        
        for indicator in time_indicators:
            if indicator in query.lower() and '2024' not in query and '2025' not in query:
                current_year = datetime.now().year
                optimized += f" {current_year}"
                break
        
        # Ensure query is not empty after optimization
        optimized = optimized.strip()
        if not optimized:
            return query
            
        return optimized
    
    def _get_search_results(self, query):
        """Get search results from DuckDuckGo"""
        try:
            # First try using the DDGS API
            logging.info(f"Searching with DDGS for: {query}")
            results = []
            
            try:
                # Use the direct DDGS method
                for r in self.ddgs.text(query, max_results=5):
                    results.append({
                        'title': r.get('title', ''),
                        'snippet': r.get('body', ''),
                        'link': r.get('href', '')
                    })
                
                if results:
                    logging.info(f"Found {len(results)} results via DDGS")
                    return results
            except Exception as e:
                logging.error(f"DDGS search failed: {e}")
            
            # If the DDGS search failed or returned no results, try the fallback
            return self._fallback_search(query)
        
        except Exception as e:
            logging.error(f"Error in get_search_results: {e}")
            logging.error(traceback.format_exc())
            # Try the fallback method
            return self._fallback_search(query)
    
    def _fallback_search(self, query):
        """Fallback search using DuckDuckGo's HTML search"""
        try:
            encoded_query = quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                logging.error(f"DuckDuckGo HTML search returned status code {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Extract results from HTML
            for result in soup.select('.result'):
                title_elem = result.select_one('.result__title')
                link_elem = result.select_one('.result__url')
                snippet_elem = result.select_one('.result__snippet')
                
                if title_elem and link_elem:
                    title = title_elem.get_text(strip=True)
                    link = link_elem.get('href', '')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                    
                    results.append({
                        'title': title,
                        'link': link,
                        'snippet': snippet
                    })
            
            return results[:5]  # Limit to 5 results
        
        except Exception as e:
            logging.error(f"Error in fallback search: {e}")
            logging.error(traceback.format_exc())
            return []
    
    def _get_content_from_url(self, url):
        """Extract content from a URL"""
        try:
            # Set a timeout to avoid hanging
            response = self.session.get(url, timeout=5)
            if response.status_code != 200:
                logging.error(f"URL {url} returned status code {response.status_code}")
                return ""
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script, style, and other non-content elements
            for element in soup(['script', 'style', 'meta', 'noscript', 'iframe', 'header', 'footer', 'nav']):
                element.decompose()
            
            # Try to find main content elements
            main_content = self._extract_main_content(soup)
            
            # Get text content
            content = main_content.get_text(separator=' ', strip=True)
            
            # Clean up the content
            content = self._clean_text(content)
            
            return content
        except Exception as e:
            logging.error(f"Error extracting content from {url}: {e}")
            logging.error(traceback.format_exc())
            return ""
    
    def _clean_content(self, content):
        """Clean and prepare the content for the model"""
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Limit content length (3000 chars max)
        if len(content) > 3000:
            content = content[:2997] + "..."
        
        return content 