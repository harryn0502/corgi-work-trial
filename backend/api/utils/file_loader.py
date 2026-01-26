import os
from pypdf import PdfReader
from docx import Document


class EvidenceLoader:
    def __init__(self):
        self.base_path = "/app/data/attachments"

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
                try:
                    reader = PdfReader(file_path)
                    text = "".join([p.extract_text() or "" for p in reader.pages])
                    results["text_context"] += f"\n[FILE: {filename}]\n{text}\n"
                except:
                    results["text_context"] += f"\n[FILE: {filename}] (Unreadable PDF)\n"

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
