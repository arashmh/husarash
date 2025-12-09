import json
import os

def process_urls():
    # Read URLs from urls.txt
    with open('urls.txt', 'r', encoding='utf-8') as f:
        new_urls = [line.strip() for line in f if line.strip()]
    
    # Check if final_urls.json exists
    if os.path.exists('final_urls.json'):
        # Load existing URLs
        with open('final_urls.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            existing_urls = data.get('urls', [])
        
        # Add new URLs that don't already exist
        existing_set = set(existing_urls)
        for url in new_urls:
            if url not in existing_set:
                existing_urls.append(url)
                existing_set.add(url)
        
        urls_to_save = existing_urls
    else:
        # Create new list with URLs from txt file
        urls_to_save = new_urls
    
    # Save to final_urls.json
    with open('final_urls.json', 'w', encoding='utf-8') as f:
        json.dump({'urls': urls_to_save}, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Processed {len(new_urls)} URLs from urls.txt")
    print(f"✓ Total URLs in final_urls.json: {len(urls_to_save)}")

if __name__ == '__main__':
    process_urls()
