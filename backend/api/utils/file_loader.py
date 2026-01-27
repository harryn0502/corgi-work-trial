import os
import tempfile
from pypdf import PdfReader
from docx import Document
from pdf2image import convert_from_path


class EvidenceLoader:
    def __init__(self):
        self.base_path = "/app/data/attachments"
        self.temp_dir = tempfile.mkdtemp()

    def load_for_claim(self, id):
        # Looks for evidence
        target_dir = os.path.join(self.base_path, str(id))

        # Initialise the result
        results = {"text_context": "", "image_paths": []}

        # Check evidence exists
        if not os.path.exists(target_dir):
            results["text_context"] = f"No attachments found for tracking number: {id}."
            return results

        # Scan the directory
        print(f"Scanning: {target_dir}")
        for filename in os.listdir(target_dir):
            file_path = os.path.join(target_dir, filename)
            if filename.startswith("."):
                continue  # Skip hidden files

            # Images
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                results["image_paths"].append(file_path)

            # PDFs
            elif filename.lower().endswith(".pdf"):
                self._process_pdf(file_path, filename, results)

            # Word Docs
            elif filename.lower().endswith(".docx"):
                try:
                    doc = Document(file_path)
                    text = "\n".join([p.text for p in doc.paragraphs])
                    results["text_context"] += f"\n[FILE: {filename}]\n{text}\n"
                except:
                    pass

            # Text/RMD
            elif filename.lower().endswith((".rmd", ".txt", ".csv")):
                try:
                    with open(file_path, "r", errors="ignore") as f:
                        results["text_context"] += f"\n[FILE: {filename}]\n{f.read()}\n"
                except:
                    pass

        return results

    def _process_pdf(self, file_path, filename, results):
        try:
            reader = PdfReader(file_path)
            extracted_text = "".join([p.extract_text() or "" for p in reader.pages])

            # If it has meaning text, use the text
            if len(extracted_text.strip()) > 50:
                results["text_context"] += f"\n[FILE: {filename}]\n{extracted_text}\n"
                return

            # FALLBACK: Convert to Images
            print(f"PDF {filename} seems scanned/handwritten. Converting to images...")
            results["text_context"] += f"\n[FILE: {filename}] (Scanned Document - See Images)\n"

            # Convert pages to images (JPEG)
            images = convert_from_path(file_path)

            for i, image in enumerate(images):
                # Save temp image
                temp_name = f"{filename}_page_{i+1}.jpg"
                temp_path = os.path.join(self.temp_dir, temp_name)
                image.save(temp_path, "JPEG")

                # Add to results so AI service sees it
                results["image_paths"].append(temp_path)
        except Exception as e:
            print(f"Failed to process PDF {filename}: {e}")
            results["text_context"] += f"\n[FILE: {filename}] (Unreadable)\n"
