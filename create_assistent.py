from openai import OpenAI
import streamlit as st

client = OpenAI(api_key= st.secrets["OPENAI_API_KEY"])

def create_assistent():
    assistant = client.beta.assistants.create(
        name="Book summarizer",
        instructions="""
Assistant Instructions:
"""

,
        tools=[{"type": "file_search"}],
        model="gpt-4o-mini",
        )
    print(assistant.id)
    return assistant.id

#assistent_ID = create_assistent()
