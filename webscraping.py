from bs4 import BeautifulSoup
import re
import requests
import pandas as pd
from fake_useragent import UserAgent
import random
import time
import trafilatura
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random

# Helper function to truncate text
def truncate_text(text, max_length=500):
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

# Logger setup (simplified)
import logging
logger = logging.getLogger(__name__)

# Trafilatura configuration
from trafilatura.settings import use_config
config = use_config()
config.set("DEFAULT", "EXTRACTION_TIMEOUT", "0")

# Retry settings for requests
@retry(reraise=True, wait=wait_fixed(1) + wait_random(0, 1), stop=stop_after_attempt(2))
def get_url_raw_data(url, headers, timeout=10):
    result = requests.get(url, headers=headers, timeout=timeout, verify=False)
    return result

# Get text from URL
def get_text_from_url(url):
    try:
        ua = UserAgent()
        headers = {'User-Agent': ua.random}
        time.sleep(random.uniform(0, 1))
        result = get_url_raw_data(url, headers)
        assert result.status_code == 200
        html = result.text

        try:
            text = trafilatura.extract(html, url=url, config=config, favor_precision=True, favor_recall=False)
            meta = trafilatura.extract_metadata(html)
            title = meta.title.replace(' | Bankrate', '').replace(' - CreditCards.com', '')
        except:
            soup = BeautifulSoup(html, 'html.parser')
            for unwanted in soup(['script', 'style']):
                unwanted.decompose()
            text = soup.get_text(separator=' ')
            title = soup.title.string.replace(' | Bankrate', '').replace(' - CreditCards.com', '')

        if isinstance(text, str):
            return text, title, html
        else:
            logger.error(f"Error from URL {url}, returning empty texts")
            return '', '', ''
    except Exception as e:
        logger.error(f"Error getting text from URL {url}, returning empty texts: {e}")
        return '', '', ''

# Extract links with types
def extract_links_with_types(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    unique_links = {}

    roles = {
        'Writer': 'Written by',
        'Editor': 'Edited by',
        'Reviewer': 'Reviewed by'
    }

    for role, text in roles.items():
        spans = soup.find_all('span', string=lambda t: t and text in t)
        for span in spans:
            common_parent = span.find_parent('div')
            if common_parent:
                a_tags = common_parent.find_all('a', href=True)
                for a_tag in a_tags:
                    href = a_tag['href']
                    if 'www.bankrate.com' in href and href not in unique_links:
                        text, title, html = get_text_from_url(href)
                        unique_links[href] = {
                            'link_type': role,
                            'body_text': text
                        }

    link_details = [{'url': url, 'link_type': details['link_type'], 'body_text': details['body_text']} for url, details in unique_links.items()]
    return link_details

# Prepare data for DataFrame
def prepare_data_for_df(links, df):
    data = {
        'source_url': df['source_url'][0],
        'text': df['text'][0],
        'title': df['title'][0],
        'html': df['html'][0]
    }

    link_types = ['Writer', 'Editor', 'Reviewer']
    type_counters = {t: 0 for t in link_types}

    for link in links:
        link_type = link['link_type']
        url_key = f"{link_type.lower()}_page_url_{type_counters[link_type] + 1}"
        text_key = f"{link_type.lower()}_page_text_{type_counters[link_type] + 1}"
        
        if url_key not in data:
            data[url_key] = []
        if text_key not in data:
            data[text_key] = []
        
        data[url_key].append(link['url'])
        data[text_key].append(link['body_text'])
        type_counters[link_type] += 1

    return data

# Extract header info
def extract_header_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    article_body = soup.find('div', class_='ArticleBody')
    
    if not article_body:
        return []
    
    headers = article_body.find_all(['h2', 'h3', 'h4'])
    header_info = []
    header_order = 1

    for i, header in enumerate(headers):
        header_text = header.get_text(strip=True)
        header_type = header.name

        elements = []
        next_header = headers[i + 1] if i < len(headers) - 1 else None
        for sibling in header.find_next_siblings():
            if sibling == next_header:
                break
            elements.append(sibling)

        body_html = ''.join(str(element) for element in elements)
        body_text = BeautifulSoup(body_html, 'html.parser').get_text(separator=' ', strip=True)
        body_text = re.sub(r'\s+', ' ', body_text)

        header_info.append({
            'header_order': header_order,
            'header_title': header_text,
            'header_type': header_type,
            'header_body_text': body_text
        })
        
        header_order += 1

    return header_info

# Extract internal links
def extract_internal_links(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    article_body = soup.find('div', class_='ArticleBody')
    links = article_body.find_all('a', href=True)
    internal_links = []

    for link in links:
        url = link['href']
        if "www.bankrate.com" in url:
            anchor_text = link.get_text(strip=True)
            title_of_linked_page = fetch_title_of_page(url)
            internal_links.append({
                'internal_link_url': url,
                'anchor_text': anchor_text,
                'title_of_linked_page': title_of_linked_page
            })

    return internal_links

def fetch_title_of_page(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            page_soup = BeautifulSoup(response.content, 'html.parser')
            title_tag = page_soup.find('title')
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                cleaned_title = title_text.replace("| Bankrate", "").strip()
                return cleaned_title
            else:
                return 'No Title Found'
    except requests.RequestException as e:
        print(f"Failed to retrieve page title from {url}: {str(e)}")
    return 'No Title Available'

# Build document DataFrame
def build_document_dataframe(retrieved_document_urls):
    document_list = []
    for url in retrieved_document_urls:
        document, title, html = get_text_from_url(url)
        if len(document) > 0:
            document_list.append({'source_url': url, 'text': document, 'title': title, 'html': html})
    return document_list

# Main function to process the URL and output required variables
def process_url(url):
    # Step 1: Create a DataFrame from the URL
    internal_df = pd.DataFrame(build_document_dataframe([url]))

    # Step 2: Extract contributor links
    test_links = extract_links_with_types(internal_df['html'][0])

    # Step 3: Prepare DataFrame with contributor information
    data1 = pd.DataFrame(prepare_data_for_df(test_links, internal_df))

    # Step 4: Extract headers and body text
    headers_list = extract_header_info(data1['html'][0])
    data1['headers_info'] = [headers_list]

    # Step 5: Extract internal links
    urls = extract_internal_links(data1['html'][0])
    data1['internal_link_info'] = [urls]

    # Extract variables
    article_title = data1['title'][0]
    article_text = data1['text'][0]
    article_internal_links = data1['internal_link_info'][0]
    article_headers_info = data1['headers_info'][0]
    writer_page_text_1 = data1['writer_page_text_1'][0] if 'writer_page_text_1' in data1 else None
    editor_page_text_1 = data1['editor_page_text_1'][0] if 'editor_page_text_1' in data1 else None

    return {
        'article_title': article_title,
        'article_text': article_text,
        'article_internal_links': article_internal_links,
        'article_headers_info': article_headers_info,
        'writer_page_text_1': writer_page_text_1,
        'editor_page_text_1': editor_page_text_1
    }

# # Example usage
# url = 'https://www.bankrate.com/banking/cds/fixed-annuities-vs-cds/'
# result = process_url(url)

# # Print result (or return result if used in a function)
# print(result)
