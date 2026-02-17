import streamlit as st
import pandas as pd
from datetime import datetime

if 'projects' not in st.session_state:
    st.session_state.projects = {'current': 'IPRC WEST'}
if 'log' not in st.session_state:
    st.session_state.log = []
if 'current_project' not in st.session_state:
    st.session_state.current_project = 'current'

def log_activity(action: str, details: str):
    st.session_state.log.append({
        'timestamp': datetime.now().isoformat(),
        'project': st.session_state.current_project,
        'action': action,
        'details': details
    })

@st.cache_data
def get_defaults(project='current'):
    return {
        'Q_avg': 0.0016,
        'BOD_in': 250,
        'TSS_in': 220,
        'MLSS': 3000,
        'Y': 0.67,
        'kd': 0.06,
        'SRT': 10
    }

st.sidebar.title('Projects')
project_list = list(st.session_state.projects.keys())
selected = st.sidebar.selectbox('Select:', project_list)
if selected != st.session_state.current_project:
    st.session_state.current_project = selected
    log_activity('project_switch', selected)

st.sidebar.divider()
with st.sidebar.expander("➕ Add New Project"):
    with st.form("add_project_form"):
        project_key = st.text_input("Project Key:", placeholder="e.g., project2")
        project_name = st.text_input("Project Name:", placeholder="e.g., Project Name")
        submitted = st.form_submit_button("Add Project")
        if submitted:
            if project_key and project_name:
                if project_key not in st.session_state.projects:
                    st.session_state.projects[project_key] = project_name
                    st.success(f"Added project: {project_key}")
                    st.rerun()
                else:
                    st.error(f"Project key '{project_key}' already exists!")
            else:
                st.error("Please fill in both fields!")

st.sidebar.divider()
st.sidebar.subheader('📋 Design Journal')
if st.session_state.log:
    st.sidebar.dataframe(
        pd.DataFrame(st.session_state.log[-10:])[['timestamp', 'action', 'details']],
        use_container_width=True
    )

st.title(f'WWTP Design Portfolio v1.0 - {st.session_state.projects[st.session_state.current_project]}')

defaults = get_defaults()
st.write(defaults)

# Test section
with st.expander("🔍 Session State Test"):
    st.write(f"Length of log: {len(st.session_state.log)}")
    st.write(f"Current project: {st.session_state.current_project}")
    st.write(f"Projects: {st.session_state.projects}")
    st.write(f"Full session state: {st.session_state}")

tab1, tab2, tab3, tab4 = st.tabs(['Mass Balance','P&ID + Equipment List','Hydraulic Design','Control Philosophy'])
