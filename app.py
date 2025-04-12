import openai
import streamlit as st
from openai import OpenAI
import time
from create_assistent import create_assistent

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "list_assistant_id" not in st.session_state:
    st.session_state.list_assistant_id = []

if "list_vector_store_id" not in st.session_state:
    st.session_state.list_vector_store_id = []

if "list_file_id" not in st.session_state:
    st.session_state.list_file_id = []

if "list_thread_id" not in st.session_state:
    st.session_state.list_thread_id = []

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = ""

if 'uploaded_files' not in st.session_state:
    st.session_state.process_file = False
    st.session_state.uploaded_files=None

if 'assistant_id' not in st.session_state:
    st.session_state.assistant_id = ''


def ensure_single_thread_id():
    """Ensures that only one thread exists in the session."""
    if "thread_id" not in st.session_state:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id

def upload_and_create_vector_store(files):
    """Uploads multiple files and creates a vector store containing them."""
    if files:
        uploaded_file_ids = []
        for file in files:
            uploaded = client.files.create(
                file=file,
                purpose="assistants"
            )
            uploaded_file_ids.append(uploaded.id)
        
        vector_store = client.beta.vector_stores.create(
            name="User Uploaded Documents",
            file_ids=uploaded_file_ids,
            expires_after={
                "anchor": "last_active_at",
                "days": 1
            }
        )
        st.session_state.list_vector_store_id.append(vector_store.id)
        
        while True:
            vs = client.beta.vector_stores.retrieve(vector_store.id)
            if vs.status == "completed":
                break
            elif vs.status == "failed":
                st.error("Vector store creation failed.")
                return None
            time.sleep(2)
        
        return vector_store.id

def upload_and_create_thread(files):
    """Uploads files, creates a vector store, and associates it with a new thread."""
    if files:
        vector_store_id = upload_and_create_vector_store(files)
        print(vector_store_id)
        if not vector_store_id:
            return None
        
        uploaded_files = client.files.list().data[-len(files):]
        uploaded_file_ids = [f.id for f in uploaded_files]
        for file_id in uploaded_file_ids:
            st.session_state.list_file_id.append(file_id)
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": "Please analyze the attached documents.",
                    "attachments": [
                        {"file_id": file_id, "tools": [{"type": "file_search"}]} 
                        for file_id in uploaded_file_ids
                    ],
                }
            ],
            tool_resources={
                "file_search": {
                    "vector_store_ids": [vector_store_id]
                }
            }
        )
        st.session_state.list_thread_id.append(thread.id)
        return thread

def stream_generator(prompt, thread_id, assistant_id):
    """Generates a stream of responses from the assistant."""
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=prompt
    )
    with st.spinner("Wait... Generating response..."):
        stream = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
            stream=True
        )
        for event in stream:
            if event.data.object == "thread.message.delta":
                for content in event.data.delta.content:
                    if content.type == "text":
                        yield content.text.value


st.set_page_config(page_icon=":speech_balloon:")
st.title("💬 Chatbot")


with st.sidebar:
    uploaded_files = st.file_uploader("Upload PDF files for analysis", type=["pdf"], accept_multiple_files=True)
    if not uploaded_files:
        st.session_state.process_files=True
        st.session_state.uploaded_files=None
        try:
            # Delete assistent
            print("assistant Deletion ")

            for assistant in st.session_state.list_assistant_id:
                client.beta.assistants.delete(assistant)

            print("assistant Deletion successful")
        except:
            st.session_state.process_files=True
            st.session_state.uploaded_files=None

        try:
            # Delete vector store
            print("vector_stores Deletion")
            for vector in st.session_state.list_vector_store_id:
                deleted_vector_store = client.beta.vector_stores.delete(
                    vector_store_id=vector
                )
            print("vector_stores Deletion successful")
        except:
            st.session_state.process_files=True
            st.session_state.uploaded_files=None

        try:
            # Delete files
            print("Files Deletion ")
            for file in st.session_state.list_file_id:
                client.files.delete(file)
            print("Files Deletion successful")
        except:
            st.session_state.process_files=True
            st.session_state.uploaded_files=None

        try:
            # Delete files
            print("threads Deletion ")
            for thread in st.session_state.list_thread_id:
                client.beta.threads.delete(thread)
            print("Threads Deletion successful")
        except:
            st.session_state.process_files=True
            st.session_state.uploaded_files=None


    
    if uploaded_files and st.session_state.process_files:
        st.session_state.process_files = False
        st.session_state.assistant_id = create_assistent()
        st.session_state.list_assistant_id.append(st.session_state.assistant_id)
        thread = upload_and_create_thread(uploaded_files)
        if thread:
            st.session_state.thread_id = thread.id
            st.success(f"{len(uploaded_files)} file(s) uploaded and thread created!")
            attached_files = [f.name for f in uploaded_files]
            st.write("Attached Files:")
            for fname in attached_files:
                st.write(f"- {fname}")



for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if uploaded_files:
    prompt = st.chat_input("Enter your message")
    if prompt:
        if st.session_state.thread_id == '':
            st.session_state.thread_id = ensure_single_thread_id()
        print(st.session_state.thread_id)
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            response = ""
            for chunk in stream_generator(prompt, st.session_state.thread_id, st.session_state.assistant_id):
                response += chunk
            st.write(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
else:
    st.warning("Please Upload file first to start chatting")
