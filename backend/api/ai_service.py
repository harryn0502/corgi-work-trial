import os
import base64
import mimetypes
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error encoding image {image_path}: {e}")
        return None


def query_ai(user, system_role="You are a helpful assistant", image_paths=None):
    content = [{"type": "input_text", "text": user}]

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

    messages = [
        {"role": "system", "content": system_role},
        {"role": "user", "content": content},
    ]

    try:
        response = client.responses.create(model="gpt-5.2", input=messages)
        return response.output_text
    except Exception as e:
        return f'{{"amount": 0, "reasoning": "Error calling AI: {str(e)}"}}'
