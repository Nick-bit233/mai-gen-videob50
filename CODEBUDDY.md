# CODEBUDDY.md

This is a Streamlit-based Python application for automatically generating MaimaiDX Best 50 (B50) videos by searching and downloading gameplay videos from streaming platforms, then compositing them with score images.

## Development Commands

### Environment Setup
```bash
# Create conda environment (Python 3.10+ required)
conda create -n mai-gen-videob50 python=3.10
conda activate mai-gen-videob50

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Start the Streamlit web application
streamlit run st_app.py
```

### External Dependencies
- **FFmpeg**: Required for video processing. Must be installed and available in PATH or project root directory
- **Node.js**: Required for YouTube PO token generation (external_scripts/po_token_generator.js)

## Architecture Overview

### Core Application Structure
- **st_app.py**: Main Streamlit application entry point with navigation structure
- **st_pages/**: Streamlit page modules organized by workflow steps:
  - Homepage.py: Main landing page
  - Setup_Achievements.py: B50 data acquisition from score trackers
  - Generate_Pic_Resources.py: Score image generation
  - Search_For_Videos.py: Video search functionality
  - Confirm_Videos.py: Video download management
  - Edit_Video_Content.py: Video segment editing
  - Composite_Videos.py: Final video composition

### Utility Modules (utils/)
- **DataUtils.py**: Score data processing, metadata handling, song ID encoding
- **VideoUtils.py**: Video processing, text overlay, composition logic using MoviePy
- **video_crawler.py**: Multi-platform video downloading (YouTube, Bilibili) with authentication
- **ImageUtils.py**: Score image generation and processing
- **VisionUtils.py**: Computer vision utilities for video alignment
- **WebAgentUtils.py**: Web scraping and API interaction utilities
- **user_gamedata_handlers.py**: Score tracker integration (DivingFish, DXRating, Official NET)

### Data Flow Architecture
1. **Data Acquisition**: Fetch B50 scores from various trackers (DivingFish, DXRating, Official NET)
2. **Image Generation**: Create score images using templates and user data
3. **Video Search**: Search streaming platforms for gameplay videos matching each song
4. **Video Processing**: Download, crop, and prepare video segments
5. **Composition**: Combine images, videos, and user comments into final B50 video

### Configuration System
- **global_config.yaml**: Main configuration file controlling:
  - Video resolution, bitrate, transition settings
  - Download preferences (high resolution, proxy settings)
  - Platform-specific authentication tokens
  - Search parameters and timing controls

### Data Storage Structure

#### New SQLite Database System (Recommended)
- **mai_gen_videob50.db**: SQLite database containing:
  - users: User information and global settings
  - save_archives: Save archives (replaces timestamp folders)
  - records: Individual song records with progress tracking
  - video_configs: Video configuration for each record
  - video_search_results: Search results from streaming platforms
  - project_configs: Intro/ending and global video settings
  - assets: Asset tracking (images, videos, etc.)

#### Legacy JSON Structure (For Migration)
- **b50_datas/{user}/{timestamp}/**: User save archives containing:
  - b50_raw.json: Raw score data with metadata
  - b50_config_{platform}.json: Video search results and mappings
  - video_config.json: User comments, timing, and rendering configuration
  - images/: Generated score images
  - videos/: Output video files
- **videos/downloads/**: Downloaded gameplay videos cached by song ID and difficulty

#### Database Migration
```bash
# Scan existing JSON data
python test_migrate_database.py --scan-only

# Run test migration
python test_migrate_database.py --db-path test_migration.db

# Full migration with backup
python migrate_to_database.py
```

### Multi-Platform Integration
- **Score Trackers**: DivingFish Prober, DXRating, Official MaimaiDX NET (International/Japan)
- **Video Sources**: YouTube (with PO token support), Bilibili (with credential management)
- **Authentication**: Handles login flows, token management, and anti-bot measures

### Video Processing Pipeline
- Uses MoviePy for video composition with custom text overlays
- Supports multiple themes (FES, Buddies, Prism) with customizable assets
- Implements video alignment using computer vision to match templates
- Handles video transitions, intro/outro segments, and batch processing

### Key Technical Features
- **Database System**: SQLite-based storage with song progress tracking across multiple archives
- **Async Operations**: Video downloading and API calls use asyncio for performance
- **Caching System**: Intelligent caching of images, videos, and metadata to avoid re-processing
- **Error Handling**: Comprehensive error handling for network issues, video corruption, and API limits
- **Backward Compatibility**: New database system maintains compatibility with existing JSON-based code
- **Data Migration**: Automated migration tools from JSON to SQLite with verification
- **Internationalization**: Support for multiple regions and character encodings

### Database Usage Examples
```python
# New database system
from utils.DatabaseDataHandler import DatabaseDataHandler
handler = DatabaseDataHandler()

# Save/load data (same interface as before)
handler.save_b50_data("username", b50_data)
data = handler.load_b50_data("username")

# New features: song progress tracking
from utils.DatabaseManager import DatabaseManager
db = DatabaseManager()
user = db.get_user("username")
history = db.get_song_history(user['id'], song_id="833", chart_type="DX", level_index=4)

# Backward compatibility functions
from utils.DatabaseDataHandler import load_user_data, save_user_data
data = load_user_data("username")  # Works with existing code
```