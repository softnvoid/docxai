import time
import logging
import json
import requests

from coolname import generate_slug
from pdf2docx import Converter

from docx import Document
from docx.enum.text import WD_COLOR_INDEX

# Handle both relative and absolute imports for flexibility
try:
    from .save_formatting import copy_style, apply_style
    from .utilites import load_env
except ImportError:
    from save_formatting import copy_style, apply_style
    from utilites import load_env


# Lazy loading of environment variables - loaded when first accessed
env_vars = None
YANDEXGPT_TOKEN = None
FOLDER_ID = None


def _ensure_env_loaded():
    """Ensure environment variables are loaded. Called before first use."""
    global env_vars, YANDEXGPT_TOKEN, FOLDER_ID
    if env_vars is None:
        env_vars = load_env()
        YANDEXGPT_TOKEN = env_vars.get("yandexgpt_token", "")
        FOLDER_ID = env_vars.get("folder_id", "")
        if not YANDEXGPT_TOKEN or not FOLDER_ID:
            logging.warning("YandexGPT credentials not found in .env file")


YANDEX_PRE_PROMPT = """\n
Ты — ИИ-помощник, тебе на вход приходит JSON файл, ты должен изменить его в соответствии со следующими правилами и инструкциями:
0. Проанализировать загруженный текст формата json. В тексте каждого элемента json при необходимости выполнить следующие действия (не меняя структуру json файла).
"""

YANDEX_POST_PROMPT = """\n
В конце - выведи изменённый текст так же в формате json, сохранив всю структуру, количество элементов и нумерацию.
Дополнение к инструкциям. Очен важно:
- Выведи изменённый текст так же в формате json, сохранив всю структуру, количество элементов и нумерацию.
- Не удаляй лишнее из оригинала. Изменениям должны подвергнуться лишь неопределенности. Все четко-определенные элементы должны остаться в том же виде в котором были.
- Не удаляй все НЕ буквенные символы, даже если элемент json целиком состоит из них. Например: "10": "__________" должна так и остаться "10": "__________".
- Обязательно в финальном тексте должен быть абсолютно весь текст из оригинального тексте с учётом корректировок и ничего дополнительно писать не надо.
- Ответ нужно предоставить в JSON формате без каких либо комментариев вначале и без каких либо комментариев в конце. Только JSON, начинается с "{" заканчивается "}".
"""


def pdf_converter(pdf_path) -> str:
    """Convert PDF file to DOCX format.

    Args:
        pdf_path: Path to PDF file

    Returns:
        str: Path to converted DOCX file, empty string on failure
    """
    docx_path = pdf_path.replace(".pdf", f"-{generate_slug(2)}.docx")
    try:
        c = Converter(pdf_path)
        c.convert(docx_path)
        c.close()
        logging.info(f"PDF converted successfully: {pdf_path} -> {docx_path}")
        return docx_path
    except FileNotFoundError as e:
        logging.error(f"PDF file not found: {pdf_path} - {e}")
        return ""
    except Exception as e:
        logging.error(f"PDF conversion failed for {pdf_path}: {e}")
        return ""


def file_process(file_path) -> str:
    """Process a document file (.docx or .pdf) through AI pipeline.

    Args:
        file_path: Path to input file (.docx or .pdf)

    Returns:
        str: Path to processed output file, empty string on failure
    """
    import os

    # Validate file exists
    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return ""

    if file_path.endswith(".docx"):
        # Process DOCX file
        new_file_path = file_path.replace(".docx", f"-{generate_slug(2)}.docx")
        logging.info(f"Document processing started: {file_path} -> {new_file_path}")

        try:
            # Open and parse document
            with open(file_path, "rb") as f:
                doc = Document(f)

            # Process through AI pipeline
            new_file_path = main_process_ai(doc, new_file_path)
            logging.info(f"Document processing completed: {new_file_path}")
            return new_file_path
        except Exception as e:
            logging.error(f"Failed to process DOCX file {file_path}: {e}")
            return ""

    elif file_path.endswith(".pdf"):
        # Convert PDF to DOCX first
        logging.info(f"PDF conversion started: {file_path}")
        new_file_path = pdf_converter(file_path)

        if not new_file_path:
            logging.error(f"PDF conversion failed: {file_path}")
            return ""

        # TODO: Implement PDF processing after conversion
        # Currently PDF processing is not fully implemented
        logging.warning("PDF processing after conversion is not yet implemented")
        return new_file_path

    else:
        # Unsupported format
        logging.error(f"Unsupported file format: {file_path}")
        return ""


def make_paragraphs_dict(doc_paragraphs: list) -> dict:
    """Convert list of paragraphs to indexed dictionary.

    Args:
        doc_paragraphs: List of paragraph objects from document

    Returns:
        dict: Dictionary mapping index to paragraph text
    """
    json_dicts = dict()
    for i in range(len(doc_paragraphs)):
        json_dicts[i] = doc_paragraphs[i].text
    return json_dicts


def make_tables_dict(doc) -> dict:
    """Convert document tables to nested dictionary structure.

    Creates a nested dict: table_index -> cell_index -> paragraph_index -> text

    Args:
        doc: Document object containing tables

    Returns:
        dict: Nested dictionary with table structure and content
    """
    table_dict = dict()
    for i in range(len(doc.tables)):
        table_dict[i] = {}
        for j in range(len(doc.tables[i].table._cells)):
            # Extract all paragraphs from this cell
            table_dict[i][j] = make_paragraphs_dict(
                doc.tables[i].table._cells[j].paragraphs
            )
    return table_dict


def write_changes_paragraph(doc, paragraph_dict_modified: dict):
    """Apply modified text to document paragraphs with highlighting.

    Args:
        doc: Document object
        paragraph_dict_modified: Dictionary with modified paragraph texts
    """
    for i in range(len(doc.paragraphs)):
        # Skip if no modification or text is the same
        if not paragraph_dict_modified.get(str(i)) or (
            paragraph_dict_modified[str(i)] == doc.paragraphs[i].text
        ):
            continue

        # Check if paragraph has runs, if not create one
        if len(doc.paragraphs[i].runs) == 0:
            doc.paragraphs[i].add_run()

        runs_amount = len(doc.paragraphs[i].runs)
        run_number = -1
        mod_flag = True

        tmp_original_text = doc.paragraphs[i].text
        # Clear existing text
        for n in range(len(doc.paragraphs[i].runs)):
            doc.paragraphs[i].runs[n].text = ""

        # Copy style from first run
        style = copy_style(doc.paragraphs[i].runs[0])

        logging.info(f"original text: {tmp_original_text}")
        logging.info(f"modified text: {paragraph_dict_modified[str(i)]}")

        # Apply changes with highlighting
        for word in find_changes_generator(
            tmp_original_text, paragraph_dict_modified[str(i)]
        ):
            if word.startswith("###"):
                # Modified word - highlight in green
                if not mod_flag or run_number == -1:
                    run_number += 1
                    mod_flag = True
                if run_number >= runs_amount:
                    doc.paragraphs[i].add_run()
                    apply_style(doc.paragraphs[i].runs[run_number], style)
                    doc.paragraphs[i].runs[
                        run_number
                    ].font.highlight_color = WD_COLOR_INDEX.BRIGHT_GREEN
                doc.paragraphs[i].runs[run_number].text += f"{word} "[3:]
                doc.paragraphs[i].runs[
                    run_number
                ].font.highlight_color = WD_COLOR_INDEX.BRIGHT_GREEN
            else:
                # Original word - no highlight
                if mod_flag or run_number == -1:
                    run_number += 1
                    mod_flag = False
                if run_number >= runs_amount:
                    doc.paragraphs[i].add_run()
                    apply_style(doc.paragraphs[i].runs[run_number], style)
                doc.paragraphs[i].runs[run_number].text += f"{word} "


def write_changes_table(doc, table_dict_modified: dict):
    """Apply modified text to document tables with highlighting.

    Args:
        doc: Document object
        table_dict_modified: Dictionary with modified table cell texts
    """
    for i in range(len(doc.tables)):
        # Skip if table not in modifications
        if i not in table_dict_modified:
            continue

        for j in range(len(doc.tables[i].table._cells)):
            for n in range(len(doc.tables[i].table._cells[j].paragraphs)):
                # Skip if no modification or text is the same
                if (
                    not table_dict_modified[i].get(str(j))
                    or not table_dict_modified[i][str(j)].get(str(n))
                    or (
                        table_dict_modified[i][str(j)][str(n)]
                        == doc.tables[i].table._cells[j].paragraphs[n].text
                    )
                ):
                    continue

                # Check if paragraph has runs, if not create one
                if len(doc.tables[i].table._cells[j].paragraphs[n].runs) == 0:
                    doc.tables[i].table._cells[j].paragraphs[n].add_run()

                runs_amount = len(doc.tables[i].table._cells[j].paragraphs[n].runs)
                run_number = -1
                mod_flag = True

                tmp_original_text = doc.tables[i].table._cells[j].paragraphs[n].text

                # Clear existing text
                for r in range(
                    len(doc.tables[i].table._cells[j].paragraphs[n].runs)
                ):
                    doc.tables[i].table._cells[j].paragraphs[n].runs[r].text = ""

                # Copy style from first run
                style = copy_style(
                    doc.tables[i].table._cells[j].paragraphs[n].runs[0]
                )

                logging.info(f"original text: {tmp_original_text}")
                logging.info(
                    f"modified text: {table_dict_modified[i][str(j)][str(n)]}"
                )

                # Apply changes with highlighting
                for word in find_changes_generator(
                    str(tmp_original_text),
                    str(table_dict_modified[i][str(j)][str(n)]),
                ):
                    if word.startswith("###"):
                        # Modified word - highlight in green
                        if not mod_flag or run_number == -1:
                            run_number += 1
                            mod_flag = True
                        if run_number >= runs_amount:
                            doc.tables[i].table._cells[j].paragraphs[n].add_run()
                            apply_style(
                                doc.tables[i]
                                .table._cells[j]
                                .paragraphs[n]
                                .runs[run_number],
                                style,
                            )
                            doc.tables[i].table._cells[j].paragraphs[n].runs[
                                run_number
                            ].font.highlight_color = WD_COLOR_INDEX.BRIGHT_GREEN
                        doc.tables[i].table._cells[j].paragraphs[n].runs[
                            run_number
                        ].text += f"{word} "[3:]
                        doc.tables[i].table._cells[j].paragraphs[n].runs[
                            run_number
                        ].font.highlight_color = WD_COLOR_INDEX.BRIGHT_GREEN
                    else:
                        # Original word - no highlight
                        if mod_flag or run_number == -1:
                            run_number += 1
                            mod_flag = False
                        if run_number >= runs_amount:
                            doc.tables[i].table._cells[j].paragraphs[n].add_run()
                            apply_style(
                                doc.tables[i]
                                .table._cells[j]
                                .paragraphs[n]
                                .runs[run_number],
                                style,
                            )
                        doc.tables[i].table._cells[j].paragraphs[n].runs[
                            run_number
                        ].text += f"{word} "


def main_process_ai(doc, new_file_path_name):
    """Main AI processing pipeline for document.

    Args:
        doc: Document object
        new_file_path_name: Path to save modified document

    Returns:
        str: Path to saved file
    """
    # Extract paragraphs and process through AI
    paragraph_dict = make_paragraphs_dict(doc.paragraphs)
    paragraph_dict_modified = func_yandexgpt(paragraph_dict)

    # Extract tables and process through AI
    table_dict = make_tables_dict(doc)
    table_dict_modified = yandex_gpt_tables(table_dict)

    # Apply changes to document
    write_changes_paragraph(doc, paragraph_dict_modified)
    write_changes_table(doc, table_dict_modified)

    # Save modified document
    doc.save(new_file_path_name)
    logging.info(f"Document saved successfully: {new_file_path_name}")
    return new_file_path_name


def find_changes_generator(text_1, text_2):
    """Generator that compares two texts and marks changed words.

    Yields words from text_2, prefixing changed words with '###'.

    Args:
        text_1: Original text
        text_2: Modified text

    Yields:
        str: Words from text_2, with '###' prefix for changes
    """
    tokens_1 = text_1.split(" ")
    tokens_2 = text_2.split(" ")
    length_1 = len(tokens_1)
    length_2 = len(tokens_2)

    # Handle empty texts
    if length_1 == 0 or length_2 == 0:
        for token in tokens_2:
            yield "###" + token
        return

    index_or = 0  # Index in original text
    index_mod = 0  # Index in modified text
    iteration = 0  # Counter for consecutive modifications
    flag = True  # Flag to track if we found a match

    while index_mod < length_2:
        # Protect against index out of bounds
        if index_or >= length_1:
            # Rest of modified text is new
            yield "###" + tokens_2[index_mod]
            index_mod += 1
            continue

        if tokens_1[index_or] != tokens_2[index_mod]:
            # Words don't match - search for match in remaining original text
            flag = True
            for tmp_index in range(index_or, length_1):
                if tokens_1[tmp_index] == tokens_2[index_mod]:
                    index_or = tmp_index
                    flag = False
                    if iteration == 0:
                        yield "###" + tokens_2[index_mod]
                    else:
                        yield tokens_2[index_mod]
                    break

            if flag:
                # No match found - this is a new/changed word
                yield "###" + tokens_2[index_mod]
                index_mod += 1
                iteration += 1
        else:
            # Words match - this is unchanged text
            if flag:
                yield tokens_2[index_mod]
            index_mod += 1
            if index_or < length_1 - 1:
                index_or += 1
            flag = True
            iteration = 0


def get_prompt() -> str:
    """Read user prompt from prompt.txt file.

    Returns:
        str: Prompt text, empty string on error
    """
    try:
        with open("prompt.txt", "r", encoding="utf-8") as file:
            prompt = file.read()
            return prompt
    except FileNotFoundError:
        logging.error("prompt.txt file not found. Run init_instruction() first.")
        return ""
    except Exception as e:
        logging.error(f"Failed to read prompt: {e}")
        return ""


def get_instruction() -> str:
    """Read system instruction from instruction.txt file.

    Returns:
        str: Instruction text, empty string on error
    """
    try:
        with open("instruction.txt", "r", encoding="utf-8") as file:
            instruction = file.read()
            return instruction
    except FileNotFoundError:
        logging.error("instruction.txt file not found. Run init_instruction() first.")
        return ""
    except Exception as e:
        logging.error(f"Failed to read instruction: {e}")
        return ""


def send_prompt(
    chunk: str, PROMPT: str, INSTRUCTION: str, token: str, folder_id: str
) -> str:
    """Send a chunk of text to YandexGPT API for processing.

    Args:
        chunk: JSON string to process
        PROMPT: User prompt text
        INSTRUCTION: System instruction text
        token: YandexGPT API token
        folder_id: Yandex Cloud folder ID

    Returns:
        str: API response text (JSON), empty string on failure
    """
    _ensure_env_loaded()  # Ensure environment variables are loaded

    success = False
    response = None
    logging.info(f"Starting work with a chunk: {chunk[:100]}...")
    time.sleep(2)  # Rate limiting

    # Construct API request
    user_message = {
        "modelUri": f"gpt://{folder_id}/yandexgpt-pro",  # Use folder_id from env
        "completionOptions": {"stream": False, "temperature": 0.6, "maxTokens": "1000"},
        "messages": [
            {"role": "system", "text": INSTRUCTION},
            {"role": "assistant", "text": PROMPT},
            {"role": "user", "text": chunk},
        ],
    }

    # Retry logic: try up to 4 times
    for attempt in range(4):
        time.sleep(2)  # Delay between attempts
        try:
            response = requests.post(
                url="https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Api-Key " + token,
                    "x-folder-id": folder_id,
                },
                json=user_message,
                timeout=60,  # Add timeout
            )
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request failed (attempt {attempt + 1}/4): {e}")
            continue

        if response.status_code == 200:
            logging.info(f"Response received successfully (status: {response.status_code})")
        else:
            logging.warning(
                f"YandexGPT API error (attempt {attempt + 1}/4), status: {response.status_code}"
            )
            continue

        # Validate JSON response
        try:
            tmp_json_response = json.loads(response.text)
            # Extract AI response text
            ai_text = tmp_json_response["result"]["alternatives"][0]["message"]["text"]
            # Clean up markdown code fences and whitespace
            cleaned_text = ai_text.strip("[]`json\n ")
            # Parse as JSON
            tmp_json = json.loads(cleaned_text)

            # Validate all original keys are present in response
            tmp_orig_dict = json.loads(chunk)
            for key in tmp_orig_dict.keys():
                if key not in tmp_json:
                    raise KeyError(f"Missing key in response: {key}")

            success = True
            logging.info("JSON validation successful")
            break
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logging.warning(
                f"JSON validation failed (attempt {attempt + 1}/4): {e}"
            )
            continue
        except Exception as e:
            logging.warning(
                f"Unexpected error processing response (attempt {attempt + 1}/4): {e}"
            )
            continue

    # Final status logging
    if response is None:
        logging.error("All API request attempts failed - no response received")
        return ""

    if response.status_code != 200:
        logging.error(f"Chunk skipped due to API errors: {chunk[:100]}...")
        return ""

    if not success:
        logging.error(f"Chunk skipped due to JSON validation errors: {chunk[:100]}...")
        return ""

    return response.text


def func_yandexgpt(input_dict: dict) -> dict:
    """Process paragraphs dictionary through YandexGPT API.

    Splits dictionary into chunks and sends to API for processing.

    Args:
        input_dict: Dictionary mapping paragraph indices to text

    Returns:
        dict: Processed dictionary with AI modifications
    """
    _ensure_env_loaded()  # Ensure environment variables are loaded

    PROMPT = YANDEX_PRE_PROMPT + get_prompt() + YANDEX_POST_PROMPT
    INSTRUCTION = get_instruction()

    # Check if prompts loaded successfully
    if not PROMPT or not INSTRUCTION:
        logging.error("Failed to load prompts, returning original dictionary")
        return input_dict

    token = YANDEXGPT_TOKEN
    folder_id = FOLDER_ID
    chunk_size = 7  # Process 7 items at a time to avoid API limits
    raw_str_json = ""
    json_strings = []
    items = list(input_dict.items())

    # Split dictionary into chunks
    for i in range(0, len(items), chunk_size):
        chunk_dict = dict(items[i : i + chunk_size])
        json_string = json.dumps(chunk_dict, ensure_ascii=False)
        json_strings.append(json_string)

    logging.info(f"Processing {len(json_strings)} chunks for paragraphs")

    # Process each chunk through API
    for idx, chunk in enumerate(json_strings):
        logging.info(f"Processing chunk {idx + 1}/{len(json_strings)}")
        response = send_prompt(chunk, PROMPT, INSTRUCTION, token, folder_id)

        if response:
            try:
                response_json = json.loads(response)
                ai_text = response_json["result"]["alternatives"][0]["message"]["text"]
                logging.info(f"Received AI response: {ai_text[:100]}...")

                # Clean and append to result
                cleaned_json = ai_text.strip("[]}{`json\n ")
                raw_str_json += cleaned_json + ","
            except (json.JSONDecodeError, KeyError) as e:
                logging.error(f"Failed to parse response for chunk {idx + 1}: {e}")
                continue
        else:
            logging.warning(f"No response for chunk {idx + 1}, skipping")

    # Combine all chunks into final JSON
    if not raw_str_json:
        logging.error("No valid responses received, returning original dictionary")
        return input_dict

    final_json_str = "{" + raw_str_json.strip(",") + "}"
    logging.info(f"FINAL JSON string: {final_json_str[:200]}...")

    try:
        final_json = json.loads(final_json_str)
        return final_json
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse final JSON: {e}")
        logging.error(f"Problematic JSON string: {final_json_str}")
        return input_dict


def yandex_gpt_tables(input_dict: dict) -> dict:
    """Process tables dictionary through YandexGPT API.

    Processes each table separately, splitting into chunks.

    Args:
        input_dict: Nested dictionary mapping table->cell->paragraph indices to text

    Returns:
        dict: Processed dictionary with AI modifications
    """
    _ensure_env_loaded()  # Ensure environment variables are loaded

    PROMPT = YANDEX_PRE_PROMPT + get_prompt() + YANDEX_POST_PROMPT
    INSTRUCTION = get_instruction()

    # Check if prompts loaded successfully
    if not PROMPT or not INSTRUCTION:
        logging.error("Failed to load prompts, returning original dictionary")
        return input_dict

    token = YANDEXGPT_TOKEN
    folder_id = FOLDER_ID
    chunk_size = 7  # Process 7 items at a time to avoid API limits
    result_dict = dict()

    # Process each table separately
    for main_i in input_dict.keys():
        raw_str_json = ""
        json_strings = []
        items = list(input_dict[main_i].items())

        # Split table cells into chunks
        for i in range(0, len(items), chunk_size):
            chunk_dict = dict(items[i : i + chunk_size])
            json_string = json.dumps(chunk_dict, ensure_ascii=False)
            json_strings.append(json_string)

        logging.info(f"Processing table {main_i} with {len(json_strings)} chunks")

        # Process each chunk through API
        for idx, chunk in enumerate(json_strings):
            logging.info(f"Processing table {main_i}, chunk {idx + 1}/{len(json_strings)}")
            response = send_prompt(chunk, PROMPT, INSTRUCTION, token, folder_id)

            if response:
                try:
                    response_json = json.loads(response)
                    ai_text = response_json["result"]["alternatives"][0]["message"]["text"]
                    logging.info(f"Received AI response: {ai_text[:100]}...")

                    # Clean and append to result (FIXED: removed extra "}")
                    cleaned_json = ai_text.strip("[]}{`json\n ")
                    raw_str_json += cleaned_json + ","
                except (json.JSONDecodeError, KeyError) as e:
                    logging.error(f"Failed to parse response for table {main_i}, chunk {idx + 1}: {e}")
                    continue
            else:
                logging.warning(f"No response for table {main_i}, chunk {idx + 1}, skipping")

        # Combine all chunks for this table
        if not raw_str_json:
            logging.warning(f"No valid responses for table {main_i}, using empty dict")
            result_dict[main_i] = {}
            continue

        final_json_str = "{" + raw_str_json.strip(",") + "}"
        logging.info(f"FINAL JSON for table {main_i}: {final_json_str[:200]}...")

        try:
            final_json = json.loads(final_json_str)
            result_dict[main_i] = final_json
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse final JSON for table {main_i}: {e}")
            logging.error(f"Problematic JSON string: {final_json_str}")
            result_dict[main_i] = input_dict[main_i]  # Use original on error

    return result_dict


def init_instruction():
    """Initialize prompt.txt and instruction.txt from default files.

    Creates user-editable configuration files from defaults if they don't exist.
    This function is called on first run to set up the environment.
    """
    import os

    # Initialize prompt.txt
    try:
        # Try to read from current directory first
        if os.path.exists("default_prompt.txt"):
            with open("default_prompt.txt", "r", encoding="utf-8") as file:
                def_prompt = file.read()
        elif os.path.exists("docxai/default_prompt.txt"):
            with open("docxai/default_prompt.txt", "r", encoding="utf-8") as file:
                def_prompt = file.read()
        else:
            logging.error("default_prompt.txt not found in current dir or docxai/")
            def_prompt = "Translate all text to English."  # Fallback default
    except Exception as e:
        logging.error(f"Failed to read default_prompt.txt: {e}")
        def_prompt = "Translate all text to English."  # Fallback default

    # Write prompt.txt if it doesn't exist
    try:
        if not os.path.exists("prompt.txt"):
            with open("prompt.txt", "w", encoding="utf-8") as file:
                file.write(def_prompt)
            logging.info("Created prompt.txt from default")
        else:
            logging.info("prompt.txt already exists, not overwriting")
    except Exception as e:
        logging.error(f"Failed to write prompt.txt: {e}")

    # Initialize instruction.txt
    try:
        # Try to read from current directory first
        if os.path.exists("default_instruction.txt"):
            with open("default_instruction.txt", "r", encoding="utf-8") as file:
                def_instruction = file.read()
        elif os.path.exists("docxai/default_instruction.txt"):
            with open("docxai/default_instruction.txt", "r", encoding="utf-8") as file:
                def_instruction = file.read()
        else:
            logging.error("default_instruction.txt not found in current dir or docxai/")
            def_instruction = "You are a helpful AI assistant."  # Fallback default
    except Exception as e:
        logging.error(f"Failed to read default_instruction.txt: {e}")
        def_instruction = "You are a helpful AI assistant."  # Fallback default

    # Write instruction.txt if it doesn't exist
    try:
        if not os.path.exists("instruction.txt"):
            with open("instruction.txt", "w", encoding="utf-8") as file:
                file.write(def_instruction)
            logging.info("Created instruction.txt from default")
        else:
            logging.info("instruction.txt already exists, not overwriting")
    except Exception as e:
        logging.error(f"Failed to write instruction.txt: {e}")


def main():
    """Main entry point for document processing.

    Initializes configuration files and processes test document.
    """
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('docxai.log', encoding='utf-8')
        ]
    )

    logging.info("=" * 60)
    logging.info("DocxAI Document Processing Started")
    logging.info("=" * 60)

    # Initialize configuration files if they don't exist
    try:
        init_instruction()
    except Exception as e:
        logging.error(f"Failed to initialize configuration: {e}")
        return

    # Process the test document
    # TODO: Accept file path as command-line argument
    input_file = "test.docx"
    logging.info(f"Processing input file: {input_file}")

    try:
        output_file = file_process(input_file)
        if output_file:
            logging.info("=" * 60)
            logging.info(f"SUCCESS! Output file created: {output_file}")
            logging.info("=" * 60)
        else:
            logging.error("=" * 60)
            logging.error("FAILED! Document processing did not complete")
            logging.error("=" * 60)
    except Exception as e:
        logging.error("=" * 60)
        logging.error(f"CRITICAL ERROR during processing: {e}")
        logging.error("=" * 60)
        raise


if __name__ == "__main__":
    main()
