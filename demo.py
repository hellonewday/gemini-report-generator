from langchain_google_vertexai import ChatVertexAI, HarmBlockThreshold, HarmCategory
from google.cloud.aiplatform_v1beta1.types import Tool as VertexTool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

llm = ChatVertexAI(
    model="gemini-2.5-flash-preview-04-17",
    project="nth-droplet-458903-p4",
    temperature=0,
    max_tokens=None,
    max_retries=6,
    stop=None,
    safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    },
)

messages = [
    SystemMessage(
        content="You are a helpful assistant. You can answer questions and provide information."
    ),
    HumanMessage(
            content="What is the capital of France?"
    ),
]
ai_msg = llm.invoke(messages, tools=[VertexTool(google_search={})])
print(ai_msg)