from google import genai
from google.genai import types

def generate():
  client = genai.Client(
      vertexai=True,
      project="nth-droplet-458903-p4",
      location="us-central1",
  )


  model = "gemini-2.5-pro-preview-05-06"
  contents = [
    types.Content(
      role="user",
      parts=[
        types.Part.from_text(text="""I need some tips to study English""")
      ]
    ),
  ]

  generate_content_config = types.GenerateContentConfig(
    temperature = 1,
    top_p = 0.95,
    seed = 0,
    max_output_tokens = 8192,
    response_modalities = ["TEXT"],
    safety_settings = [types.SafetySetting(
      category="HARM_CATEGORY_HATE_SPEECH",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_DANGEROUS_CONTENT",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_HARASSMENT",
      threshold="OFF"
    )],
  )
  print(contents);
  for chunk in client.models.generate_content_stream(
    model = model,
    contents = contents,
    config = generate_content_config,
    ):
    print(chunk.text, end="")

generate()