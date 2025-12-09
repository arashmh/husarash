# 🏠 Husarash - Real Estate Image Scraper

A smart web scraper that extracts high-quality property images and titles from Danish real estate listings, with an elegant card-based display interface.

## ✨ Features

- **Intelligent Image Filtering** - Only downloads images meeting quality criteria (400×600px min, >120KB, proper aspect ratio)
- **Smart Title Extraction** - Validates titles with strict formatting rules and flags invalid ones
- **Duplicate Detection** - MD5 hashing prevents downloading the same image twice
- **Automatic Compression** - Optimizes images to ~100KB total per property
- **Resume Capability** - Continues from last processed URL
- **Interactive UI** - Modern card layout with Google Maps integration

## 🚀 Quick Start

```bash
# Install dependencies
pip install selenium pillow requests

# Add URLs to urls.txt (one per line)
echo "https://example.com/property1" > urls.txt

# Run the scraper
python get_webpage_screenshot.py

# Open the results
start index.html
```

## 📋 How It Works

1. **URL Processing** - Cleans URLs (removes query params, anchors) and deduplicates
2. **Title Extraction** - Validates titles must contain:
   - At least one digit
   - A comma separator
   - 5+ letters before and after comma
3. **Image Discovery** - Finds the 4 largest unique images per property
4. **Quality Filtering** - Rejects images that are:
   - Too small (<400×600px)
   - Too square (aspect ratio <1.3)
   - Mostly white (>50% white pixels)
   - Too small file size (<120KB)
5. **Smart Compression** - Distributes 100KB budget across all images
6. **Display** - Generates interactive cards with Google Maps integration

## 📂 Project Structure

```
husarash/
├── get_webpage_screenshot.py  # Main scraper script
├── index.html                 # Display interface
├── urls.txt                   # Input URLs (optional)
├── final_urls.json           # Processed URLs and titles
└── screenshots/              # Downloaded images
```

## 🎨 UI Features

- **Adaptive Layouts** - Handles 1-4 images per property gracefully
- **Google Maps Integration** - Click valid titles to search location
- **Visual Indicators** - Gradient badges show property index
- **Disabled States** - Invalid titles are non-clickable and dimmed

## 🔧 Configuration

Image quality thresholds in `get_webpage_screenshot.py`:
- `MIN_WIDTH = 400`, `MIN_HEIGHT = 600`
- `MIN_SIZE_BYTES = 120 * 1024`
- `MAX_SIZE_PER_URL = 100 * 1024`
- White pixel threshold: 50%
- Aspect ratio threshold: 1.3

## 📊 Data Format

`final_urls.json` structure:
```json
{
  "urls": [
    {
      "url": "https://cleaned-url.com",
      "title": "Street 123, City Name"
    },
    {
      "url": "https://another-url.com",
      "title": "<bad>Invalid Title Format"
    }
  ]
}
```

## 🛠️ Technologies

- **Python 3.x** - Core scripting
- **Selenium WebDriver** - Browser automation
- **Pillow** - Image processing
- **HTML/CSS/JS** - Frontend display

## 📝 License

MIT

---

Built with ❤️ for Danish real estate analysis
