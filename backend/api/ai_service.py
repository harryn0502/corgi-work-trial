import os
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def request(user, system, image_url=None):

    content = [{"type": "input_text", "text": user}]

    if image_url:
        content.append(
            {
                "type": "input_image",
                "image_url": image_url,
            }
        )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]

    try:
        response = client.responses.create(model="gpt-5.2", input=messages)
        return response.output_text
    except Exception as e:
        return str(e)
