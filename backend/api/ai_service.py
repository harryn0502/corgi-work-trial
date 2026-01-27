import os
import base64
import mimetypes
from openai import OpenAI
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


# --- Pydantic Models for Structured Output ---
class LineItem(BaseModel):
    item_name: str = Field(
        ..., description="Name of the service or item (e.g., 'Carpet Cleaning', 'Drywall Repair')."
    )
    claimed_amount: float = Field(
        ..., description="The amount the user is asking for this specific item."
    )
    approved_amount: float = Field(
        ..., description="The amount you approve after reviewing evidence and policy limits."
    )
    rejection_reason: Optional[str] = Field(
        None,
        description="If approved_amount < claimed_amount, explain why (e.g., 'Wear and tear', 'No receipt').",
    )
    note: Optional[str] = Field(
        None, description="Observations about dates, discrepancies, or specific evidence found."
    )


class ClaimAssessment(BaseModel):
    confidence_score: float = Field(
        ...,
        description="A generic score from 0.0 to 1.0 representing how confident you are in this assessment based on evidence clarity.",
    )
    summary_of_evidence: str = Field(
        ..., description="A brief summary of the valid receipts and documents found."
    )
    line_items: List[LineItem] = Field(..., description="A breakdown of every item claimed.")
    policy_check_notes: str = Field(
        ..., description="Notes on lease dates, policy limits, or specific exclusions applied."
    )
    final_total_approved: float = Field(
        ...,
        description="The sum of all approved_amount fields, capped by the Policy Limit if necessary.",
    )


class AbbreviationItem(BaseModel):
    code: str = Field(..., description="The abbreviation acronym (e.g., 'MCF')")
    meaning: str = Field(
        ..., description="The full definition (e.g., 'Maintenance Coordination Fee')"
    )


class PolicyRules(BaseModel):
    abbreviations: List[AbbreviationItem] = Field(
        ...,
        description="List of found abbreviations and their meanings.",
    )
    approved_categories: List[str] = Field(
        ..., description="List of categories or items that are explicitly COVERED/APPROVED."
    )
    rejected_categories: List[str] = Field(
        ..., description="List of categories or items that are explicitly REJECTED/NOT COVERED."
    )
    formatted_rule_text: str = Field(
        ...,
        description="A clear, markdown-formatted string suitable for a System Prompt (e.g., '### COVERAGE RULES...').",
    )


# Helper function to encode image file into base64
def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error encoding image {image_path}: {e}")
        return None


def query_claim_assessment(user_prompt: str, system_prompt: str, image_paths: List[str] = None):
    # Prepare content
    content = [{"type": "input_text", "text": user_prompt}]

    # Attach Images (if any)
    if image_paths:
        for path in image_paths:
            base64_image = encode_image(path)
            if base64_image:
                # Detect mimetype
                mime_type, _ = mimetypes.guess_type(path)

                # Fallback if detection fails
                if not mime_type:
                    mime_type = "image/jpeg"

                content.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{base64_image}",
                    }
                )

    # Call OpenAI
    try:
        response = client.responses.parse(
            model="gpt-5.2",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            text_format=ClaimAssessment,
        )
        return response.output_parsed
    except Exception as e:
        raise RuntimeError(f"AI Service Failure: {str(e)}")


def generate_converage_policy(history_summary):
    system_prompt = """
    ROLE: Insurance Policy Manager
    GOAL: Analyze the provided "History of PM Explnations" and create a list of "Deposit Claim Coverage Policy"

    OUTPUT REQUIREMENTS:
    1. Identify all Abbreviations (e.g., MCF, RBP).
    2. Identify what was APPROVED vs REJECTED.
    3. Detect nuance (e.g., "Lightbulbs are rejected UNLESS > $50").
    4. Generate a clean Markdown section titled "### GENERATED COVERAGE RULES" that instructs an AI how to audit future claims.
    """

    try:
        response = client.responses.parse(
            model="gpt-5.2",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"### HISTORY OF DECISIONS:\n{history_summary}"},
            ],
            text_format=PolicyRules,
        )
        return response.output_parsed.formatted_rule_text

    except Exception as e:
        print(f"Policy Generation Error: {e}")
        return """
        ### GENERATED COVERAGE RULES
        - Apply reasonable rules
        """
