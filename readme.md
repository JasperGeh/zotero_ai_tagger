# Zotero AI Tagger

An intelligent tagging assistant for Zotero libraries that uses Claude AI to automatically generate and maintain consistent tags across your references. The script can process multiple content sources including abstracts, PDFs, and linked webpages to generate relevant tags for your library items.

## Features

- 🤖 Uses Claude AI for intelligent tag generation
- 📚 Maintains consistency with existing tags
- 📑 Can process multiple content sources:
  - Document abstracts
  - PDF attachments
  - Linked URLs/webpages
- 📝 Maintains a master list of tags
- 🔄 Preserves existing item tags
- 📊 Detailed logging of all operations

## Prerequisites

- Python 3.8+
- Zotero API key ([How to get one](https://www.zotero.org/settings/keys))
- Claude API key from Anthropic ([Get API key](https://docs.anthropic.com/claude/docs/getting-access-to-claude))
- For group libraries: Group Library ID (found in the URL when viewing the group)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/jaspergeh/zotero-ai-tagger.git
cd zotero-ai-tagger
```

2. Create and activate a virtual environment (recommended):
```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

## Configuration

Set up your environment variables:

```bash
# Linux/macOS
export ZOTERO_LIBRARY_ID="your_library_id"
export ZOTERO_LIBRARY_TYPE="group"  # or "user"
export ZOTERO_API_KEY="your_zotero_api_key"
export ANTHROPIC_API_KEY="your_anthropic_api_key"

# Windows (PowerShell)
$env:ZOTERO_LIBRARY_ID="your_library_id"
$env:ZOTERO_LIBRARY_TYPE="group"
$env:ZOTERO_API_KEY="your_zotero_api_key"
$env:ANTHROPIC_API_KEY="your_anthropic_api_key"
```

## Usage

The script provides several command-line options to control its behavior:

```bash
python zotero_tagger.py [-h] [-u] [-U] [-p] [-t TAGS_FILE] [-l LIMIT]

options:
  -h, --help            Show this help message and exit
  -u, --url-fallback    Look up URL only when no PDF is attached
  -U, --url-always      Always look up URL content
  -p, --parse-pdf       Parse PDF attachments
  -t TAGS_FILE, --tags-file TAGS_FILE
                        Path to text file with existing tags (one per line)
  -l LIMIT, --limit LIMIT
                        Limit number of items to process
```

### Example Commands

1. Process everything (PDFs and URLs) with existing tags:
```bash
python zotero_tagger.py -p -U -t tags.txt
```

2. Use PDFs primarily, fall back to URLs when no PDF exists:
```bash
python zotero_tagger.py -p -u -t tags.txt
```

3. Test run with only URLs (no PDFs) and process just 5 items:
```bash
python zotero_tagger.py -U -t tags.txt -l 5
```

### Tags File Format

The tags file should be a plain text file with one tag per line:
```text
LLM jailbreaking
LLM evals
biosecurity
unlearning
protein design
```

The script will:
- Load existing tags from this file
- Add any new tags generated during processing
- Keep the file sorted alphabetically
- Save updates after each new tag is generated

## Logging

The script logs all operations to both console and `zotero_tagger.log`. The log includes:
- Items being processed
- Content sources used
- Suggested and existing tags
- Any errors or warnings

Monitor the log in real-time:
```bash
tail -f zotero_tagger.log
```

## Best Practices

1. **Start Small**
   - Do a test run with a small number of items first
   - Review the generated tags before processing your entire library

2. **Back Up Your Tags**
   ```bash
   cp tags.txt tags_backup.txt
   ```

3. **Monitor the Process**
   - Keep an eye on the log file
   - Check the first few items to ensure tags are being generated as expected

4. **Tag File Maintenance**
   - Review and clean up your tags file periodically
   - Remove any unwanted or duplicate tags
   - Keep backups of your tags file

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to Anthropic for the Claude API
- Thanks to the Zotero team for their excellent reference manager and API
- All contributors and users of this tool

## Support

If you encounter any issues or have questions:
1. Check the existing issues on GitHub
2. Open a new issue with:
   - A description of the problem
   - Your command line arguments
   - Relevant log output
   - Any error messages

---
**Note**: This tool is not officially affiliated with either Zotero or Anthropic.