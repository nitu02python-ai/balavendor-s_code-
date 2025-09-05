import os
from bs4 import BeautifulSoup
import openai
from bs4 import NavigableString

# Define folder structure
BASE_DIR = "input"
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
INCLUDES_DIR = os.path.join(BASE_DIR, "includes")

# Ensure output and includes folders exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(INCLUDES_DIR, exist_ok=True)

# Read OpenAI API key from environment (if used). Avoid hard-coded secrets.
openai.api_key = os.getenv("OPENAI_API_KEY")
print(openai.api_key)
def save_include(content, filename):
    """Save content to an include file."""
    include_path = os.path.join(INCLUDES_DIR, filename)
    # Pretty-format the fragment before saving so includes are readable HTML
    try:
        frag_soup = BeautifulSoup(content, "html.parser")
        pretty = frag_soup.prettify(formatter="html")
    except Exception:
        pretty = content

    with open(include_path, "w", encoding="utf-8") as f:
        f.write(pretty)
    return f"<?php include_once $_SERVER['DOCUMENT_ROOT'] . '/includes/{filename}'; ?>"


def log_change(file_name, message):
    """Log changes to console and a log file in the output directory."""
    log_path = os.path.join(OUTPUT_DIR, "agent-changes.log")
    entry = f"[{file_name}] {message}\n"
    print(entry.strip())
    try:
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(entry)
    except Exception:
        pass

def train_ai_agent():
    """Train the AI agent using unstructured and structured code."""
    with open("generated-px-code-input.txt", "r", encoding="utf-8") as unstructured_file:
        unstructured_code = unstructured_file.read()

    with open("final-PHPoutput.txt", "r", encoding="utf-8") as structured_file:
        structured_code = structured_file.read()

    prompt = f"""
    You are an AI agent tasked with converting unstructured HTML code into structured PHP code. Your goals are:
    1. Identify and fill in missing HTML parts intelligently.
    2. Ensure compatibility with existing PHP includes and partials.
    3. Preserve the design and functionality of the original HTML.

    Unstructured HTML:
    {unstructured_code}

    Structured PHP:
    {structured_code}

    Based on the above examples, process new HTML inputs to generate structured PHP outputs.
    """
    return prompt

def ai_fill_missing_parts(html_content):
    """Use the trained AI agent to fill in missing HTML parts."""
    prompt = train_ai_agent() + f"\nNew HTML Input:\n{html_content}\n\nStructured PHP Output:\n"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-5",  # Updated to use chat model
            messages=[
                {"role": "system", "content": "You are an AI agent tasked with converting unstructured HTML code into structured PHP code."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=1500  # Updated parameter name
        )
        ai_generated_content = response["choices"][0]["message"]["content"].strip()
        if ai_generated_content:
            return ai_generated_content
    except Exception as e:
        print(f"AI processing failed: {e}")

    # Fallback to original content if AI fails
    print("Using original HTML content as fallback.")
    return html_content

def ensure_html_structure(html_content):
    """Ensure the HTML structure is complete and well-ordered.

    Returns (final_html, changes) where changes is a list of strings describing modifications made.
    """
    changes = []
    placeholder = "___PHP_HEADER_ASSETS_INCLUDE___"

    has_doctype = "<!doctype" in html_content.lower()
    original_soup = BeautifulSoup(html_content, "html.parser")

    # Detect if original had html/head/body
    had_html = original_soup.html is not None
    had_head = original_soup.head is not None
    had_body = original_soup.body is not None

    # Create new document skeleton
    new_soup = BeautifulSoup("", "html.parser")
    html_tag = new_soup.new_tag("html", lang="en")
    new_soup.append(html_tag)

    # HEAD: use existing head if present, otherwise create one
    if had_head:
        # move existing head into new soup (preserve as-is)
        head_html = str(original_soup.head)
        head_fragment = BeautifulSoup(head_html, "html.parser")
        html_tag.append(head_fragment.head)
    else:
        head_tag = new_soup.new_tag("head")
        meta_charset = new_soup.new_tag("meta", charset="UTF-8")
        meta_viewport = new_soup.new_tag("meta", attrs={"name": "viewport", "content": "width=device-width, initial-scale=1.0"})
        title_tag = new_soup.new_tag("title")
        title_tag.string = "Clipping Path Services"
        head_tag.append(meta_charset)
        head_tag.append(meta_viewport)
        head_tag.append(title_tag)
        # insert placeholder which will be replaced with raw PHP include later
        head_tag.append(BeautifulSoup(placeholder, "html.parser"))
        html_tag.append(head_tag)
        changes.append("Added missing <head> with meta/title and header-assets placeholder")

    # BODY: if original has body, preserve it; otherwise move top-level content into body
    body_tag = new_soup.new_tag("body")
    if had_body:
        # move children of original body into new body
        for child in original_soup.body.contents:
            body_tag.append(BeautifulSoup(str(child), "html.parser"))
    else:
        # move all top-level nodes (except head if it existed) into body
        for child in original_soup.contents:
            # skip doctype declarations and head nodes
            if getattr(child, 'name', None) == 'head':
                continue
            # append to body
            body_tag.append(BeautifulSoup(str(child), "html.parser"))
        changes.append("Wrapped top-level content into <body>")

    html_tag.append(body_tag)

    final_html = new_soup.prettify()

    # Prepend doctype if it was missing
    if not has_doctype:
        final_html = "<!DOCTYPE html>\n" + final_html
        changes.insert(0, "Added missing <!DOCTYPE html>")

    # If original did not have <html>, record it
    if not had_html:
        changes.append('Wrapped content in <html lang="en">')

    # Replace placeholder with raw PHP include (not escaped)
    php_include = "<?php include_once $_SERVER['DOCUMENT_ROOT'] . \"/includes/header-assets.php\"; ?>"
    if placeholder in final_html:
        final_html = final_html.replace(placeholder, php_include)
        # only record if we actually inserted the include
        changes.append("Inserted header-assets PHP include into <head>")

    # Ensure closing tags for body/html exist (prettify already includes them)
    return final_html, changes

# Updated function to handle <nav> tags
def convert_html_to_php(file_path):
    # Read HTML file
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    filename = os.path.basename(file_path)

    # Agent 1: insert PHP includes for header/nav/footer and save partials
    html_content, agent1_changes = agent_insert_includes(html_content, filename)
    for c in agent1_changes:
        log_change(filename, f"Agent1: {c}")

    # Agent 2: validate/fix HTML structure (head meta, closing tags)
    html_content, agent2_changes = agent_validate_and_fix_structure(html_content, filename)
    for c in agent2_changes:
        log_change(filename, f"Agent2: {c}")

    # Final pass: ensure PHP tags are not escaped by BeautifulSoup
    # (some operations may have produced escaped entities like &lt;?php)
    html_content = unescape_php_tags(html_content)

    return html_content


def unescape_php_tags(content):
    # Replace common escaped php sequences
    return content.replace("&lt;?php", "<?php").replace("?&gt;", "?>")


def agent_insert_includes(html_content, filename):
    """Agent 1: find <header>, <nav>, <footer> and replace them with PHP includes while saving the extracted markup.
    Returns modified content and a list of change messages.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    changes = []

    # header
    header = soup.find("header")
    if header:
        include_php = save_include(str(header), "header-navbar.php")
        header.replace_with(NavigableString(include_php))
        changes.append("Replaced <header> with /includes/header-navbar.php")

    # nav
    nav = soup.find("nav")
    if nav:
        include_php = save_include(str(nav), "nav.php")
        nav.replace_with(NavigableString(include_php))
        changes.append("Replaced <nav> with /includes/nav.php")

    # footer
    footer = soup.find("footer")
    if footer:
        include_php = save_include(str(footer), "footer.php")
        footer.replace_with(NavigableString(include_php))
        changes.append("Replaced <footer> with /includes/footer.php")

    return str(soup), changes


def agent_validate_and_fix_structure(html_content, filename):
    """Agent 2: ensure head exists with meta charset, viewport, title and header-assets include; ensure closing </body></html> present.
    Returns modified content and list of change messages.
    """
    changes = []

    # First, ensure basic structure and capture changes
    html_content, structural_changes = ensure_html_structure(html_content)
    changes.extend(structural_changes)

    soup = BeautifulSoup(html_content, "html.parser")

    # Ensure head contains charset, viewport, title and header-assets include
    head = soup.head
    if head:
        # charset
        if not head.find("meta", attrs={"charset": True}):
            meta_charset = soup.new_tag("meta", charset="UTF-8")
            head.insert(0, meta_charset)
            changes.append("Added <meta charset=\"UTF-8\"> to <head>")

        # viewport
        if not head.find("meta", attrs={"name": "viewport"}):
            meta_viewport = soup.new_tag("meta", attrs={"name": "viewport", "content": "width=device-width, initial-scale=1.0"})
            head.append(meta_viewport)
            changes.append("Added viewport meta to <head>")

        # title
        if not head.find("title"):
            title_tag = soup.new_tag("title")
            title_tag.string = "Clipping Path Services"
            head.append(title_tag)
            changes.append("Added <title> to <head>")

        # header-assets include (raw php)
        include_line = "<?php include_once $_SERVER['DOCUMENT_ROOT'] . \"/includes/header-assets.php\"; ?>"
        head_text = str(head)
        if "/includes/header-assets.php" not in head_text:
            # append as NavigableString to avoid BeautifulSoup creating a weird tag
            head.append(NavigableString(include_line))
            changes.append("Inserted header-assets PHP include into <head>")

    # Ensure closing tags exist
    final = str(soup)
    if "</body>" not in final:
        final = final + "\n</body>"
        changes.append("Appended missing </body>")
    if "</html>" not in final:
        final = final + "\n</html>"
        changes.append("Appended missing </html>")

    # Unescape any PHP escapes
    final = unescape_php_tags(final)

    return final, changes

# Updated process_all_files to validate output
def process_all_files():
    for filename in os.listdir(BASE_DIR):
        if filename.endswith(".html"):
            file_path = os.path.join(BASE_DIR, filename)
            php_content = convert_html_to_php(file_path)

            # Save as .php in output folder
            output_path = os.path.join(OUTPUT_DIR, filename.replace(".html", ".php"))
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(php_content)

            print(f"Converted: {filename} → {output_path}")

            # Validate output with training data
            validate_output(output_path)

# Validation function using training data
def validate_output(output_path):
    with open("generated-px-code-input.txt", "r", encoding="utf-8") as input_file:
        with open("final-PHPoutput.txt", "r", encoding="utf-8") as output_file:
            expected_output = output_file.read()
            generated_output = open(output_path, "r", encoding="utf-8").read()

            if generated_output.strip() == expected_output.strip():
                print(f"Validation passed for {output_path}")
            else:
                print(f"Validation failed for {output_path}")

if __name__ == "__main__":
    process_all_files()
