import streamlit as st
import random
import string
from datetime import datetime

class FakeLLM:
    @staticmethod
    def generate_response(prompt: str) -> str:
        # Generate a random response between 50-150 characters
        length = random.randint(50, 150)
        return ''.join(random.choices(string.ascii_letters + ' ,.!?', k=length))

class ChatPage:
    def __init__(self):
        self.llm = FakeLLM()

    def show(self):
        st.title("Chat with AI")
        
        # Initialize chat history in session state if it doesn't exist
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        
        # Display chat history
        for message in st.session_state.chat_history:
            with st.chat_message("user" if message["is_user"] else "assistant"):
                st.write(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Type your message here..."):
            self._handle_chat_interaction(prompt)

    def _handle_chat_interaction(self, prompt: str):
        # Add user message to chat history
        self._add_message_to_history(prompt, is_user=True)
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Generate and display AI response
        response = self.llm.generate_response(prompt)
        
        # Add AI response to chat history
        self._add_message_to_history(response, is_user=False)
        
        # Display AI response
        with st.chat_message("assistant"):
            st.write(response)

    def _add_message_to_history(self, content: str, is_user: bool):
        st.session_state.chat_history.append({
            "content": content,
            "is_user": is_user,
            "timestamp": datetime.now()
        })