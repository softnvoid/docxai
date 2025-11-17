# CLAUDE.md - AI Assistant Guide for DocxAI

## Project Overview

**DocxAI** is a Python-based intelligent document processing tool that:
- Extracts text from `.docx` documents (paragraphs and tables)
- Processes text through YandexGPT API for AI-powered modifications
- Highlights changes in the output document (green highlighting)
- Supports PDF to DOCX conversion before processing
- Preserves original document formatting while applying modifications

**Primary Use Case**: Automated document translation, correction, and modification with visible change tracking.

---

## Codebase Structure

```
/home/user/docxai/
├── src/                          # Source code directory
│   ├── docxai_process.py        # Main processing logic and AI integration
│   ├── save_formatting.py       # Text formatting preservation utilities
│   └── utilites.py              # Helper functions (env loading)
├── default_instruction.txt       # Default system instruction for AI
├── default_prompt.txt           # Default user prompt template
├── .env.example                 # Environment variable template
├── .gitignore                   # Git ignore rules
├── pyproject.toml              # Python project configuration (uv/pip)
├── requirenments.txt           # Legacy requirements file (note typo)
├── README.md                   # User-facing documentation
└── .python-version             # Python version specification
```

**Generated Files** (gitignored):
- `instruction.txt` - Active system instruction (created from default)
- `prompt.txt` - Active user prompt (created from default)
- `test.docx` - Input document for processing
- `test-<random-name>.docx` - Output document with highlighted changes

---

## Tech Stack

### Core Technologies
- **Python**: 3.12+ (see `.python-version`)
- **Package Manager**: uv (modern) or pip (legacy)
- **Document Processing**: `python-docx` (0.8.10+)
- **PDF Conversion**: `pdf2docx` (0.5.8+)
- **AI Integration**: YandexGPT API via `requests`
- **Utilities**: `coolname` for random file naming

### Dependencies
```toml
# From pyproject.toml
coolname>=2.2.0
openai>=1.65.4          # Listed but not actively used in current code
pdf2docx>=0.5.8
python-docx>=1.1.2
requests>=2.32.3
```

---

## Core Architecture

### Processing Flow

1. **File Input** → `file_process()` (src/docxai_process.py:50)
   - Validates file format (.docx or .pdf)
   - Converts PDF to DOCX if needed
   - Passes to main AI processor

2. **Document Parsing** → `make_paragraphs_dict()`, `make_tables_dict()`
   - Extracts all paragraphs into numbered dictionary
   - Extracts table cells into nested dictionary structure
   - Preserves indexing for later reconstruction

3. **AI Processing** → `func_yandexgpt()`, `yandex_gpt_tables()`
   - Chunks text into groups of 7 items (prevents API overload)
   - Sends JSON-formatted chunks to YandexGPT
   - Validates JSON response structure
   - Retries up to 4 times on failure

4. **Change Detection** → `find_changes_generator()` (src/docxai_process.py:221)
   - Token-level comparison between original and modified text
   - Marks changed tokens with `###` prefix
   - Yields tokens for highlighting

5. **Document Reconstruction** → `write_changes_paragraph()`, `write_changes_table()`
   - Applies modified text back to document
   - Preserves original formatting via `copy_style()`/`apply_style()`
   - Highlights changes with `WD_COLOR_INDEX.BRIGHT_GREEN`

6. **Output** → Saves to new file with random name

---

## Key Components

### 1. `src/docxai_process.py` (Main Module)

**Critical Functions:**

- `pdf_converter(pdf_path)` (line 37)
  - Converts PDF to DOCX using pdf2docx library
  - Returns new DOCX path with random name
  - TODO: Improve error handling (line 43)

- `file_process(file_path)` (line 50)
  - Entry point for document processing
  - Handles both .docx and .pdf files
  - Returns path to processed file

- `send_prompt(chunk, PROMPT, INSTRUCTION, token, folder_id)` (line 274)
  - Sends individual chunk to YandexGPT API
  - Retries 4 times on failure
  - Validates JSON structure of response
  - **Important**: Uses hardcoded model URI (line 282)

- `func_yandexgpt(input_dict)` (line 341)
  - Processes paragraph dictionaries through AI
  - Chunks into groups of 7 items
  - Concatenates responses back into single JSON

- `yandex_gpt_tables(input_dict)` (line 376)
  - Similar to `func_yandexgpt` but for table structures
  - Handles nested dictionary structure

**AI Prompt Structure:**
```python
YANDEX_PRE_PROMPT + get_prompt() + YANDEX_POST_PROMPT
```
- Pre-prompt: Instructs AI to work with JSON and preserve structure
- User prompt: From `prompt.txt` (default: translate to English)
- Post-prompt: Strict JSON formatting instructions

### 2. `src/save_formatting.py`

- `copy_style(run)` - Extracts all font attributes from a text run
- `apply_style(run, style)` - Reapplies captured style to new run
- **Purpose**: Ensures formatting consistency when modifying text

### 3. `src/utilites.py`

- `load_env()` - Simple .env file parser (no external library)
- Returns dictionary of environment variables

---

## Configuration

### Environment Variables (.env)

**Required:**
```bash
YANDEXGPT_TOKEN=<your_api_key>     # YandexGPT API key
FOLDER_ID=<your_folder_id>         # Yandex Cloud folder ID
```

**Optional (in .env.example but not used in current code):**
```bash
tgbot_token=                       # Telegram bot integration (future?)
openai_token=                      # OpenAI integration (future?)
```

### AI Configuration Files

**`instruction.txt`** (System Role):
- Default: Russian instructions for JSON processing
- Tells AI to preserve JSON structure and indexes
- Auto-created from `default_instruction.txt` on first run

**`prompt.txt`** (User Task):
- Default: "Переведи весь текст на английский язык" (Translate all text to English)
- Auto-created from `default_prompt.txt` on first run
- Modifiable by user for different tasks

---

## Development Workflow

### Setup

```bash
# Clone repository
git clone <repository_url>
cd docxai

# Install dependencies (modern approach with uv)
uv pip install -e .

# Or legacy approach
pip install -r requirenments.txt  # Note: typo in filename

# Configure environment
cp .env.example .env
# Edit .env with your YandexGPT credentials
```

### Running the Application

```bash
# Place your document as test.docx in project root
cp /path/to/your/document.docx test.docx

# Run processing
python -m src.docxai_process
# Or
python src/docxai_process.py
```

**Output**: New file `test-<random-name>.docx` with highlighted changes

### Git Workflow

**Current Branch**: `claude/claude-md-mi3s10gfvyuj1uyi-014GhNSwgd5vtVYtvL6pYG4Y`

**Important**:
- Always develop on feature branches starting with `claude/`
- Branch names should match session ID pattern
- Use descriptive commit messages
- Push with `git push -u origin <branch-name>`

---

## Code Conventions

### Naming Conventions

- **Functions**: `snake_case` (e.g., `file_process`, `make_paragraphs_dict`)
- **Variables**: `snake_case` (e.g., `new_file_path`, `json_strings`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `YANDEXGPT_TOKEN`, `YANDEX_PRE_PROMPT`)
- **Module Names**: `snake_case` (e.g., `docxai_process.py`)

### Patterns Used

1. **Dictionary-based Data Flow**
   - Documents converted to nested dictionaries
   - Preserves structure through processing pipeline
   - Easy JSON serialization for API calls

2. **Generator Pattern**
   - `find_changes_generator()` yields tokens lazily
   - Memory-efficient for large documents

3. **Retry Logic**
   - 4 retry attempts with 2-second delays
   - Applied to API calls (line 291-330)

4. **Chunking Strategy**
   - Documents split into 7-item chunks
   - Prevents API token limits
   - Results concatenated back together

### Logging

- Uses Python `logging` module
- Levels: `info`, `warning`, `error`
- Key logged events:
  - Document processing start/end
  - API response status
  - JSON validation failures
  - Original vs modified text comparison

---

## AI Integration Details

### YandexGPT API

**Endpoint**: `https://llm.api.cloud.yandex.net/foundationModels/v1/completion`

**Model**: `yandexgpt-pro` (hardcoded in line 282)

**Parameters**:
```json
{
  "temperature": 0.6,
  "maxTokens": "1000",
  "stream": false
}
```

**Request Format**:
```json
{
  "modelUri": "gpt://b1gr06ae9rrolg6nf1c4/yandexgpt-pro",
  "completionOptions": {...},
  "messages": [
    {"role": "system", "text": "<instruction>"},
    {"role": "assistant", "text": "<prompt>"},
    {"role": "user", "text": "<json_chunk>"}
  ]
}
```

**Response Parsing**:
- Extracts: `response["result"]["alternatives"][0]["message"]["text"]`
- Strips markdown code fences: `` `json `` and backticks
- Validates all keys from original JSON are present
- Retries if validation fails

---

## Common Tasks for AI Assistants

### 1. Adding New Document Format Support

**Files to modify**: `src/docxai_process.py:file_process()`

Add new format handler:
```python
elif file_path.endswith(".rtf"):
    # Add RTF conversion logic
    new_file_path = rtf_converter(file_path)
```

### 2. Changing AI Provider (e.g., OpenAI instead of YandexGPT)

**Files to modify**:
- `src/docxai_process.py:send_prompt()` (line 274)
- Update API endpoint, headers, request format
- Modify response parsing logic

**Note**: OpenAI dependency already in pyproject.toml

### 3. Modifying Chunk Size

**Location**: `src/docxai_process.py:342, 382`

Change `chunk_size = 7` to desired value. Considerations:
- Larger chunks = fewer API calls but risk token limit
- Smaller chunks = more API calls but safer

### 4. Customizing Change Highlighting

**Location**: `src/docxai_process.py:118, 122, 183, 189`

Change `WD_COLOR_INDEX.BRIGHT_GREEN` to other colors:
- `WD_COLOR_INDEX.YELLOW`
- `WD_COLOR_INDEX.TURQUOISE`
- `WD_COLOR_INDEX.PINK`
- etc.

### 5. Adding Logging/Debugging

Add logging statements:
```python
import logging
logging.info("Your message here")
logging.warning("Warning message")
logging.error("Error message")
```

Configure logging level in main:
```python
logging.basicConfig(level=logging.DEBUG)
```

### 6. Error Handling Improvements

**Known TODOs**:
- Line 43: Improve PDF converter exception handling
- General: Add specific exception types instead of bare `except:`
- Add user-friendly error messages

---

## Important Notes

### ⚠️ Known Issues

1. **Typo in requirements file**: `requirenments.txt` should be `requirements.txt`
   - pyproject.toml is the source of truth

2. **Hardcoded Model URI**: Line 282 contains hardcoded YandexGPT folder ID
   - Should be extracted to environment variable

3. **Bare Exception Handlers**: Multiple `except:` without specific types
   - Can hide bugs and make debugging difficult

4. **File Path Hardcoded**: `main()` function processes `test.docx` only
   - Should accept command-line arguments

5. **OpenAI Dependency Unused**: Listed in pyproject.toml but not imported
   - May indicate planned feature or leftover dependency

### Security Considerations

1. **API Keys**: Never commit `.env` file (properly gitignored)
2. **Input Validation**: No validation of document content before API send
3. **Injection Risks**: User-controlled prompts sent to AI without sanitization

### Performance Notes

1. **Chunking**: 7-item chunks with 2-second delays between requests
   - Large documents will take significant time
   - Example: 100 paragraphs = ~15 chunks = ~30+ seconds minimum

2. **Retry Logic**: 4 retries with 2-second delays = up to 8 seconds per failed chunk

3. **Memory**: Entire document loaded into memory
   - May struggle with very large files

### Testing

**Current Status**: No automated tests present

**Manual Testing**:
```bash
# Create a simple test document
# Run processing
python src/docxai_process.py
# Verify output file exists with correct highlighting
```

---

## Git Ignore Patterns

Key gitignored items:
- `.env` - Environment variables (secrets)
- `venv/`, `openai-env/` - Virtual environments
- `instruction.txt`, `prompt.txt` - User-specific configurations
- `__pycache__/` - Python bytecode
- `archive/`, `tmp/`, `notes/` - Working directories
- `*.code-workspace` - IDE configurations

---

## Future Improvements (Suggestions)

1. **CLI Interface**: Add argparse for file path, output path, config selection
2. **Batch Processing**: Process multiple files in one run
3. **Progress Indicators**: Add tqdm or similar for long operations
4. **Test Suite**: Add pytest tests for core functions
5. **Error Recovery**: Save partial progress on failure
6. **Async Processing**: Use async/await for API calls
7. **Multiple AI Providers**: Abstract AI interface for easy switching
8. **Web Interface**: Consider Flask/FastAPI frontend
9. **Docker Support**: Add Dockerfile for consistent environment

---

## Quick Reference

### Environment Setup
```bash
uv pip install -e .
cp .env.example .env
# Edit .env with credentials
```

### Run Processing
```bash
python src/docxai_process.py
```

### Key Files to Modify
- AI logic: `src/docxai_process.py`
- Formatting: `src/save_formatting.py`
- Utilities: `src/utilites.py`
- Prompts: `default_prompt.txt`, `default_instruction.txt`

### Key Constants
- Chunk size: Line 347, 382 in docxai_process.py
- Retry count: Line 291 in docxai_process.py
- Highlight color: Lines 118, 122, 183, 189 in docxai_process.py

---

**Last Updated**: 2025-11-17
**Python Version**: 3.12+
**Primary Maintainer**: See git history
