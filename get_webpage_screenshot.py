import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import os
import requests
from urllib.parse import urljoin, urlparse, urlunparse
from io import BytesIO
from PIL import Image
import hashlib

def clean_url(url):
    """Remove query parameters and anchors from URL"""
    parsed = urlparse(url)
    # Reconstruct URL without query string and fragment (anchor)
    cleaned = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        '',  # params
        '',  # query (removing this removes ?... parameters)
        ''   # fragment (removing this removes #... anchors)
    ))
    # Remove trailing slash for consistency
    if cleaned.endswith('/'):
        cleaned = cleaned[:-1]
    return cleaned

def normalize_urls_in_json():
    """Clean all URLs in final_urls.json and convert to new format with title field"""
    if not os.path.exists('final_urls.json'):
        return
    
    print("Normalizing URLs in final_urls.json...")
    
    with open('final_urls.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        urls = data.get('urls', [])
    
    # Handle both old format (list of strings) and new format (list of objects)
    normalized_entries = []
    seen_urls = set()
    
    for item in urls:
        if isinstance(item, str):
            # Old format: plain string URL
            cleaned = clean_url(item)
            if cleaned not in seen_urls:
                normalized_entries.append({'url': cleaned, 'title': ''})
                seen_urls.add(cleaned)
        elif isinstance(item, dict):
            # New format: object with url and title
            cleaned = clean_url(item.get('url', ''))
            if cleaned and cleaned not in seen_urls:
                normalized_entries.append({'url': cleaned, 'title': item.get('title', '')})
                seen_urls.add(cleaned)
    
    # Save back to file
    with open('final_urls.json', 'w', encoding='utf-8') as f:
        json.dump({'urls': normalized_entries}, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Normalized {len(normalized_entries)} URLs (removed {len(urls) - len(normalized_entries)} duplicates)")
    print()

def get_image_hash(image_content):
    """Generate a hash of the image content to detect duplicates"""
    return hashlib.md5(image_content).hexdigest()

def is_image_mostly_white(img_content):
    """Check if image has more than 50% white or near-white pixels"""
    try:
        img = Image.open(BytesIO(img_content))
        
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Get pixel data
        pixels = list(img.getdata())
        total_pixels = len(pixels)
        white_pixels = 0
        
        # Count white or near-white pixels (RGB values > 240)
        for r, g, b in pixels:
            if r > 240 and g > 240 and b > 240:
                white_pixels += 1
        
        white_percentage = (white_pixels / total_pixels) * 100
        return white_percentage > 50
    except:
        # If we can't check, assume it's not mostly white
        return False

def is_image_too_square(width, height):
    """Check if image is too square (aspect ratio too close to 1:1)"""
    if width == 0 or height == 0:
        return True
    
    aspect_ratio = max(width, height) / min(width, height)
    # If aspect ratio is less than 1.3, it's too square
    # (e.g., 600x600 is 1.0, 600x500 is 1.2, 600x400 is 1.5)
    return aspect_ratio < 1.3

def compress_image(img_content, target_size_kb):
    """Compress image to target file size in KB"""
    try:
        img = Image.open(BytesIO(img_content))
        
        # Convert RGBA to RGB if needed
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Start with high quality
        quality = 95
        output = BytesIO()
        
        # Iteratively reduce quality until we hit target size
        while quality > 20:
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            size_kb = len(output.getvalue()) / 1024
            
            if size_kb <= target_size_kb:
                break
            
            # Reduce quality more aggressively if we're far from target
            if size_kb > target_size_kb * 2:
                quality -= 15
            elif size_kb > target_size_kb * 1.5:
                quality -= 10
            else:
                quality -= 5
        
        # If still too large, resize the image
        if len(output.getvalue()) / 1024 > target_size_kb:
            scale_factor = 0.9
            while len(output.getvalue()) / 1024 > target_size_kb and scale_factor > 0.3:
                new_width = int(img.width * scale_factor)
                new_height = int(img.height * scale_factor)
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                output = BytesIO()
                resized_img.save(output, format='JPEG', quality=85, optimize=True)
                scale_factor -= 0.1
        
        return output.getvalue()
    except Exception as e:
        print(f"  Error compressing image: {str(e)}")
        return img_content

def get_webpage_screenshot():
    """
    Reads URLs from final_urls.json and downloads the 4 biggest unique images from each webpage.
    Only downloads images that are at least 400x600 pixels and 120KB in size.
    Images are saved in the screenshots folder with format {index}_{1-4}.png
    Resumes from the last processed index if images already exist.
    """
    # Check if urls.txt exists and merge new URLs
    if os.path.exists('urls.txt'):
        print("Checking urls.txt for new URLs...")
        with open('urls.txt', 'r', encoding='utf-8') as f:
            raw_urls = [line.strip() for line in f if line.strip()]
        
        # Clean URLs from txt file
        cleaned_new_urls = []
        seen_new = set()
        for url in raw_urls:
            cleaned = clean_url(url)
            if cleaned and cleaned not in seen_new:
                cleaned_new_urls.append(cleaned)
                seen_new.add(cleaned)
        
        # Check if final_urls.json exists
        if os.path.exists('final_urls.json'):
            # Load existing entries
            with open('final_urls.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                existing_entries = data.get('urls', [])
            
            # Get existing URLs
            existing_urls = set()
            for entry in existing_entries:
                if isinstance(entry, dict):
                    existing_urls.add(entry['url'])
                else:
                    existing_urls.add(entry)
            
            # Add only new URLs that don't exist
            added_count = 0
            for new_url in cleaned_new_urls:
                if new_url not in existing_urls:
                    existing_entries.append({'url': new_url, 'title': ''})
                    existing_urls.add(new_url)
                    added_count += 1
            
            if added_count > 0:
                with open('final_urls.json', 'w', encoding='utf-8') as f:
                    json.dump({'urls': existing_entries}, f, indent=2, ensure_ascii=False)
                print(f"✓ Added {added_count} new URLs to final_urls.json")
            else:
                print("✓ No new URLs to add")
        else:
            # Create new file from urls.txt
            entries = [{'url': url, 'title': ''} for url in cleaned_new_urls]
            with open('final_urls.json', 'w', encoding='utf-8') as f:
                json.dump({'urls': entries}, f, indent=2, ensure_ascii=False)
            print(f"✓ Created final_urls.json with {len(entries)} URLs from urls.txt")
    elif not os.path.exists('final_urls.json'):
        # Neither file exists
        print("Neither final_urls.json nor urls.txt found.")
        with open('final_urls.json', 'w', encoding='utf-8') as f:
            json.dump({'urls': []}, f, indent=2)
        print("✓ Created empty final_urls.json")
        print("Please add URLs to the file and run again.")
        return
    
    # First, normalize all URLs in the JSON file
    normalize_urls_in_json()
    
    # Read URLs from JSON file
    with open('final_urls.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
        entries = data['urls']
    
    # Check if there are any URLs to process
    if not entries:
        print("No URLs found in final_urls.json. Please add URLs and run again.")
        return
    
    # Extract just the URLs for processing
    urls = [entry['url'] if isinstance(entry, dict) else entry for entry in entries]
    
    # Create screenshots folder if it doesn't exist
    if not os.path.exists('screenshots'):
        os.makedirs('screenshots')
    
    # Find the highest index already processed
    start_index = 0
    existing_files = os.listdir('screenshots')
    if existing_files:
        # Extract indices from filenames like "3_1.png"
        indices = []
        for filename in existing_files:
            if '_' in filename:
                try:
                    index = int(filename.split('_')[0])
                    indices.append(index)
                except:
                    continue
        
        if indices:
            start_index = max(indices)
            print(f"Found existing images up to index {start_index}")
            print(f"Resuming from index {start_index}...")
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Initialize the Chrome driver
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        # Iterate through URLs and download images, starting from start_index
        for index in range(start_index, len(urls)):
            url = urls[index]
            try:
                print(f"\nProcessing {index}/{len(urls)-1}: {url}")
                
                # Navigate to the URL
                driver.get(url)
                time.sleep(5)
                
                # Extract page title
                try:
                    page_title = driver.title
                    
                    # Split on both - and | to get all parts
                    import re
                    parts = re.split(r'[-|]', page_title)
                    
                    # Clean and strip all parts
                    parts = [p.strip() for p in parts]
                    
                    # Find valid title: must have digit, comma, >5 letters before and after comma
                    selected_title = ''
                    is_valid = False
                    for part in parts:
                        if not part:
                            continue
                        
                        # Check if part contains a digit
                        if not any(char.isdigit() for char in part):
                            continue
                        
                        # Check if part contains a comma
                        if ',' not in part:
                            continue
                        
                        # Split by comma
                        comma_parts = part.split(',')
                        if len(comma_parts) < 2:
                            continue
                        
                        before_comma = comma_parts[0].strip()
                        after_comma = comma_parts[1].strip()
                        
                        # Count alphabet characters before comma
                        alpha_before = sum(1 for c in before_comma if c.isalpha())
                        # Count alphabet characters after comma
                        alpha_after = sum(1 for c in after_comma if c.isalpha())
                        
                        # Must have >5 alphabet chars before and after comma
                        if alpha_before > 5 and alpha_after > 5:
                            selected_title = part
                            is_valid = True
                            break
                    
                    # If no valid title found, use whole title with <bad> flag
                    if not is_valid:
                        # Remove double spacing from the whole title
                        cleaned_title = re.sub(r'\s+', ' ', page_title).strip()
                        page_title = f"<bad>{cleaned_title}"
                        print(f"Title: {cleaned_title} (marked as bad)")
                    else:
                        page_title = selected_title.strip()
                        print(f"Title: {page_title}")
                    
                    # Update the entry in the data structure
                    entries[index]['title'] = page_title
                    
                    # Save to JSON immediately
                    try:
                        with open('final_urls.json', 'w', encoding='utf-8') as f:
                            json.dump({'urls': entries}, f, indent=2, ensure_ascii=False)
                    except Exception as save_error:
                        print(f"  Warning: Could not save title to JSON: {save_error}")
                except Exception as e:
                    print(f"Could not extract title: {str(e)}")
                
                # Find all images and get their dimensions
                images = driver.find_elements(By.TAG_NAME, 'img')
                
                # Filter images that meet minimum size requirements
                valid_images = []
                for img in images:
                    try:
                        src = img.get_attribute('src')
                        width = img.size['width']
                        height = img.size['height']
                        
                        # Check if image meets minimum size (400x600 or 600x400)
                        if src and ((width >= 400 and height >= 600) or (width >= 600 and height >= 400)):
                            img_url = urljoin(url, src)
                            
                            # Try to get file size via HEAD request
                            file_size = 0
                            try:
                                head_response = requests.head(img_url, timeout=5, allow_redirects=True, headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                })
                                content_length = head_response.headers.get('content-length')
                                if content_length:
                                    file_size = int(content_length)
                            except:
                                pass
                            
                            # Only add if file size is at least 120KB, or if we couldn't determine size
                            if file_size == 0 or file_size >= 120 * 1024:
                                area = width * height
                                valid_images.append({
                                    'src': src,
                                    'width': width,
                                    'height': height,
                                    'area': area,
                                    'file_size': file_size
                                })
                            else:
                                print(f"  Skipping: image too small ({file_size / 1024:.1f}KB)")
                    except:
                        continue
                
                # Sort by area (biggest first)
                valid_images.sort(key=lambda x: x['area'], reverse=True)
                
                print(f"Found {len(valid_images)} valid images (>= 400x600)")
                
                # Download unique images
                downloaded_hashes = set()
                saved_count = 0
                white_image_count = 0
                temp_images = []  # Store images temporarily before compression
                
                for img_info in valid_images:
                    if saved_count >= 4:
                        break
                    
                    try:
                        img_url = urljoin(url, img_info['src'])
                        
                        # Download the image
                        response = requests.get(img_url, timeout=10, headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        })
                        response.raise_for_status()
                        
                        # Get image content
                        img_content = response.content
                        
                        # Check file size (must be at least 120KB)
                        content_size = len(img_content)
                        if content_size < 120 * 1024:
                            print(f"  Skipping: downloaded file too small ({content_size / 1024:.1f}KB)")
                            continue
                        
                        # Check if image is duplicate
                        img_hash = get_image_hash(img_content)
                        if img_hash in downloaded_hashes:
                            print(f"  Skipping duplicate image")
                            continue
                        
                        # Check if image is mostly white
                        if is_image_mostly_white(img_content):
                            white_image_count += 1
                            # Only skip if we have other images or will have other images
                            # If this is our only chance and we have no saved images yet, keep it
                            if saved_count > 0 or (len(valid_images) - valid_images.index(img_info) > 1):
                                print(f"  Skipping: image is mostly white (>50%)")
                                continue
                            else:
                                print(f"  Warning: Keeping mostly-white image (only option available)")
                        
                        # Verify actual image dimensions
                        try:
                            img_obj = Image.open(BytesIO(img_content))
                            actual_width, actual_height = img_obj.size
                            
                            # Verify it meets minimum size requirements
                            if not ((actual_width >= 400 and actual_height >= 600) or 
                                   (actual_width >= 600 and actual_height >= 400)):
                                print(f"  Skipping: actual size {actual_width}x{actual_height} too small")
                                continue
                            
                            # Check if image is too square
                            if is_image_too_square(actual_width, actual_height):
                                # Only skip if we have other images or will have other images
                                if saved_count > 0 or (len(valid_images) - valid_images.index(img_info) > 1):
                                    aspect_ratio = max(actual_width, actual_height) / min(actual_width, actual_height)
                                    print(f"  Skipping: image too square (aspect ratio {aspect_ratio:.2f})")
                                    continue
                                else:
                                    print(f"  Warning: Keeping square image (only option available)")
                        except:
                            print(f"  Skipping: cannot verify image")
                            continue
                        
                        # Store image temporarily (will compress after collecting all images)
                        saved_count += 1
                        temp_images.append({
                            'content': img_content,
                            'width': actual_width,
                            'height': actual_height,
                            'original_size': content_size
                        })
                        
                        downloaded_hashes.add(img_hash)
                        print(f"  Collected: image {saved_count} ({actual_width}x{actual_height}, {content_size / 1024:.1f}KB)")
                        
                    except Exception as e:
                        print(f"  Error downloading image: {str(e)}")
                        continue
                
                # Now compress and save all collected images
                if temp_images:
                    target_size_per_image = 100 / len(temp_images)  # KB per image
                    print(f"\nCompressing {len(temp_images)} images (target: {target_size_per_image:.1f}KB each)...")
                    
                    for idx, img_data in enumerate(temp_images, 1):
                        compressed_content = compress_image(img_data['content'], target_size_per_image)
                        
                        # Save the compressed image
                        img_path = os.path.join('screenshots', f'{index}_{idx}.png')
                        with open(img_path, 'wb') as f:
                            f.write(compressed_content)
                        
                        compressed_size = len(compressed_content) / 1024
                        print(f"  Saved: {index}_{idx}.png ({img_data['width']}x{img_data['height']}, {compressed_size:.1f}KB)")
                
                print(f"Successfully saved {len(temp_images)} unique images for URL {index}")
                
            except Exception as e:
                print(f"Error processing {url}: {str(e)}")
                continue
    
    finally:
        # Close the browser
        driver.quit()
        
        # Save updated titles back to JSON
        try:
            with open('final_urls.json', 'w', encoding='utf-8') as f:
                json.dump({'urls': entries}, f, indent=2, ensure_ascii=False)
            print("\n✓ Saved updated titles to final_urls.json")
        except Exception as e:
            print(f"\n⚠ Could not save titles: {str(e)}")
    
    print(f"\nCompleted! Processed {len(urls)} URLs.")

if __name__ == "__main__":
    get_webpage_screenshot()
