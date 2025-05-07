from components import HomePage, LoginPage, UploadPage, ProjectHomePage, RFPPage, ProcessedRFPsPage
from processing import Database
from auth import Authenticator

import streamlit as st
import os

# Set page config before anything else
st.set_page_config(
    page_title="LLM Assisted Q&A",
    page_icon=os.path.join(os.path.dirname(__file__), 'assets', 'Logo.jpg'),
    layout="wide",
    menu_items={
                'Get Help': None,
                'Report a bug': None,
                'About': "# Your AI Assistant"
            }
)

class App:

    def __init__(self):

        # Initialize components only once when app starts
        if 'initialized' not in st.session_state:
            self._initialize_components()
            st.session_state['initialized'] = True

    def _initialize_components(self):

        # Initialize database
        db = Database.get_instance()

        # Initialize core services
        st.session_state['auth'] = Authenticator(db)

        # Initialize pages
        st.session_state['home_page'] = HomePage(db)
        st.session_state['login_page'] = LoginPage(st.session_state['auth'])
        st.session_state['upload_page'] = UploadPage(
            db = db
        )
        st.session_state['project_home_page'] = ProjectHomePage(db)
        st.session_state['project_upload_page'] = UploadPage(
            db=db
        )
        st.session_state['project_rfp_page'] = RFPPage(db)
        st.session_state['processed_rfps_page'] = ProcessedRFPsPage(db)

    def run(self):
        
        

        # Initialize session state for current page if not exists
        if 'current_page' not in st.session_state:
            st.session_state['current_page'] = 'Login'
        
        # Show different navigation based on authentication status
        if not st.session_state.get('authentication_status'):
            if st.sidebar.button('Login'):
                st.session_state['current_page'] = 'Login'
        else:
            # Only show logout button once
            st.session_state['auth'].authenticator.logout(location='sidebar')
            
            # Check if we're in a project context
            if st.session_state.get('current_project_id'):
                if st.sidebar.button('Back to Dashboard'):
                    st.session_state['current_project_id'] = None
                    st.session_state['current_page'] = 'Home'
                    st.rerun()
                
                # Project-specific navigation
                pages = {
                    "Home": st.session_state['project_home_page'].show,
                    "Upload": st.session_state['project_upload_page'].show,
                    "RFP": st.session_state['project_rfp_page'].show,
                    "Processed RFPs": st.session_state['processed_rfps_page'].show
                }
            else:
                # Main dashboard - only show Home
                pages = {
                    "Dashboard": st.session_state['home_page'].show
                }
            
            page = st.sidebar.selectbox("Navigate to", options=list(pages.keys()))
            pages[page]()
        
        # Handle unauthenticated pages
        if st.session_state['current_page'] == "Login":
            st.session_state['login_page'].show()

if __name__ == "__main__":
    app = App()
    app.run()