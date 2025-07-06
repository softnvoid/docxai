# DocxAI: Intelligent Document Processing

DocxAI is a Python script for the automated processing and modification of .docx documents. It extracts text from paragraphs and tables, sends it to YandexGPT for modifications according to specified instructions, and then creates a new document with the changes highlighted. Conversion from .pdf to .docx is also supported.

🚀 **Key Features**

  * **Docx File Processing:** Reads text from paragraphs and tables.
  * **YandexGPT Integration:** Sends text for processing using the YandexGPT API.
  * **Configurable Instructions:** Allows setting custom instructions for the model via `prompt.txt` and `instruction.txt` files.
  * **Highlighting Changes:** Changes made by the AI are highlighted in green in the final document.
  * **PDF Conversion:** Automatically converts .pdf files to .docx before processing.
  * **Formatting Preservation:** The script attempts to preserve the original text formatting.
  * **Segmented Processing:** Long documents are split into parts before being sent to the API.

⚙️ **Installation**

**Clone the repository:**

```bash
git clone <URL of repository>
cd <folder name>
```

**Install dependencies:**

```bash
pip install -r requirements.txt
```

**`requirements.txt` content:**

```
requests
python-docx
pdf2docx
coolname
```

**Configure environment variables:**

Create a `.env` file in the project's root directory and add your Yandex Cloud credentials:

```
YANDEXGPT_TOKEN=Your_API_key
FOLDER_ID=Your_folder_ID
```

📝 **Usage**

**Configure AI instructions:**

  * **`instruction.txt`:** System instruction for YandexGPT. Defines the role and general guidelines for the AI.
  * **`prompt.txt`:** The main prompt that will be applied to the document text.

Upon the first run, the script will automatically create `prompt.txt` and `instruction.txt` files with content from `docxai/default_prompt.txt` and `docxai/default_instruction.txt`. You can modify these files for your tasks.

**Place the file for processing in the project root.**

Currently, the script is configured to process a file named `test.docx`. You can change this in the `main()` function.

**Run the script:**

```bash
python main.py
```

**Get the result.**

The processed file will be saved with a new, randomly generated name (e.g., `test-possible-wombat.docx`) in the same directory. Changes in the text will be highlighted.

