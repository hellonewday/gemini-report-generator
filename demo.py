
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

client = genai.Client(
            vertexai=True,
            project="nth-droplet-458903-p4",
            location="global",
        )
model_id = "gemini-2.5-pro-preview-03-25"

google_search_tool = Tool(
      google_search = GoogleSearch()
)

response = client.models.generate_content(
      model=model_id,
      contents="Research Nike SEA&I current promotion campaigns, with deep dive into the details. Avoid jargon and lacks substance.",
      config=GenerateContentConfig(
          temperature = 0.7,
          max_output_tokens = 65535,
          tools=[google_search_tool],
          response_modalities=["TEXT"]
      )
)

# for each in response.candidates[0].content.parts:
#     print(each.text)

print(response.text)