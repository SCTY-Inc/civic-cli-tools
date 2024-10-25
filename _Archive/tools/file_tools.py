from datetime import datetime
import os
import re

class FileTools:
    @staticmethod
    def format_to_markdown(text):
        # Split the text into sections based on the pattern
        sections = re.split(r'(\d+\..+?)(?=\n\d+\.|$)', text, flags=re.DOTALL)
        formatted_text = ""
        for section in sections:
            if section.strip():
                if section.startswith("Title:"):
                    formatted_text += f"# {section.strip()}\n\n"
                elif re.match(r'\d+\.', section.strip()):
                    header, content = section.split('\n', 1)
                    formatted_text += f"## {header.strip()}\n\n{content.strip()}\n\n"
                else:
                    formatted_text += f"{section.strip()}\n\n"
        return formatted_text

    @staticmethod
    def write_file(content, filename_prefix="Civic", output_directory="output", extension=".md"):
        try:
            if not re.match(r'^[\w\-. ]+$', filename_prefix):
                raise ValueError("Invalid filename prefix")
            current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_filename = f"{filename_prefix}_{current_datetime}{extension}"
            output_file_path = os.path.join(output_directory, output_filename)
            if not os.path.exists(output_directory):
                os.makedirs(output_directory)
            with open(output_file_path, "w") as f:
                f.write(content)
            return f"File successfully written to {os.path.abspath(output_file_path)}"
        except Exception as e:
            return f"Error writing the file: {e}"

    @staticmethod
    def save_markdown(task_output, filename_prefix="Brief", output_directory="/Users/amadad/Projects/civic-agentcy/output"):
        today_date = datetime.now().strftime('%Y-%m-%d')
        filename = f"{filename_prefix}-{today_date}.md"
        full_path = os.path.join(output_directory, filename)
        try:
            with open(full_path, 'w') as file:
                file.write(task_output)
            print(f"Policy Brief saved as {full_path}")
        except Exception as e:
            print(f"Error saving the markdown: {e}")