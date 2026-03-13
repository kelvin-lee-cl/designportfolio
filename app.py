import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import fsolve
from datetime import datetime
import json
import os
import html
import uuid
from io import BytesIO
import base64

if 'projects' not in st.session_state:
    st.session_state.projects = {'current': 'IPRC WEST'}
if 'log' not in st.session_state:
    st.session_state.log = []
if 'current_project' not in st.session_state:
    st.session_state.current_project = 'current'
if 'mb_inputs' not in st.session_state:
    st.session_state.mb_inputs = {}
if 'wwtp_design' not in st.session_state:
    st.session_state.wwtp_design = {
        'chain': 'Standard:Headworks→Primary→Aeration→Sec→UV',
        'inputs': {},
        'custom_code': ''
    }
if 'wwtp_overview' not in st.session_state:
    st.session_state.wwtp_overview = {
        'sections': [],
        'flow_connections': []
    }

# Project data storage path
PROJECTS_DIR = "projects_data"
if not os.path.exists(PROJECTS_DIR):
    os.makedirs(PROJECTS_DIR)

# Reference files storage path (for NAS deployment)
REFERENCE_FILES_DIR = "reference_files"
if not os.path.exists(REFERENCE_FILES_DIR):
    os.makedirs(REFERENCE_FILES_DIR)

def get_reference_file_path(project_key, ref_id, filename):
    """Get the file path for a reference file"""
    project_ref_dir = os.path.join(REFERENCE_FILES_DIR, project_key)
    if not os.path.exists(project_ref_dir):
        os.makedirs(project_ref_dir)
    # Sanitize filename
    safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
    return os.path.join(project_ref_dir, f"ref_{ref_id}_{safe_filename}")

def save_reference_file(project_key, ref_id, filename, file_data):
    """Save a reference file to disk"""
    file_path = get_reference_file_path(project_key, ref_id, filename)
    with open(file_path, 'wb') as f:
        if isinstance(file_data, bytes):
            f.write(file_data)
        else:
            f.write(file_data.read())
    return file_path

def load_reference_file(file_path):
    """Load a reference file from disk"""
    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            return f.read()
    return None

def delete_reference_file(file_path):
    """Delete a reference file from disk"""
    if os.path.exists(file_path):
        os.remove(file_path)

def save_project_data(project_key):
    """Save all project data to JSON file"""
    # Prepare references - files are stored on disk, only save metadata
    references_to_save = {}
    if 'references' in st.session_state:
        references_to_save = {}
        for section_key, ref_list in st.session_state.references.items():
            references_to_save[section_key] = []
            for ref in ref_list:
                ref_copy = ref.copy()
                # Remove file_data if exists (files are stored on disk)
                if 'file_data' in ref_copy:
                    del ref_copy['file_data']
                # Keep file_path for reference
                references_to_save[section_key].append(ref_copy)
    
    project_data = {
        'project_name': st.session_state.projects.get(project_key, ''),
        'wwtp_design': st.session_state.get('wwtp_design', {}),
        'wwtp_overview': st.session_state.get('wwtp_overview', {}),
        'mass_balance': st.session_state.get('mass_balance', {}),
        'equipment_list': st.session_state.get('equipment_list', {}),
        'hydraulic_design': st.session_state.get('hydraulic_design', {}),
        'control_philosophy': st.session_state.get('control_philosophy', {}),
        'default_parameters': st.session_state.get('project_defaults', {}),
        'default_parameters_units': st.session_state.get('project_default_units', {}),
        'default_parameters_remarks': st.session_state.get('project_default_remarks', {}),
        'default_parameters_custom': st.session_state.get('project_defaults_custom', {'flow': [], 'kinetic': [], 'system': []}),
        'design_requirements': st.session_state.get('design_requirements', []),
        'python_coding_guide_cards': st.session_state.get('python_coding_guide_cards', []),
        'references': references_to_save,
        'reference_counter': st.session_state.get('reference_counter', 1),
        'saved_at': datetime.now().isoformat()
    }
    
    file_path = os.path.join(PROJECTS_DIR, f"{project_key}.json")
    with open(file_path, 'w') as f:
        json.dump(project_data, f, indent=2, default=str)
    
    # Store last save time
    st.session_state[f'last_save_{project_key}'] = datetime.now().isoformat()
    return file_path

def convert_numeric_values(obj):
    """Recursively convert numeric values to floats to ensure type consistency"""
    if isinstance(obj, dict):
        return {k: convert_numeric_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numeric_values(item) for item in obj]
    elif isinstance(obj, (int, float)):
        return float(obj)
    else:
        return obj

def load_project_data(project_key):
    """Load project data from JSON file"""
    file_path = os.path.join(PROJECTS_DIR, f"{project_key}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                project_data = json.load(f)
            
            # Restore project name
            if 'project_name' in project_data:
                st.session_state.projects[project_key] = project_data['project_name']
            
            # Restore session state with numeric conversion
            if 'wwtp_design' in project_data:
                st.session_state.wwtp_design = convert_numeric_values(project_data['wwtp_design'])
            if 'wwtp_overview' in project_data:
                wwtp_overview = convert_numeric_values(project_data['wwtp_overview'])
                # Ensure discharge structure exists (backward compatibility)
                if 'sewage_discharge' not in wwtp_overview:
                    wwtp_overview['sewage_discharge'] = {'section': None, 'values': {}}
                if 'sludge_discharge' not in wwtp_overview:
                    wwtp_overview['sludge_discharge'] = {'section': None, 'values': {}}
                st.session_state.wwtp_overview = wwtp_overview
            if 'mass_balance' in project_data:
                st.session_state.mass_balance = convert_numeric_values(project_data['mass_balance'])
            if 'equipment_list' in project_data:
                st.session_state.equipment_list = project_data['equipment_list']  # No conversion needed for strings
            if 'hydraulic_design' in project_data:
                st.session_state.hydraulic_design = convert_numeric_values(project_data['hydraulic_design'])
            if 'control_philosophy' in project_data:
                st.session_state.control_philosophy = convert_numeric_values(project_data['control_philosophy'])
            if 'default_parameters' in project_data:
                st.session_state.project_defaults = convert_numeric_values(project_data['default_parameters'])
            elif 'project_defaults' not in st.session_state:
                st.session_state.project_defaults = get_defaults()
            if 'default_parameters_units' in project_data:
                st.session_state.project_default_units = project_data['default_parameters_units']
            else:
                st.session_state.project_default_units = {
                    'Q_avg': 'm³/day', 'BOD_in': 'mg/L', 'TSS_in': 'mg/L',
                    'Y': '-', 'kd': 'day⁻¹', 'SRT': 'days', 'MLSS': 'mg/L'
                }
            if 'default_parameters_remarks' in project_data:
                st.session_state.project_default_remarks = project_data['default_parameters_remarks']
            else:
                st.session_state.project_default_remarks = {}
            if 'default_parameters_custom' in project_data:
                custom = project_data['default_parameters_custom']
                default_units = {'flow': 'm³/day', 'kinetic': '-', 'system': '-'}
                for cat in ('flow', 'kinetic', 'system'):
                    if cat not in custom or not isinstance(custom[cat], list):
                        custom[cat] = []
                    for item in custom[cat]:
                        if isinstance(item.get('value'), (int, float)):
                            item['value'] = float(item['value'])
                        if 'unit' not in item:
                            item['unit'] = default_units.get(cat, '-')
                        if 'remark' not in item:
                            item['remark'] = ''
                st.session_state.project_defaults_custom = custom
            else:
                st.session_state.project_defaults_custom = {'flow': [], 'kinetic': [], 'system': []}
            if 'design_requirements' in project_data:
                reqs = project_data['design_requirements']
                if isinstance(reqs, list):
                    for r in reqs:
                        if isinstance(r.get('value'), (int, float)):
                            r['value'] = float(r['value'])
                        if 'unit' not in r:
                            r['unit'] = '-'
                        if 'remark' not in r:
                            r['remark'] = ''
                    st.session_state.design_requirements = reqs
                else:
                    st.session_state.design_requirements = []
            elif 'design_requirements' not in st.session_state:
                st.session_state.design_requirements = []
            if 'python_coding_guide_cards' in project_data:
                st.session_state.python_coding_guide_cards = project_data['python_coding_guide_cards']
            elif 'python_coding_guide_cards' not in st.session_state:
                st.session_state.python_coding_guide_cards = []
            
            # Load references - files are stored on disk, only metadata in JSON
            if 'references' in project_data:
                references_loaded = {}
                max_ref_id = 0
                for section_key, ref_list in project_data['references'].items():
                    references_loaded[section_key] = []
                    for ref in ref_list:
                        ref_copy = ref.copy()
                        # Handle backward compatibility: if file_data exists (old format), migrate to disk
                        if 'file_data' in ref_copy:
                            # Old format with base64 data - migrate to disk
                            if ref_copy.get('_is_base64', False):
                                file_data = base64.b64decode(ref_copy['file_data'])
                            else:
                                file_data = ref_copy['file_data']
                            
                            # Save to disk if not already saved
                            if 'file_path' not in ref_copy or not os.path.exists(ref_copy['file_path']):
                                filename = ref_copy.get('filename', f"ref_{ref_copy.get('id', 'unknown')}.pdf")
                                if ref_copy.get('type') == 'image':
                                    if not filename.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                                        filename = f"{filename}.png"
                                file_path = save_reference_file(project_key, ref_copy.get('id', 0), filename, file_data)
                                ref_copy['file_path'] = file_path
                            
                            # Remove file_data from memory
                            del ref_copy['file_data']
                            if '_is_base64' in ref_copy:
                                ref_copy.pop('_is_base64')
                        
                        references_loaded[section_key].append(ref_copy)
                        # Track max reference ID
                        if 'id' in ref_copy and ref_copy['id'] > max_ref_id:
                            max_ref_id = ref_copy['id']
                st.session_state.references = references_loaded
                # Set counter to max ID + 1 to avoid conflicts
                if 'reference_counter' in project_data:
                    st.session_state.reference_counter = max(project_data['reference_counter'], max_ref_id + 1)
                else:
                    st.session_state.reference_counter = max_ref_id + 1
            elif 'references' not in st.session_state:
                st.session_state.references = {
                    'section_1': [],
                    'section_2': [],
                    'section_3': []
                }
            
            if 'reference_counter' not in st.session_state:
                st.session_state.reference_counter = 1
            
            return True
        except Exception as e:
            st.sidebar.error(f"Error loading project: {str(e)}")
            return False
    return False

def log_activity(action: str, details: str):
    st.session_state.log.append({
        'timestamp': datetime.now().isoformat(),
        'project': st.session_state.current_project,
        'action': action,
        'details': details
    })

def get_defaults():
    """Default parameters (m³/day for flow). Save per project; one set of defaults."""
    return {
        'Q_avg': 60000,
        'BOD_in': 250,
        'TSS_in': 220,
        'MLSS': 3000,
        'Y': 0.67,
        'kd': 0.06,
        'SRT': 10
    }

def get_flow_loading_conc_params():
    """
    Returns list of (default_key, mb_key) for Flow & Loading concentration params.
    Built-in: BOD_in->BOD, TSS_in->TSS. Custom: e.g. COD_in->COD (params with mg/L-type units).
    Excludes Q_avg (flow).
    """
    result = [('BOD_in', 'BOD'), ('TSS_in', 'TSS')]
    custom = st.session_state.get('project_defaults_custom', {'flow': []})
    conc_units = ('mg/L', 'mg/l', 'g/m³', 'g/m3', 'ppm')
    for p in custom.get('flow', []):
        name = p.get('name', '').strip()
        u = (p.get('unit', '') or '').strip()
        if not name or name == 'Q_avg':
            continue
        if any(cu in u for cu in conc_units):
            mb_key = name[:-3] if name.endswith('_in') else name
            result.append((name, mb_key))
    return result

def _get_conc_val_from_defaults(default_key, defaults, custom_flow):
    """Get concentration value for a param from project defaults or custom flow."""
    if default_key in ('BOD_in', 'TSS_in'):
        return float(defaults.get(default_key, 250 if default_key == 'BOD_in' else 220))
    for p in custom_flow:
        if p.get('name') == default_key:
            return float(p.get('value', 0))
    return 0.0

def _get_conc_from_mb(mb_dict, mb_key):
    """Get concentration from intake/outlet/return_flow dict."""
    return float(mb_dict.get(mb_key, 0.0))

def get_chain_parameters(chain_type):
    """Get chain-specific parameter definitions"""
    chain_configs = {
        'Standard:Headworks→Primary→Aeration→Sec→UV': {
            'params': ['Primary_rem%'],
            'defaults': {'Primary_rem%': 30}
        },
        'Compact:Primary→MBBR→UF': {
            'params': ['Primary_rem%', 'MBBR_fill%'],
            'defaults': {'Primary_rem%': 25, 'MBBR_fill%': 65}
        },
        'Advanced:Primary→A2O→MBR→UV': {
            'params': ['Primary_rem%', 'A2O_stages'],
            'defaults': {'Primary_rem%': 35, 'A2O_stages': 3}
        },
        'Custom': {
            'params': [],
            'defaults': {}
        }
    }
    return chain_configs.get(chain_type, chain_configs['Custom'])

def residuals(vars):
    V, RAS = vars
    defaults = get_defaults()
    mb_inputs = st.session_state.get('mb_inputs', {})
    Y = mb_inputs.get('Y', defaults['Y'])
    BOD = mb_inputs.get('BOD_in', defaults['BOD_in'])
    Q = mb_inputs.get('Q_avg', defaults['Q_avg'])
    MLSS = defaults['MLSS']
    kd = defaults['kd']
    SRT = defaults['SRT']
    mu = Y * (BOD / 1e6 * Q) / (V * MLSS / 1e6) - kd
    return np.array([mu * SRT - 1, RAS - 0.5])

st.sidebar.title('Projects')
project_list = list(st.session_state.projects.keys())
selected = st.sidebar.selectbox('Select:', project_list)

# Auto-load project data on first run or when switching
if 'project_loaded' not in st.session_state or st.session_state.get('last_loaded_project') != selected:
    load_project_data(selected)
    st.session_state.last_loaded_project = selected
    st.session_state.project_loaded = True

if selected != st.session_state.current_project:
    st.session_state.current_project = selected
    # Load project data when switching
    load_project_data(selected)
    log_activity('project_switch', selected)

st.sidebar.divider()
with st.sidebar.expander("➕ Add New Project"):
    with st.form("add_project_form", enter_to_submit=False):
        project_key = st.text_input("Project Key:", placeholder="e.g., project2")
        project_name = st.text_input("Project Name:", placeholder="e.g., Project Name")
        submitted = st.form_submit_button("➕", help="Add Project")
        if submitted:
            if project_key and project_name:
                if project_key not in st.session_state.projects:
                    st.session_state.projects[project_key] = project_name
                    # Initialize defaults for new project
                    if 'project_defaults' not in st.session_state:
                        st.session_state.project_defaults = get_defaults()
                    st.success(f"Added project: {project_key}")
                    log_activity('project_added', f"{project_key}: {project_name}")
                    st.rerun()
                else:
                    st.error(f"Project key '{project_key}' already exists!")
            else:
                st.error("Please fill in both fields!")

st.sidebar.divider()
with st.sidebar.expander("💾 Load Project"):
    project_files = [f.replace('.json', '') for f in os.listdir(PROJECTS_DIR) if f.endswith('.json')] if os.path.exists(PROJECTS_DIR) else []
    if project_files:
        load_project = st.selectbox("Select project to load:", [''] + project_files)
        if st.button("📂", help="Load Selected Project") and load_project:
            if load_project in st.session_state.projects:
                st.session_state.current_project = load_project
                load_project_data(load_project)
                st.success(f"✅ Loaded project: {load_project}")
                log_activity('project_loaded', load_project)
                st.rerun()
            else:
                st.error("Project not found in current session!")
    else:
        st.info("No saved projects found")


# Top bar with editable project name and save button
col_title_left, col_title_right = st.columns([5, 1])

with col_title_left:
    current_project_name = st.session_state.projects.get(st.session_state.current_project, 'New Project')
    
    # Initialize edit mode if not exists
    if 'project_name_edit_mode' not in st.session_state:
        st.session_state.project_name_edit_mode = False
    
    # Display project name - clickable to edit
    if not st.session_state.project_name_edit_mode:
        # Show project name as clickable text
        st.markdown(f"### 📁 {current_project_name}")
        if st.button("✏️", key="edit_name_btn", use_container_width=False, help="Edit Name"):
            st.session_state.project_name_edit_mode = True
            st.rerun()
    else:
        # Edit mode - show text input
        new_project_name = st.text_input(
            'Project Name:',
            value=current_project_name,
            key='project_name_input',
            label_visibility='visible'
        )
        col_edit1, col_edit2 = st.columns([1, 1])
        with col_edit1:
            if st.button('✅', key='save_name_btn', type='primary', help='Save'):
                if new_project_name.strip():
                    st.session_state.projects[st.session_state.current_project] = new_project_name.strip()
                    st.session_state.project_name_edit_mode = False
                    log_activity('project_name_changed', f"Changed to {new_project_name.strip()}")
                    st.rerun()
        with col_edit2:
            if st.button('❌', key='cancel_name_btn', help='Cancel'):
                st.session_state.project_name_edit_mode = False
                st.rerun()

with col_title_right:
    # Save button in top right corner (icon only)
    if st.button('💾', type='primary', use_container_width=True, help='Save Project'):
        try:
            file_path = save_project_data(st.session_state.current_project)
            st.success(f"✅ Project saved!")
            log_activity('project_saved', st.session_state.current_project)
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error saving project: {str(e)}")
    
    # Show last save time
    last_save_key = f'last_save_{st.session_state.current_project}'
    if last_save_key in st.session_state:
        save_time = st.session_state[last_save_key]
        try:
            save_dt = datetime.fromisoformat(save_time)
            st.caption(f"Last: {save_dt.strftime('%m/%d %H:%M')}")
        except:
            pass

# Default units for built-in parameters (flow in m³/day)
DEFAULT_PARAM_UNITS = {
    'Q_avg': 'm³/day',
    'BOD_in': 'mg/L',
    'TSS_in': 'mg/L',
    'Y': '-',
    'kd': 'day⁻¹',
    'SRT': 'days',
    'MLSS': 'mg/L'
}

# Initialize project defaults if not exists
if 'project_defaults' not in st.session_state:
    st.session_state.project_defaults = get_defaults()
if 'project_default_units' not in st.session_state:
    st.session_state.project_default_units = dict(DEFAULT_PARAM_UNITS)
if 'project_defaults_custom' not in st.session_state:
    st.session_state.project_defaults_custom = {'flow': [], 'kinetic': [], 'system': []}
if 'default_param_editing' not in st.session_state:
    st.session_state.default_param_editing = None  # e.g. 'Q_avg', 'flow_0'
if 'show_param_edit_buttons' not in st.session_state:
    st.session_state.show_param_edit_buttons = False
if 'show_add_param_forms' not in st.session_state:
    st.session_state.show_add_param_forms = False
if 'show_param_remarks' not in st.session_state:
    st.session_state.show_param_remarks = False
if 'design_requirements' not in st.session_state:
    st.session_state.design_requirements = []
if 'python_coding_guide_cards' not in st.session_state:
    st.session_state.python_coding_guide_cards = []
if 'design_requirement_editing' not in st.session_state:
    st.session_state.design_requirement_editing = None
if 'dr_show_edit_buttons' not in st.session_state:
    st.session_state.dr_show_edit_buttons = False
if 'dr_show_remarks' not in st.session_state:
    st.session_state.dr_show_remarks = False
if 'dr_show_add_form' not in st.session_state:
    st.session_state.dr_show_add_form = False
if 'project_default_remarks' not in st.session_state:
    st.session_state.project_default_remarks = {}

# Editable Default Parameters - display as "Name = value (unit)", click to edit; remark on hover
with st.expander("📋 Design Parameters", expanded=False):
    # Buttons first (no space above)
    _col_edit, _col_remark, _col_add = st.columns([1, 1, 1])
    with _col_edit:
        _edit_label = "Done" if st.session_state.show_param_edit_buttons else "Edit"
        if st.button(_edit_label, key="param_edit_toggle", help="Show/hide Edit buttons for each parameter"):
            st.session_state.show_param_edit_buttons = not st.session_state.show_param_edit_buttons
            st.rerun()
    with _col_remark:
        _remark_label = "Done" if st.session_state.show_param_remarks else "Remark"
        if st.button(_remark_label, key="param_remark_toggle", help="Show/hide all parameter remarks"):
            st.session_state.show_param_remarks = not st.session_state.show_param_remarks
            st.rerun()
    with _col_add:
        _add_label = "Done" if st.session_state.show_add_param_forms else "Add"
        if st.button(_add_label, key="param_add_toggle", help="Show/hide Add parameter forms"):
            st.session_state.show_add_param_forms = not st.session_state.show_add_param_forms
            st.rerun()
    # CSS: reduce expander top padding and remove gap between buttons and three columns
    st.markdown("""
    <style>
    /* Less top padding in expander content */
    section[data-testid="stExpander"] details > div {
        padding-top: 0 !important;
    }
    /* No gap between button row and content below (tight vertical spacing) */
    section[data-testid="stExpander"] [data-testid="stVerticalBlock"] > div {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        padding-top: 0.15rem !important;
        padding-bottom: 0.15rem !important;
    }
    .default-params-section .param-row {
        display: inline-block;
        padding: 2px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="default-params-section">', unsafe_allow_html=True)
    defaults = st.session_state.project_defaults
    units = st.session_state.project_default_units
    remarks = st.session_state.project_default_remarks
    for k in DEFAULT_PARAM_UNITS:
        if k not in units:
            units[k] = DEFAULT_PARAM_UNITS[k]
        if k not in remarks:
            remarks[k] = ''
    custom = st.session_state.project_defaults_custom
    editing = st.session_state.default_param_editing
    
    def fmt_display_val(v, max_decimals=6):
        """Format number; no decimals when value is whole (e.g. 250.0 -> 250)."""
        f = float(v)
        if f == int(f):
            return str(int(f))
        s = f"{f:.{max_decimals}f}".rstrip('0').rstrip('.')
        return s

    def fmt_val(k, v):
        if k == 'Q_avg':
            return fmt_display_val(v, 6)
        if k in ('Y', 'kd'):
            return fmt_display_val(v, 3)
        if k == 'SRT':
            return str(int(v))
        return fmt_display_val(v, 2)
    
    def param_line_with_tooltip(name, val_str, u, remark):
        r = (remark or '').strip()
        title_attr = f' title="{html.escape(r)}"' if r else ''
        inner = f'<b>{html.escape(str(name))}</b> = {html.escape(str(val_str))} ({html.escape(str(u))})'
        return f'<div class="param-row"{title_attr}>{inner}</div>'
    
    col_def1, col_def2, col_def3 = st.columns(3)
    
    # --- Flow & Loading ---
    with col_def1:
        st.markdown("**Flow & Loading**")
        
        for key in ['Q_avg', 'BOD_in', 'TSS_in']:
            edit_key = key
            if editing == edit_key:
                new_val = st.number_input("Value", value=float(defaults.get(key, 60000 if key == 'Q_avg' else 0)), step=1000.0 if key == 'Q_avg' else 10.0, format="%.2f" if key == 'Q_avg' else "%.2f", key=f"edit_val_{key}")
                new_unit = st.text_input("Unit", value=units.get(key, 'm³/day'), key=f"edit_unit_{key}")
                new_remark = st.text_input("Remark", value=remarks.get(key, ''), key=f"edit_remark_{key}", placeholder="Hover to see this note")
                if st.button("✅", key=f"save_{key}", help="Save"):
                    defaults[key] = new_val
                    units[key] = new_unit.strip() or units.get(key, '')
                    remarks[key] = new_remark.strip()
                    st.session_state.default_param_editing = None
                    st.rerun()
                if st.button("❌", key=f"cancel_{key}", help="Cancel"):
                    st.session_state.default_param_editing = None
                    st.rerun()
            else:
                val_str = fmt_val(key, defaults.get(key, 60000 if key == 'Q_avg' else 0))
                u = units.get(key, '')
                st.markdown(param_line_with_tooltip(key, val_str, u, remarks.get(key, '')), unsafe_allow_html=True)
                if st.session_state.show_param_remarks:
                    _r = (remarks.get(key, '') or '').strip()
                    if _r:
                        st.caption(_r)
                if st.session_state.show_param_edit_buttons and st.button("✏️", key=f"edit_btn_{key}", help="Edit"):
                    st.session_state.default_param_editing = edit_key
                    st.rerun()
        
        for i, p in enumerate(list(custom['flow'])):
            edit_key = f"flow_{i}"
            if editing == edit_key:
                new_name = st.text_input("Name", value=p.get('name', ''), key=f"edit_flow_name_{i}")
                new_val = st.number_input("Value", value=float(p.get('value', 0)), step=0.0001, format="%.6f", key=f"edit_flow_val_{i}")
                new_unit = st.text_input("Unit", value=p.get('unit', 'm³/day'), key=f"edit_flow_unit_{i}")
                new_remark = st.text_input("Remark", value=p.get('remark', ''), key=f"edit_flow_remark_{i}", placeholder="Hover to see this note")
                if st.button("✅", key=f"save_flow_{i}", help="Save"):
                    if new_name and new_name.strip():
                        p['name'] = new_name.strip()
                    p['value'] = new_val
                    p['unit'] = new_unit.strip() or 'm³/day'
                    p['remark'] = new_remark.strip()
                    st.session_state.default_param_editing = None
                    st.rerun()
                if st.button("❌", key=f"cancel_flow_{i}", help="Cancel"):
                    st.session_state.default_param_editing = None
                    st.rerun()
                if st.button("🗑️", key=f"del_flow_{i}", help="Delete"):
                    custom['flow'].pop(i)
                    st.session_state.default_param_editing = None
                    st.rerun()
            else:
                val_str = fmt_display_val(p.get('value', 0), 6)
                u = p.get('unit', 'm³/day')
                st.markdown(param_line_with_tooltip(p.get('name', ''), val_str, u, p.get('remark', '')), unsafe_allow_html=True)
                if st.session_state.show_param_remarks:
                    _r = (p.get('remark', '') or '').strip()
                    if _r:
                        st.caption(_r)
                if st.session_state.show_param_edit_buttons and st.button("✏️", key=f"edit_btn_flow_{i}", help="Edit"):
                    st.session_state.default_param_editing = edit_key
                    st.rerun()
        
        if st.session_state.show_add_param_forms:
            with st.form("add_flow_param", enter_to_submit=False):
                new_name = st.text_input("Parameter name", key="new_flow_name", placeholder="e.g. NH3_in")
                new_val = st.number_input("Value", value=0.0, step=0.0001, format="%.6f", key="new_flow_val")
                new_unit = st.text_input("Unit", value="m³/day", key="new_flow_unit")
                new_remark = st.text_input("Remark (optional)", key="new_flow_remark", placeholder="e.g. Influent concentration")
                if st.form_submit_button("➕", help="Add"):
                    if new_name and new_name.strip():
                        name = new_name.strip()
                        if not any(x['name'] == name for x in custom['flow']):
                            custom['flow'].append({'name': name, 'value': float(new_val), 'unit': new_unit.strip() or 'm³/day', 'remark': (new_remark or '').strip()})
                            st.rerun()
    
    # --- Kinetic ---
    with col_def2:
        st.markdown("**Kinetic Parameters**")
        
        for key in ['Y', 'kd', 'SRT']:
            edit_key = key
            if editing == edit_key:
                new_val = st.number_input("Value", value=float(defaults.get(key, 0.67 if key == 'Y' else 0.06 if key == 'kd' else 10)), step=0.01 if key == 'Y' else 0.001 if key == 'kd' else 1, format="%.2f" if key == 'Y' else "%.3f" if key == 'kd' else "%d", key=f"edit_val_{key}")
                new_unit = st.text_input("Unit", value=units.get(key, '-'), key=f"edit_unit_{key}")
                new_remark = st.text_input("Remark", value=remarks.get(key, ''), key=f"edit_remark_{key}", placeholder="Hover to see this note")
                if st.button("✅", key=f"save_{key}", help="Save"):
                    defaults[key] = int(new_val) if key == 'SRT' else new_val
                    units[key] = new_unit.strip() or units.get(key, '')
                    remarks[key] = new_remark.strip()
                    st.session_state.default_param_editing = None
                    st.rerun()
                if st.button("❌", key=f"cancel_{key}", help="Cancel"):
                    st.session_state.default_param_editing = None
                    st.rerun()
            else:
                val_str = fmt_val(key, defaults.get(key, 0))
                u = units.get(key, '')
                st.markdown(param_line_with_tooltip(key, val_str, u, remarks.get(key, '')), unsafe_allow_html=True)
                if st.session_state.show_param_remarks:
                    _r = (remarks.get(key, '') or '').strip()
                    if _r:
                        st.caption(_r)
                if st.session_state.show_param_edit_buttons and st.button("✏️", key=f"edit_btn_{key}", help="Edit"):
                    st.session_state.default_param_editing = edit_key
                    st.rerun()
        
        for i, p in enumerate(list(custom['kinetic'])):
            edit_key = f"kinetic_{i}"
            if editing == edit_key:
                new_name = st.text_input("Name", value=p.get('name', ''), key=f"edit_kinetic_name_{i}")
                new_val = st.number_input("Value", value=float(p.get('value', 0)), step=0.001, format="%.3f", key=f"edit_kinetic_val_{i}")
                new_unit = st.text_input("Unit", value=p.get('unit', '-'), key=f"edit_kinetic_unit_{i}")
                new_remark = st.text_input("Remark", value=p.get('remark', ''), key=f"edit_kinetic_remark_{i}", placeholder="Hover to see this note")
                if st.button("✅", key=f"save_kinetic_{i}", help="Save"):
                    if new_name and new_name.strip():
                        p['name'] = new_name.strip()
                    p['value'] = new_val
                    p['unit'] = new_unit.strip() or '-'
                    p['remark'] = new_remark.strip()
                    st.session_state.default_param_editing = None
                    st.rerun()
                if st.button("❌", key=f"cancel_kinetic_{i}", help="Cancel"):
                    st.session_state.default_param_editing = None
                    st.rerun()
                if st.button("🗑️", key=f"del_kinetic_{i}", help="Delete"):
                    custom['kinetic'].pop(i)
                    st.session_state.default_param_editing = None
                    st.rerun()
            else:
                val_str = fmt_display_val(p.get('value', 0), 3)
                u = p.get('unit', '-')
                st.markdown(param_line_with_tooltip(p.get('name', ''), val_str, u, p.get('remark', '')), unsafe_allow_html=True)
                if st.session_state.show_param_remarks:
                    _r = (p.get('remark', '') or '').strip()
                    if _r:
                        st.caption(_r)
                if st.session_state.show_param_edit_buttons and st.button("✏️", key=f"edit_btn_kinetic_{i}", help="Edit"):
                    st.session_state.default_param_editing = edit_key
                    st.rerun()
        
        if st.session_state.show_add_param_forms:
            with st.form("add_kinetic_param", enter_to_submit=False):
                new_name = st.text_input("Parameter name", key="new_kinetic_name", placeholder="e.g. Ks")
                new_val = st.number_input("Value", value=0.0, step=0.001, format="%.3f", key="new_kinetic_val")
                new_unit = st.text_input("Unit", value="-", key="new_kinetic_unit")
                new_remark = st.text_input("Remark (optional)", key="new_kinetic_remark", placeholder="e.g. Half-saturation constant")
                if st.form_submit_button("➕", help="Add"):
                    if new_name and new_name.strip():
                        name = new_name.strip()
                        if not any(x['name'] == name for x in custom['kinetic']):
                            custom['kinetic'].append({'name': name, 'value': float(new_val), 'unit': new_unit.strip() or '-', 'remark': (new_remark or '').strip()})
                            st.rerun()
    
    # --- System ---
    with col_def3:
        st.markdown("**System Parameters**")
        
        key = 'MLSS'
        if editing == key:
            new_val = st.number_input("Value", value=float(defaults.get(key, 3000)), step=100.0, key=f"edit_val_{key}")
            new_unit = st.text_input("Unit", value=units.get(key, 'mg/L'), key=f"edit_unit_{key}")
            new_remark = st.text_input("Remark", value=remarks.get(key, ''), key=f"edit_remark_{key}", placeholder="Hover to see this note")
            if st.button("✅", key=f"save_{key}", help="Save"):
                defaults[key] = new_val
                units[key] = new_unit.strip() or 'mg/L'
                remarks[key] = new_remark.strip()
                st.session_state.default_param_editing = None
                st.rerun()
            if st.button("❌", key=f"cancel_{key}", help="Cancel"):
                st.session_state.default_param_editing = None
                st.rerun()
        else:
            val_str = fmt_val(key, defaults.get(key, 3000))
            u = units.get(key, 'mg/L')
            st.markdown(param_line_with_tooltip(key, val_str, u, remarks.get(key, '')), unsafe_allow_html=True)
            if st.session_state.show_param_remarks:
                _r = (remarks.get(key, '') or '').strip()
                if _r:
                    st.caption(_r)
            if st.session_state.show_param_edit_buttons and st.button("✏️", key=f"edit_btn_{key}", help="Edit"):
                st.session_state.default_param_editing = key
                st.rerun()
        
        for i, p in enumerate(list(custom['system'])):
            edit_key = f"system_{i}"
            if editing == edit_key:
                new_name = st.text_input("Name", value=p.get('name', ''), key=f"edit_system_name_{i}")
                new_val = st.number_input("Value", value=float(p.get('value', 0)), step=1.0, key=f"edit_system_val_{i}")
                new_unit = st.text_input("Unit", value=p.get('unit', '-'), key=f"edit_system_unit_{i}")
                new_remark = st.text_input("Remark", value=p.get('remark', ''), key=f"edit_system_remark_{i}", placeholder="Hover to see this note")
                if st.button("✅", key=f"save_system_{i}", help="Save"):
                    if new_name and new_name.strip():
                        p['name'] = new_name.strip()
                    p['value'] = new_val
                    p['unit'] = new_unit.strip() or '-'
                    p['remark'] = new_remark.strip()
                    st.session_state.default_param_editing = None
                    st.rerun()
                if st.button("❌", key=f"cancel_system_{i}", help="Cancel"):
                    st.session_state.default_param_editing = None
                    st.rerun()
                if st.button("🗑️", key=f"del_system_{i}", help="Delete"):
                    custom['system'].pop(i)
                    st.session_state.default_param_editing = None
                    st.rerun()
            else:
                val_str = fmt_display_val(p.get('value', 0), 2)
                u = p.get('unit', '-')
                st.markdown(param_line_with_tooltip(p.get('name', ''), val_str, u, p.get('remark', '')), unsafe_allow_html=True)
                if st.session_state.show_param_remarks:
                    _r = (p.get('remark', '') or '').strip()
                    if _r:
                        st.caption(_r)
                if st.session_state.show_param_edit_buttons and st.button("✏️", key=f"edit_btn_system_{i}", help="Edit"):
                    st.session_state.default_param_editing = edit_key
                    st.rerun()
        
        if st.session_state.show_add_param_forms:
            with st.form("add_system_param", enter_to_submit=False):
                new_name = st.text_input("Parameter name", key="new_system_name", placeholder="e.g. HRT")
                new_val = st.number_input("Value", value=0.0, step=1.0, key="new_system_val")
                new_unit = st.text_input("Unit", value="-", key="new_system_unit")
                new_remark = st.text_input("Remark (optional)", key="new_system_remark", placeholder="e.g. Hydraulic retention time")
                if st.form_submit_button("➕", help="Add"):
                    if new_name and new_name.strip():
                        name = new_name.strip()
                        if not any(x['name'] == name for x in custom['system']):
                            custom['system'].append({'name': name, 'value': float(new_val), 'unit': new_unit.strip() or '-', 'remark': (new_remark or '').strip()})
                            st.rerun()
    
    st.session_state.project_defaults = defaults
    st.session_state.project_default_units = units
    st.session_state.project_default_remarks = remarks
    st.session_state.project_defaults_custom = custom
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    with st.expander("📄 View as JSON", expanded=False):
        merged = dict(defaults)
        merged_units = dict(units)
        for cat_name, cat_key in [('Flow & Loading', 'flow'), ('Kinetic', 'kinetic'), ('System', 'system')]:
            for p in custom[cat_key]:
                merged[f"({cat_name}) {p['name']}"] = p['value']
                merged_units[f"({cat_name}) {p['name']}"] = p.get('unit', '-')
        st.json({"values": merged, "units": merged_units})

# Design Requirement (name = value (unit), like Flow & Loading)
with st.expander("📋 Design Requirement", expanded=False):
    # Edit, Remark, Add buttons (same behavior as Default Parameters)
    _dr_col_edit, _dr_col_remark, _dr_col_add = st.columns([1, 1, 1])
    with _dr_col_edit:
        _dr_edit_label = "Done" if st.session_state.dr_show_edit_buttons else "Edit"
        if st.button(_dr_edit_label, key="dr_edit_toggle", help="Show/hide Edit buttons for each requirement"):
            st.session_state.dr_show_edit_buttons = not st.session_state.dr_show_edit_buttons
            st.rerun()
    with _dr_col_remark:
        _dr_remark_label = "Done" if st.session_state.dr_show_remarks else "Remark"
        if st.button(_dr_remark_label, key="dr_remark_toggle", help="Show/hide all requirement remarks"):
            st.session_state.dr_show_remarks = not st.session_state.dr_show_remarks
            st.rerun()
    with _dr_col_add:
        _dr_add_label = "Done" if st.session_state.dr_show_add_form else "Add"
        if st.button(_dr_add_label, key="dr_add_toggle", help="Show/hide Add requirement form"):
            st.session_state.dr_show_add_form = not st.session_state.dr_show_add_form
            st.rerun()

    reqs = st.session_state.design_requirements
    editing_req = st.session_state.design_requirement_editing
    st.markdown('<div class="default-params-section">', unsafe_allow_html=True)

    def req_line_display(name, val_str, unit, remark):
        r = (remark or '').strip()
        title_attr = f' title="{html.escape(r)}"' if r else ''
        inner = f'<b>{html.escape(str(name))}</b> = {html.escape(str(val_str))} ({html.escape(str(unit))})'
        return f'<div class="param-row"{title_attr}>{inner}</div>'

    for i, r in enumerate(list(reqs)):
        name = r.get('name', '')
        value = r.get('value', 0)
        unit = r.get('unit', '-')
        remark = r.get('remark', '')
        if editing_req == i:
            new_name = st.text_input("Name", value=name, key=f"dr_name_{i}")
            new_val = st.number_input("Value", value=float(value), step=0.01, format="%.2f", key=f"dr_val_{i}")
            new_unit = st.text_input("Unit", value=unit, key=f"dr_unit_{i}")
            new_remark = st.text_input("Remark (optional)", value=remark, key=f"dr_remark_{i}")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("✅ Save", key=f"dr_save_{i}"):
                    if new_name and new_name.strip():
                        r['name'] = new_name.strip()
                    r['value'] = new_val
                    r['unit'] = (new_unit or '-').strip()
                    r['remark'] = (new_remark or '').strip()
                    st.session_state.design_requirement_editing = None
                    st.rerun()
            with c2:
                if st.button("❌ Cancel", key=f"dr_cancel_{i}"):
                    st.session_state.design_requirement_editing = None
                    st.rerun()
            with c3:
                if st.button("🗑️ Delete", key=f"dr_del_{i}"):
                    st.session_state.design_requirements.pop(i)
                    st.session_state.design_requirement_editing = None
                    st.rerun()
        else:
            val_str = f"{value:.2f}".rstrip('0').rstrip('.') if isinstance(value, float) else str(value)
            st.markdown(req_line_display(name, val_str, unit, remark), unsafe_allow_html=True)
            if st.session_state.dr_show_remarks:
                _r = (remark or '').strip()
                if _r:
                    st.caption(_r)
            if st.session_state.dr_show_edit_buttons and st.button("✏️", key=f"dr_edit_{i}", help="Edit"):
                st.session_state.design_requirement_editing = i
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    if st.session_state.dr_show_add_form:
        with st.form("add_design_requirement", enter_to_submit=False):
            st.markdown("**Add requirement**")
            add_name = st.text_input("Name", key="dr_add_name", placeholder="e.g. BOD_out")
            add_val = st.number_input("Value", value=0.0, step=0.1, format="%.2f", key="dr_add_val")
            add_unit = st.text_input("Unit", value="mg/L", key="dr_add_unit", placeholder="e.g. mg/L")
            add_remark = st.text_input("Remark (optional)", key="dr_add_remark", placeholder="Optional note")
            if st.form_submit_button("➕ Add"):
                if add_name and add_name.strip():
                    n = add_name.strip()
                    if not any(x.get('name') == n for x in st.session_state.design_requirements):
                        st.session_state.design_requirements.append({
                            'name': n,
                            'value': float(add_val),
                            'unit': (add_unit or 'mg/L').strip(),
                            'remark': (add_remark or '').strip()
                        })
                        st.rerun()

# Test section
with st.expander("🔍 Session State Test"):
    st.write(f"Length of log: {len(st.session_state.log)}")
    st.write(f"Current project: {st.session_state.current_project}")
    st.write(f"Projects: {st.session_state.projects}")
    st.write(f"Full session state: {st.session_state}")

# Main app tabs
tab0, tab1, tab2, tab3 = st.tabs(['Overview', 'Mass Balance', 'Reference', 'Python Coding Guide'])

# ==================== OVERVIEW TAB ====================
with tab0:
    st.header('🏗️ WWTP Process Flow Overview')
    st.caption("Define your WWTP sections and build the process flow diagram. Other tabs will reference this overview.")
    
    # Initialize overview structure
    if 'wwtp_overview' not in st.session_state:
        st.session_state.wwtp_overview = {
            'sections': [],
            'flow_connections': [],
            'sewage_discharge': {
                'section': None,
                'values': {}  # Will store BOD, TSS, etc.
            },
            'sludge_discharge': {
                'section': None,
                'values': {}  # Will store flow, solids, etc.
            }
        }
    
    overview = st.session_state.wwtp_overview
    
    # Initialize discharge structure if not exists (backward compatibility)
    if 'sewage_discharge' not in overview:
        overview['sewage_discharge'] = {'section': None, 'values': {}}
    if 'sludge_discharge' not in overview:
        overview['sludge_discharge'] = {'section': None, 'values': {}}
    
    # Sync flow_connections with effluent_to for all sections
    # This ensures consistency between effluent_to and flow_connections
    for section in overview['sections']:
        section_name = section['name']
        effluent_to_list = section.get('effluent_to', [])
        
        # Remove old connections from this section
        overview['flow_connections'] = [
            conn for conn in overview['flow_connections'] 
            if conn['from'] != section_name
        ]
        
        # Add connections based on effluent_to
        for effluent_dest in effluent_to_list:
            # Check if connection already exists
            if not any(conn['from'] == section_name and conn['to'] == effluent_dest 
                      for conn in overview['flow_connections']):
                overview['flow_connections'].append({
                    'from': section_name,
                    'to': effluent_dest
                })
    
    # Section 1: Add/Edit WWTP Sections
    st.subheader('1️⃣ WWTP Sections')
    
    col_add1, col_add2 = st.columns([3, 1])
    
    with col_add1:
        new_section_name = st.text_input(
            'Add New Section:',
            placeholder='e.g., Headworks, Primary Clarifier, Aeration Tank',
            key='new_section_input'
        )
    
    with col_add2:
        st.write("")  # Spacing
        if st.button('➕', type='primary', help='Add Section'):
            if new_section_name.strip():
                if new_section_name.strip() not in [s['name'] for s in overview['sections']]:
                    overview['sections'].append({
                        'name': new_section_name.strip(),
                        'id': len(overview['sections']),
                        'has_return_flow': False,
                        'return_to': None,
                        'generates_sludge': False,
                        'sludge_to': None,
                        'effluent_to': [],  # List of sections where effluent goes
                        'flow_type': 'sewage',  # 'sewage', 'sludge', 'service_water'
                        'downstream': []
                    })
                    log_activity('section_added', new_section_name.strip())
                    st.success(f"✅ Added section: {new_section_name.strip()}")
                    st.rerun()
                else:
                    st.error("❌ Section name already exists!")
            else:
                st.error("❌ Please enter a section name!")
    
    # Display existing sections
    if overview['sections']:
        st.markdown("**Existing Sections:**")
        
        # Ensure all sections have required fields (backward compatibility)
        for section in overview['sections']:
            if 'flow_type' not in section:
                section['flow_type'] = 'sewage'
            if 'effluent_to' not in section:
                section['effluent_to'] = []
                # Migrate from old flow_connections if exists
                existing_connections = [conn['to'] for conn in overview['flow_connections'] if conn['from'] == section['name']]
                if existing_connections:
                    section['effluent_to'] = existing_connections
        
        for idx, section in enumerate(overview['sections']):
            # Determine icon based on flow_type
            flow_type = section.get('flow_type', 'sewage')
            if flow_type == 'sludge':
                icon = '🔴'
            elif flow_type == 'other':
                icon = '🟢'
            else:  # sewage (default)
                icon = '🔵'
            
            with st.expander(f"{icon} {section['name']}", expanded=False):
                col_sec1, col_sec2, col_sec3 = st.columns([2, 2, 1])
                
                with col_sec1:
                    st.write(f"**Section ID:** {section['id']}")
                    st.write(f"**Name:** {section['name']}")
                    
                    # Flow type selector
                    flow_type_map = {'sewage': 'Sewage', 'sludge': 'Sludge', 'other': 'Other'}
                    current_flow = section.get('flow_type', 'sewage')
                    if current_flow == 'service_water':  # Migrate old value
                        current_flow = 'other'
                        section['flow_type'] = 'other'
                    flow_type = st.selectbox(
                        'Flow Type:',
                        ['sewage', 'sludge', 'other'],
                        index=['sewage', 'sludge', 'other'].index(current_flow),
                        key=f'flow_type_{idx}'
                    )
                    section['flow_type'] = flow_type
                    
                    # Reorder buttons inside the expander
                    col_up_down = st.columns([1, 1])
                    with col_up_down[0]:
                        if idx > 0:
                            if st.button('⬆️', key=f'move_up_{idx}', help='Move section up'):
                                overview['sections'][idx], overview['sections'][idx-1] = overview['sections'][idx-1], overview['sections'][idx]
                                st.rerun()
                    with col_up_down[1]:
                        if idx < len(overview['sections']) - 1:
                            if st.button('⬇️', key=f'move_down_{idx}', help='Move section down'):
                                overview['sections'][idx], overview['sections'][idx+1] = overview['sections'][idx+1], overview['sections'][idx]
                                st.rerun()
                    
                    with col_sec2:
                        # Effluent destination (where does the effluent go)
                        st.markdown("**Effluent Flow:**")
                        
                        # Check if this section is set as final sewage discharge
                        is_final_sewage_discharge = overview.get('sewage_discharge', {}).get('section') == section['name']
                        
                        if is_final_sewage_discharge:
                            # This is the final sewage discharge - no effluent goes anywhere
                            st.info("📍 **Final Sewage Discharge** - No downstream effluent flow")
                            section['effluent_to'] = []
                            # Clear any existing connections from this section
                            overview['flow_connections'] = [
                                conn for conn in overview['flow_connections'] 
                                if conn['from'] != section['name']
                            ]
                        else:
                            effluent_options = [s['name'] for s in overview['sections'] if s['name'] != section['name']]
                            if effluent_options:
                                # Initialize effluent_to if not exists
                                if 'effluent_to' not in section:
                                    section['effluent_to'] = []
                                
                                # Get current selections
                                current_effluent = section.get('effluent_to', [])
                                if not isinstance(current_effluent, list):
                                    current_effluent = [current_effluent] if current_effluent else []
                                
                                # Multi-select for effluent destinations
                                selected_effluent = st.multiselect(
                                    'Effluent Goes To:',
                                    effluent_options,
                                    default=[opt for opt in current_effluent if opt in effluent_options],
                                    key=f'effluent_to_{idx}',
                                    help='Select one or more sections where effluent flows to'
                                )
                                section['effluent_to'] = selected_effluent if selected_effluent else []
                                
                                # Update flow_connections based on effluent_to
                                # Remove old connections from this section
                                overview['flow_connections'] = [
                                    conn for conn in overview['flow_connections'] 
                                    if conn['from'] != section['name']
                                ]
                                # Add new connections
                                for effluent_dest in selected_effluent:
                                    overview['flow_connections'].append({
                                        'from': section['name'],
                                        'to': effluent_dest
                                    })
                            else:
                                section['effluent_to'] = []
                                st.caption("(No other sections available)")
                        
                        st.divider()
                        
                        # Return flow
                        has_return = st.checkbox(
                            'Has Return Flow',
                            value=section.get('has_return_flow', False),
                            key=f'return_{idx}'
                        )
                        section['has_return_flow'] = has_return
                        
                        if has_return:
                            return_options = [s['name'] for s in overview['sections'] if s['name'] != section['name']]
                            if return_options:
                                return_to = st.selectbox(
                                    'Return Flow To:',
                                    [''] + return_options,
                                    index=0 if not section.get('return_to') else return_options.index(section['return_to']) + 1 if section['return_to'] in return_options else 0,
                                    key=f'return_to_{idx}'
                                )
                                section['return_to'] = return_to if return_to else None
                        
                        # Sludge generation
                        # Check if this section is set as final sludge discharge
                        is_final_sludge_discharge = overview.get('sludge_discharge', {}).get('section') == section['name']
                        
                        if is_final_sludge_discharge:
                            # This is the final sludge discharge - show info and disable sludge generation
                            st.info("📍 **Final Sludge Discharge** - This is the final sludge discharge point")
                            section['generates_sludge'] = False
                            section['sludge_to'] = None
                            # Clear any existing sludge connections to this section
                            for other_section in overview['sections']:
                                if other_section.get('sludge_to') == section['name']:
                                    other_section['sludge_to'] = None
                        else:
                            generates_sludge = st.checkbox(
                                'Generates Sludge',
                                value=section.get('generates_sludge', False),
                                key=f'sludge_gen_{idx}'
                            )
                            section['generates_sludge'] = generates_sludge
                            
                            if generates_sludge:
                                # Exclude final sludge discharge section from sludge options
                                final_sludge_section = overview.get('sludge_discharge', {}).get('section')
                                sludge_options = [s['name'] for s in overview['sections'] 
                                                if s['name'] != section['name'] and s['name'] != final_sludge_section]
                                if sludge_options:
                                    sludge_to = st.selectbox(
                                        'Sludge To:',
                                        [''] + sludge_options,
                                        index=0 if not section.get('sludge_to') else sludge_options.index(section['sludge_to']) + 1 if section['sludge_to'] in sludge_options else 0,
                                        key=f'sludge_to_{idx}'
                                    )
                                    section['sludge_to'] = sludge_to if sludge_to else None
                                else:
                                    section['sludge_to'] = None
                                    st.caption("(No downstream sludge sections available)")
                            else:
                                section['sludge_to'] = None
                    
                    with col_sec3:
                        if st.button('🗑️', key=f'delete_{idx}', help='Delete'):
                            # Remove section and update connections
                            section_name = section['name']
                            overview['sections'].pop(idx)
                            
                            # Remove connections involving this section
                            overview['flow_connections'] = [
                                conn for conn in overview['flow_connections']
                                if conn['from'] != section_name and conn['to'] != section_name
                            ]
                            
                            # Clean up effluent_to references in other sections
                            for other_section in overview['sections']:
                                if 'effluent_to' in other_section:
                                    if isinstance(other_section['effluent_to'], list):
                                        other_section['effluent_to'] = [e for e in other_section['effluent_to'] if e != section_name]
                                    elif other_section['effluent_to'] == section_name:
                                        other_section['effluent_to'] = []
                                
                                # Clean up return_to references
                                if other_section.get('return_to') == section_name:
                                    other_section['return_to'] = None
                                    other_section['has_return_flow'] = False
                                
                                # Clean up sludge_to references
                                if other_section.get('sludge_to') == section_name:
                                    other_section['sludge_to'] = None
                                    other_section['generates_sludge'] = False
                            
                            log_activity('section_deleted', section_name)
                            st.rerun()
        
        st.divider()
        
        # Section 2: Visual Process Flow Diagram
        st.subheader('2️⃣ Process Flow Diagram')
        
        if overview['sections']:
            # Create a simple text-based flow diagram
            st.markdown("**Process Flow:**")
            
            # Build flow diagram
            diagram_lines = []
            processed = set()
            
            def build_diagram(section_name, indent=0):
                if section_name in processed:
                    return
                processed.add(section_name)
                
                section = next((s for s in overview['sections'] if s['name'] == section_name), None)
                if section:
                    prefix = "  " * indent + "└─ " if indent > 0 else ""
                    # Get icon based on flow_type
                    flow_type = section.get('flow_type', 'sewage')
                    if flow_type == 'sludge':
                        icon = '🔴'
                    elif flow_type == 'other' or flow_type == 'service_water':  # Support old value
                        icon = '🟢'
                    else:  # sewage (default)
                        icon = '🔵'
                    return_flow = f" ↻ (returns to {section['return_to']})" if section.get('has_return_flow') and section.get('return_to') else ""
                    sludge_flow = f" 🟤 (sludge to {section['sludge_to']})" if section.get('generates_sludge') and section.get('sludge_to') else ""
                    effluent_to_list = section.get('effluent_to', [])
                    effluent_flow = f" → ({', '.join(effluent_to_list)})" if effluent_to_list else ""
                    diagram_lines.append(f"{prefix}{icon} **{section['name']}**{effluent_flow}{return_flow}{sludge_flow}")
                    
                    # Add downstream sections (from effluent_to or flow_connections)
                    downstream = section.get('effluent_to', [])
                    if not downstream:
                        # Fallback to flow_connections if effluent_to not set
                        downstream = [conn['to'] for conn in overview['flow_connections'] if conn['from'] == section_name]
                    for ds in downstream:
                        build_diagram(ds, indent + 1)
            
            # Start from sections with no upstream connections (entry points)
            all_downstream = set(conn['to'] for conn in overview['flow_connections'])
            entry_points = [s['name'] for s in overview['sections'] if s['name'] not in all_downstream]
            
            if entry_points:
                for entry in entry_points:
                    build_diagram(entry)
            else:
                # If no clear entry point, show all sections
                for section in overview['sections']:
                    if section['name'] not in processed:
                        # Get icon based on flow_type
                        flow_type = section.get('flow_type', 'sewage')
                        if flow_type == 'sludge':
                            icon = '🔴'
                        elif flow_type == 'other' or flow_type == 'service_water':  # Support old value
                            icon = '🟢'
                        else:  # sewage (default)
                            icon = '🔵'
                        diagram_lines.append(f"{icon} **{section['name']}**")
            
            # Display diagram
            st.code("\n".join(diagram_lines) if diagram_lines else "No flow connections defined", language=None)
            
            # Summary table
            st.markdown("**Section Summary:**")
            summary_data = []
            for section in overview['sections']:
                # Get effluent destinations
                effluent_to_list = section.get('effluent_to', [])
                if not effluent_to_list:
                    # Fallback to flow_connections
                    effluent_to_list = [conn['to'] for conn in overview['flow_connections'] if conn['from'] == section['name']]
                effluent_info = ", ".join(effluent_to_list) if effluent_to_list else "None"
                
                downstream_list = ", ".join(section['downstream']) if section.get('downstream') else "None"
                return_info = section.get('return_to', 'None') if section.get('has_return_flow') else 'No'
                sludge_info = section.get('sludge_to', 'None') if section.get('generates_sludge') else 'No'
                flow_type = section.get('flow_type', 'sewage')
                if flow_type == 'service_water':  # Migrate old value
                    flow_type = 'other'
                flow_type_display = 'Other' if flow_type == 'other' else flow_type.replace('_', ' ').title()
                summary_data.append({
                    'Section': section['name'],
                    'Flow Type': flow_type_display,
                    'Effluent To': effluent_info,
                    'Return Flow': return_info,
                    'Sludge To': sludge_info
                })
            
            if summary_data:
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
        else:
            st.info("👆 Add sections above to build your process flow diagram")
    
    else:
        st.info("👆 Start by adding your first WWTP section above")
    
    # Section 3: Discharge Configuration
    st.divider()
    st.subheader('3️⃣ Discharge Configuration')
    st.caption("Configure final discharge points and validate against Design Requirements")
    
    if overview['sections']:
        # Get design requirements for validation
        design_reqs = st.session_state.get('design_requirements', [])
        req_dict = {req.get('name', ''): req for req in design_reqs}
        
        col_disch1, col_disch2 = st.columns(2)
        
        # Sewage Discharge Configuration
        with col_disch1:
            st.markdown("**🔵 Final Sewage Discharge**")
            sewage_sections = [s['name'] for s in overview['sections'] if s.get('flow_type') == 'sewage']
            if sewage_sections:
                current_sewage_discharge = overview['sewage_discharge'].get('section')
                sewage_discharge_idx = 0
                if current_sewage_discharge and current_sewage_discharge in sewage_sections:
                    sewage_discharge_idx = sewage_sections.index(current_sewage_discharge) + 1
                
                selected_sewage = st.selectbox(
                    'Select Final Sewage Discharge Section:',
                    ['None'] + sewage_sections,
                    index=sewage_discharge_idx,
                    key='sewage_discharge_section'
                )
                
                # Clear effluent_to connections if this section is newly selected as final discharge
                previous_sewage_discharge = overview['sewage_discharge'].get('section')
                if selected_sewage != 'None' and selected_sewage != previous_sewage_discharge:
                    # Clear effluent_to for the newly selected section
                    for section in overview['sections']:
                        if section['name'] == selected_sewage:
                            section['effluent_to'] = []
                            # Remove flow connections from this section
                            overview['flow_connections'] = [
                                conn for conn in overview['flow_connections'] 
                                if conn['from'] != selected_sewage
                            ]
                            break
                
                overview['sewage_discharge']['section'] = selected_sewage if selected_sewage != 'None' else None
                
                if selected_sewage != 'None':
                    st.markdown("**Discharge Values:**")
                    sewage_values = overview['sewage_discharge'].get('values', {})
                    
                    # Get concentration parameters from defaults
                    conc_params = get_flow_loading_conc_params()
                    
                    for default_key, mb_key in conc_params:
                        # Check if there's a design requirement for this parameter
                        req_key = f"{mb_key}_out"  # e.g., BOD_out, TSS_out
                        req_key_alt = f"{mb_key}_discharge"  # Alternative naming
                        
                        # Find matching requirement
                        matching_req = None
                        for req_name, req in req_dict.items():
                            if mb_key.lower() in req_name.lower() and ('out' in req_name.lower() or 'discharge' in req_name.lower() or 'effluent' in req_name.lower()):
                                matching_req = req
                                break
                        
                        current_val = sewage_values.get(mb_key, 0.0)
                        unit = st.session_state.get('project_default_units', {}).get(default_key, 'mg/L')
                        
                        if matching_req:
                            req_value = matching_req.get('value', 0.0)
                            req_unit = matching_req.get('unit', 'mg/L')
                            # Show requirement as hint
                            st.caption(f"Requirement: {matching_req.get('name', '')} ≤ {req_value:.2f} {req_unit}")
                            
                            new_val = st.number_input(
                                f'{mb_key} ({unit}):',
                                value=float(current_val),
                                min_value=0.0,
                                format="%.2f",
                                step=0.1,
                                key=f'sewage_discharge_{mb_key}',
                                help=f"Must meet requirement: {matching_req.get('name', '')} ≤ {req_value:.2f} {req_unit}"
                            )
                            sewage_values[mb_key] = new_val
                            
                            # Validation
                            # Simple unit conversion check (assuming same unit type)
                            if req_unit.lower() == unit.lower() or req_unit.replace('³', '3').lower() == unit.replace('³', '3').lower():
                                if new_val > req_value:
                                    st.error(f"❌ {mb_key} = {new_val:.2f} {unit} exceeds requirement of {req_value:.2f} {req_unit}")
                                else:
                                    st.success(f"✅ {mb_key} = {new_val:.2f} {unit} meets requirement")
                            else:
                                st.warning(f"⚠️ Unit mismatch: requirement is {req_unit}, input is {unit}")
                        else:
                            new_val = st.number_input(
                                f'{mb_key} ({unit}):',
                                value=float(current_val),
                                min_value=0.0,
                                format="%.2f",
                                step=0.1,
                                key=f'sewage_discharge_{mb_key}'
                            )
                            sewage_values[mb_key] = new_val
                    
                    overview['sewage_discharge']['values'] = sewage_values
            else:
                st.info("No sewage sections available")
        
        # Sludge Discharge Configuration
        with col_disch2:
            st.markdown("**🔴 Final Sludge Discharge**")
            sludge_sections = [s['name'] for s in overview['sections'] if s.get('flow_type') == 'sludge']
            # Also include sections that generate sludge
            sludge_generating = [s['name'] for s in overview['sections'] if s.get('generates_sludge', False)]
            all_sludge_sections = list(set(sludge_sections + sludge_generating))
            
            if all_sludge_sections:
                current_sludge_discharge = overview['sludge_discharge'].get('section')
                sludge_discharge_idx = 0
                if current_sludge_discharge and current_sludge_discharge in all_sludge_sections:
                    sludge_discharge_idx = all_sludge_sections.index(current_sludge_discharge) + 1
                
                selected_sludge = st.selectbox(
                    'Select Final Sludge Discharge Section:',
                    ['None'] + all_sludge_sections,
                    index=sludge_discharge_idx,
                    key='sludge_discharge_section'
                )
                
                # Clear sludge_to connections if this section is newly selected as final discharge
                previous_sludge_discharge = overview['sludge_discharge'].get('section')
                if selected_sludge != 'None' and selected_sludge != previous_sludge_discharge:
                    # Clear sludge_to for sections that were sending sludge to the newly selected section
                    for section in overview['sections']:
                        if section.get('sludge_to') == selected_sludge:
                            section['sludge_to'] = None
                            section['generates_sludge'] = False
                
                overview['sludge_discharge']['section'] = selected_sludge if selected_sludge != 'None' else None
                
                if selected_sludge != 'None':
                    st.markdown("**Discharge Values:**")
                    sludge_values = overview['sludge_discharge'].get('values', {})
                    
                    # Sludge flow
                    current_flow = sludge_values.get('flow', 0.0)
                    flow_req = None
                    for req_name, req in req_dict.items():
                        if 'sludge' in req_name.lower() and ('flow' in req_name.lower() or 'discharge' in req_name.lower()):
                            flow_req = req
                            break
                    
                    if flow_req:
                        req_value = flow_req.get('value', 0.0)
                        req_unit = flow_req.get('unit', 'm³/day')
                        st.caption(f"Requirement: {flow_req.get('name', '')} ≤ {req_value:.2f} {req_unit}")
                        
                        new_flow = st.number_input(
                            'Sludge Flow (m³/day):',
                            value=float(current_flow),
                            min_value=0.0,
                            format="%.2f",
                            step=10.0,
                            key='sludge_discharge_flow',
                            help=f"Must meet requirement: {flow_req.get('name', '')} ≤ {req_value:.2f} {req_unit}"
                        )
                        sludge_values['flow'] = new_flow
                        
                        # Validation
                        if req_unit.lower() in ['m³/day', 'm3/day', 'm^3/day']:
                            if new_flow > req_value:
                                st.error(f"❌ Flow = {new_flow:.2f} m³/day exceeds requirement of {req_value:.2f} {req_unit}")
                            else:
                                st.success(f"✅ Flow = {new_flow:.2f} m³/day meets requirement")
                        else:
                            st.warning(f"⚠️ Unit mismatch: requirement is {req_unit}, input is m³/day")
                    else:
                        new_flow = st.number_input(
                            'Sludge Flow (m³/day):',
                            value=float(current_flow),
                            min_value=0.0,
                            format="%.2f",
                            step=10.0,
                            key='sludge_discharge_flow'
                        )
                        sludge_values['flow'] = new_flow
                    
                    # Sludge solids percentage
                    current_solids = sludge_values.get('solids', 0.0)
                    solids_req = None
                    for req_name, req in req_dict.items():
                        if 'sludge' in req_name.lower() and ('solids' in req_name.lower() or 'concentration' in req_name.lower()):
                            solids_req = req
                            break
                    
                    if solids_req:
                        req_value = solids_req.get('value', 0.0)
                        req_unit = solids_req.get('unit', '%')
                        st.caption(f"Requirement: {solids_req.get('name', '')} ≥ {req_value:.2f} {req_unit}")
                        
                        new_solids = st.number_input(
                            'Solids (%):',
                            value=float(current_solids),
                            min_value=0.0,
                            max_value=100.0,
                            format="%.2f",
                            step=0.1,
                            key='sludge_discharge_solids',
                            help=f"Must meet requirement: {solids_req.get('name', '')} ≥ {req_value:.2f} {req_unit}"
                        )
                        sludge_values['solids'] = new_solids
                        
                        # Validation (for solids, typically we want >= requirement)
                        if req_unit.lower() in ['%', 'percent', 'pct']:
                            if new_solids < req_value:
                                st.error(f"❌ Solids = {new_solids:.2f}% below requirement of {req_value:.2f}%")
                            else:
                                st.success(f"✅ Solids = {new_solids:.2f}% meets requirement")
                        else:
                            st.warning(f"⚠️ Unit mismatch: requirement is {req_unit}, input is %")
                    else:
                        new_solids = st.number_input(
                            'Solids (%):',
                            value=float(current_solids),
                            min_value=0.0,
                            max_value=100.0,
                            format="%.2f",
                            step=0.1,
                            key='sludge_discharge_solids'
                        )
                        sludge_values['solids'] = new_solids
                    
                    overview['sludge_discharge']['values'] = sludge_values
            else:
                st.info("No sludge sections available")
        
        # Summary of discharge validation
        if overview['sewage_discharge'].get('section') or overview['sludge_discharge'].get('section'):
            st.divider()
            st.markdown("**📊 Discharge Summary:**")
            summary_discharge = []
            
            if overview['sewage_discharge'].get('section'):
                sewage_section = overview['sewage_discharge']['section']
                sewage_vals = overview['sewage_discharge'].get('values', {})
                row = {'Type': 'Sewage Discharge', 'Section': sewage_section}
                for key, val in sewage_vals.items():
                    row[key] = f"{val:.2f}"
                summary_discharge.append(row)
            
            if overview['sludge_discharge'].get('section'):
                sludge_section = overview['sludge_discharge']['section']
                sludge_vals = overview['sludge_discharge'].get('values', {})
                row = {'Type': 'Sludge Discharge', 'Section': sludge_section}
                for key, val in sludge_vals.items():
                    row[key] = f"{val:.2f}"
                summary_discharge.append(row)
            
            if summary_discharge:
                st.dataframe(pd.DataFrame(summary_discharge), use_container_width=True, hide_index=True)
    else:
        st.info("👆 Add sections above to configure discharge points")
    
    # Store updated overview
    st.session_state.wwtp_overview = overview

# ==================== MASS BALANCE TAB ====================
with tab1:
    st.header('🔄 Mass Balance - Sewage, Centrate & Sludge')
    st.caption("Mass balance calculations based on sections defined in Overview tab")
    
    # Check if overview sections exist
    overview = st.session_state.get('wwtp_overview', {'sections': [], 'flow_connections': []})
    
    if not overview['sections']:
        st.warning("⚠️ **No sections defined yet!** Please go to the **Overview** tab first to define your WWTP sections.")
        st.info("💡 Once you've defined sections in Overview, this tab will show mass balance inputs for each section.")
    else:
        st.success(f"✅ Found {len(overview['sections'])} sections from Overview")
        
        # Initialize mass balance storage
        if 'mass_balance' not in st.session_state:
            st.session_state.mass_balance = {}
        
        st.subheader('Mass Balance by Section')
        
        # For each section, provide mass balance inputs
        for idx, section in enumerate(overview['sections']):
            section_name = section['name']
            
            with st.expander(f"📊 {section_name} - Mass Balance", expanded=False):
                # Cross-reference to Reference tab - Collapsible and hidden by default
                with st.expander("🔗 Cross-Reference to Design Notes", expanded=False):
                    all_references = []
                    for section_key in ['section_1', 'section_2', 'section_3']:
                        for ref in st.session_state.get('references', {}).get(section_key, []):
                            all_references.append(ref)
                    
                    if all_references:
                        # Get current cross-references for this section
                        mb_cross_refs_key = f'mb_cross_refs_{section_name}'
                        if mb_cross_refs_key not in st.session_state:
                            st.session_state[mb_cross_refs_key] = []
                        
                        # Create reference options
                        ref_options = {f"Ref {ref['id']} ({ref.get('type', 'text').upper()})": ref['id'] for ref in all_references}
                        selected_ref_labels = st.multiselect(
                            "Select References:",
                            options=list(ref_options.keys()),
                            default=[label for label in ref_options.keys() 
                                    if ref_options[label] in st.session_state[mb_cross_refs_key]],
                            key=f'cross_ref_select_{section_name}',
                            help="Select references from the Reference tab that explain this section's calculations"
                        )
                        
                        # Update cross-references
                        selected_ref_ids = [ref_options[label] for label in selected_ref_labels]
                        st.session_state[mb_cross_refs_key] = selected_ref_ids
                        
                        # Update references with cross-ref info
                        for ref in all_references:
                            if 'cross_refs' not in ref:
                                ref['cross_refs'] = []
                            ref_section = f"{section_name} - Mass Balance"
                            if ref['id'] in selected_ref_ids:
                                if ref_section not in ref['cross_refs']:
                                    ref['cross_refs'].append(ref_section)
                            else:
                                if ref_section in ref['cross_refs']:
                                    ref['cross_refs'].remove(ref_section)
                        
                        if selected_ref_labels:
                            st.success(f"✅ Linked to: {', '.join(selected_ref_labels)}")
                            st.caption("💡 View these references in the **Reference** tab")
                    else:
                        st.info("👆 No references available yet. Add references in the **Reference** tab first.")
                
                st.divider()
                
                # Determine intake loading source based on Process Flow Diagram
                defaults = st.session_state.get('project_defaults', get_defaults())
                
                # Find all intake sources based on Process Flow Diagram:
                # 1. Upstream sections via flow_connections
                # 2. Return flows (sections that return to this section)
                # 3. Sludge flows (sections that send sludge to this section)
                # 4. Initial loading (for entry point sections)
                
                # Find upstream sections via flow_connections
                upstream_sections = [conn['from'] for conn in overview['flow_connections'] if conn['to'] == section_name]
                
                # Find sections that return flow to this section (RAS, internal recirculation)
                return_flow_sections = [s['name'] for s in overview['sections'] 
                                       if s.get('has_return_flow') and s.get('return_to') == section_name]
                
                # Find sections that send sludge to this section
                sludge_source_sections = [s['name'] for s in overview['sections'] 
                                         if s.get('generates_sludge') and s.get('sludge_to') == section_name]
                
                # Determine if this is an entry point (no upstream connections)
                all_downstream = set(conn['to'] for conn in overview['flow_connections'])
                is_entry_point = section_name not in all_downstream
                
                # Calculate combined intake from all sources (supports all Flow & Loading conc params)
                conc_params = get_flow_loading_conc_params()
                custom_flow = st.session_state.get('project_defaults_custom', {}).get('flow', [])
                intake_sources = []
                total_intake_flow = 0.0
                total_intake_loads = {mb_key: 0.0 for _, mb_key in conc_params}
                
                def _source_dict(flow, vals_by_mb_key, src_type):
                    d = {'source': '', 'flow': flow, 'type': src_type}
                    for k, v in vals_by_mb_key.items():
                        d[k] = v
                    return d
                
                # 1. Initial loading (for entry point sections)
                if is_entry_point:
                    initial_flow = float(defaults.get('Q_avg', 60000))
                    vals = {mb_key: _get_conc_val_from_defaults(dk, defaults, custom_flow) for dk, mb_key in conc_params}
                    total_intake_flow += initial_flow
                    for mb_key in vals:
                        total_intake_loads[mb_key] += initial_flow * vals[mb_key] / 1000
                    src = _source_dict(initial_flow, vals, 'sewage')
                    src['source'] = 'Initial Loading'
                    intake_sources.append(src)
                
                # 2. Upstream sections via flow_connections
                for upstream_name in upstream_sections:
                    if upstream_name in st.session_state.mass_balance:
                        upstream_mb = st.session_state.mass_balance[upstream_name]
                        if 'outlet' in upstream_mb:
                            upstream_flow = float(upstream_mb['outlet'].get('flow', 0.0))
                            vals = {mb_key: _get_conc_from_mb(upstream_mb['outlet'], mb_key) for _, mb_key in conc_params}
                            total_intake_flow += upstream_flow
                            for mb_key in vals:
                                total_intake_loads[mb_key] += upstream_flow * vals[mb_key] / 1000
                            upstream_section = next((s for s in overview['sections'] if s['name'] == upstream_name), None)
                            flow_type = upstream_section.get('flow_type', 'sewage') if upstream_section else 'sewage'
                            src = _source_dict(upstream_flow, vals, flow_type)
                            src['source'] = f"{upstream_name} (Effluent)"
                            intake_sources.append(src)
                    else:
                        vals = {mb_key: 0.0 for _, mb_key in conc_params}
                        upstream_section = next((s for s in overview['sections'] if s['name'] == upstream_name), None)
                        flow_type = upstream_section.get('flow_type', 'sewage') if upstream_section else 'sewage'
                        src = _source_dict(0.0, vals, flow_type)
                        src['source'] = f"{upstream_name} (Effluent - Not configured yet)"
                        intake_sources.append(src)
                
                # 3. Return flows
                for return_section_name in return_flow_sections:
                    if return_section_name in st.session_state.mass_balance:
                        return_mb = st.session_state.mass_balance[return_section_name]
                        if 'return_flow' in return_mb and return_mb['return_flow'].get('flow', 0) > 0:
                            return_flow = float(return_mb['return_flow'].get('flow', 0.0))
                            vals = {mb_key: _get_conc_from_mb(return_mb['return_flow'], mb_key) for _, mb_key in conc_params}
                            total_intake_flow += return_flow
                            for mb_key in vals:
                                total_intake_loads[mb_key] += return_flow * vals[mb_key] / 1000
                            src = _source_dict(return_flow, vals, 'return')
                            src['source'] = f"{return_section_name} (Return Flow)"
                            intake_sources.append(src)
                
                # 4. Sludge flows (BOD/TSS estimated from solids; others use COD≈2*BOD if COD exists, else 0)
                for sludge_source_name in sludge_source_sections:
                    if sludge_source_name in st.session_state.mass_balance:
                        sludge_source_mb = st.session_state.mass_balance[sludge_source_name]
                        if 'sludge_discharge' in sludge_source_mb:
                            sludge_flow = float(sludge_source_mb['sludge_discharge'].get('flow', 0.0))
                            sludge_solids = float(sludge_source_mb['sludge_discharge'].get('solids', 0.0))
                            if sludge_flow > 0:
                                sludge_tss = sludge_solids * 10000
                                sludge_bod = sludge_tss * 0.5
                                vals = {}
                                for _, mb_key in conc_params:
                                    if mb_key == 'BOD':
                                        vals[mb_key] = sludge_bod
                                    elif mb_key == 'TSS':
                                        vals[mb_key] = sludge_tss
                                    elif mb_key == 'COD':
                                        vals[mb_key] = sludge_bod * 2.0  # typical COD/BOD ~2 for sludge
                                    else:
                                        vals[mb_key] = 0.0
                                total_intake_flow += sludge_flow
                                for mb_key in vals:
                                    total_intake_loads[mb_key] += sludge_flow * vals[mb_key] / 1000
                                src = _source_dict(sludge_flow, vals, 'sludge')
                                src['source'] = f"{sludge_source_name} (Sludge)"
                                intake_sources.append(src)
                
                # Weighted average concentrations
                avg_intake = {}
                if total_intake_flow > 0:
                    for mb_key in total_intake_loads:
                        avg_intake[mb_key] = (total_intake_loads[mb_key] * 1000) / total_intake_flow
                else:
                    avg_intake = {mb_key: 0.0 for mb_key in total_intake_loads}
                
                # Special case: single upstream effluent source → direct assignment
                upstream_effluent_only = [s for s in intake_sources if "(Effluent)" in s['source'] and "Not configured" not in s['source']]
                if len(upstream_effluent_only) == 1 and len(intake_sources) == 1:
                    upstream_source = upstream_effluent_only[0]
                    total_intake_flow = upstream_source['flow']
                    avg_intake = {mb_key: upstream_source.get(mb_key, 0.0) for _, mb_key in conc_params}
                
                # Build intake/outlet/return_flow defaults with all conc params
                base_intake = {'flow': total_intake_flow, **{mb_key: avg_intake.get(mb_key, 0) for _, mb_key in conc_params}}
                base_outlet_rf = {'flow': 0.0, **{mb_key: 0.0 for _, mb_key in conc_params}}
                
                # Initialize section mass balance if not exists
                if section_name not in st.session_state.mass_balance:
                    st.session_state.mass_balance[section_name] = {
                        'intake': dict(base_intake),
                        'outlet': dict(base_outlet_rf),
                        'sludge_discharge': {'flow': 0.0, 'solids': 0.0},
                        'return_flow': dict(base_outlet_rf),
                        'python_code': '',
                        'python_output': '',
                        'python_updated_outlet': False
                    }
                
                mb_data = st.session_state.mass_balance[section_name]
                
                # Ensure structure exists and merge any new conc params
                if 'intake' not in mb_data:
                    mb_data['intake'] = dict(base_intake)
                else:
                    for mb_key in base_intake:
                        if mb_key not in mb_data['intake']:
                            mb_data['intake'][mb_key] = base_intake[mb_key]
                if 'outlet' not in mb_data:
                    mb_data['outlet'] = dict(base_outlet_rf)
                else:
                    for mb_key in base_outlet_rf:
                        if mb_key not in mb_data['outlet']:
                            mb_data['outlet'][mb_key] = 0.0
                if 'sludge_discharge' not in mb_data:
                    mb_data['sludge_discharge'] = {'flow': 0.0, 'solids': 0.0}
                if 'return_flow' not in mb_data:
                    mb_data['return_flow'] = dict(base_outlet_rf)
                else:
                    for mb_key in base_outlet_rf:
                        if mb_key not in mb_data['return_flow']:
                            mb_data['return_flow'][mb_key] = 0.0
                if 'python_updated_outlet' not in mb_data:
                    mb_data['python_updated_outlet'] = False
                
                # Update intake from all sources
                mb_data['intake']['flow'] = total_intake_flow
                for _, mb_key in conc_params:
                    mb_data['intake'][mb_key] = avg_intake.get(mb_key, 0.0)
                
                col_mb1, col_mb2 = st.columns(2)
                
                # Intake Loading - Show all sources based on Process Flow Diagram
                with col_mb1:
                    st.markdown("**📥 Intake Loading**")
                    
                    # Display intake sources
                    if intake_sources:
                        st.caption("**Intake Sources (from Process Flow Diagram):**")
                        source_info = []
                        for src in intake_sources:
                            icon = "🔄" if src['type'] == 'return' else "🟤" if src['type'] == 'sludge' else "🔵"
                            if src['flow'] > 0 or "Not configured" not in src['source']:
                                conc_str = ", ".join(f"{mb_key}: {src.get(mb_key, 0):.1f} mg/L" for _, mb_key in conc_params)
                                source_info.append(f"{icon} **{src['source']}**: {src['flow']:.2f} m³/day, {conc_str}")
                            else:
                                source_info.append(f"{icon} **{src['source']}**: Waiting for upstream section configuration")
                        
                        if source_info:
                            st.info("\n".join(source_info))
                        
                        # Special case: If only one upstream section feeds here, make it clear
                        upstream_effluent_sources = [s for s in intake_sources if "(Effluent)" in s['source'] and "Not configured" not in s['source']]
                        if len(upstream_effluent_sources) == 1 and len(intake_sources) == 1:
                            upstream_src = upstream_effluent_sources[0]
                            upstream_name = upstream_src['source'].replace(" (Effluent)", "")
                            st.success(f"✅ **Intake = Outlet from {upstream_name}**")
                            conc_str = " | ".join(f"{mb_key}: {upstream_src.get(mb_key, 0):.1f} mg/L" for _, mb_key in conc_params)
                            st.caption(f"Flow: {upstream_src['flow']:.2f} m³/day | {conc_str}")
                    else:
                        st.warning("⚠️ No intake sources defined. Check Process Flow Diagram connections.")
                    
                    # Show combined intake (editable for entry points, read-only for others)
                    if is_entry_point:
                        st.caption("**Combined Intake (Editable - Entry Point)**")
                        mb_data['intake']['flow'] = st.number_input(
                            'Total Flow (m³/day)',
                            value=float(mb_data['intake'].get('flow', total_intake_flow)),
                            format="%.2f",
                            step=100.0,
                            key=f'mb_intake_flow_{section_name}'
                        )
                        for _, mb_key in conc_params:
                            mb_data['intake'][mb_key] = st.number_input(
                                f'{mb_key} (mg/L)',
                                value=float(mb_data['intake'].get(mb_key, avg_intake.get(mb_key, 0))),
                                step=10.0,
                                key=f'mb_intake_{mb_key}_{section_name}'
                            )
                    else:
                        st.caption("**Combined Intake (Auto-calculated from sources)**")
                        conc_lines = "  \n".join(f"**{mb_key}:** {mb_data['intake'].get(mb_key, 0):.1f} mg/L" for _, mb_key in conc_params)
                        load_parts = [f"{mb_key}: {(mb_data['intake']['flow'] * mb_data['intake'].get(mb_key, 0) / 1000):.2f} kg/d" for _, mb_key in conc_params]
                        load_str = ", ".join(load_parts)
                        upstream_txt = f"\n\n*Intake from: {', '.join(upstream_sections)}*" if upstream_sections else ""
                        st.info(f"""
                        **Total Flow:** {mb_data['intake']['flow']:.2f} m³/day  
                        {conc_lines}
                        {upstream_txt}
                        """)
                        st.caption(f"**Intake Loads:** {load_str}")
                        
                        # Note about updating when upstream changes
                        if upstream_sections:
                            st.caption("💡 *Intake automatically updates when upstream sections' outlets change*")
                
                # Outlet Loading - Account for return flows and sludge generation
                with col_mb2:
                    st.markdown("**📤 Outlet Loading**")
                    
                    # Find downstream sections (where this section's effluent goes)
                    downstream_sections = []
                    # Check effluent_to first (from Process Flow Diagram)
                    effluent_to_list = section.get('effluent_to', [])
                    if effluent_to_list:
                        downstream_sections = effluent_to_list
                    else:
                        # Fallback to flow_connections
                        downstream_sections = [conn['to'] for conn in overview['flow_connections'] if conn['from'] == section_name]
                    
                    if downstream_sections:
                        st.caption(f"**Feeds to:** {', '.join(downstream_sections)}")
                        st.info(f"💡 *Outlet values feed to intake of: {', '.join(downstream_sections)}*")
                    else:
                        st.caption("**Final Effluent** (No downstream sections)")
                    
                    # Check if this section has return flow
                    has_return = section.get('has_return_flow', False)
                    return_to = section.get('return_to', None)
                    if has_return and return_to:
                        st.caption(f"↻ **Return Flow to:** {return_to}")
                        # Initialize return flow if not exists
                        if 'return_flow' not in mb_data:
                            mb_data['return_flow'] = {'flow': 0.0, 'BOD': 0.0, 'TSS': 0.0}
                    
                    # Check if this section generates sludge
                    generates_sludge = section.get('generates_sludge', False)
                    sludge_to = section.get('sludge_to', None)
                    if generates_sludge and sludge_to:
                        st.caption(f"🟤 **Sludge to:** {sludge_to}")
                    
                    # Get current outlet values from session state (Python updates are stored here)
                    current_outlet = st.session_state.mass_balance[section_name].get('outlet', {})
                    current_outlet = {'flow': 0.0, **{mb_key: 0.0 for _, mb_key in conc_params}, **current_outlet}
                    # Capture python_updated before outlet block resets it (used by sludge block too)
                    section_python_updated = mb_data.get('python_updated_outlet', False)
                    
                    # Initialize outlet keys in session state
                    outlet_flow_key = f'mb_outlet_flow_{section_name}'
                    outlet_keys = {mb_key: f'mb_outlet_{mb_key}_{section_name}' for _, mb_key in conc_params}
                    
                    # Check if Python updated outlet (this flag is set before rerun)
                    python_updated = mb_data.get('python_updated_outlet', False)
                    if python_updated:
                        st.info("💡 Outlet values updated by Python code")
                        st.session_state[outlet_flow_key] = float(current_outlet.get('flow', 0.0))
                        for mb_key, ok in outlet_keys.items():
                            st.session_state[ok] = float(current_outlet.get(mb_key, 0.0))
                        mb_data['python_updated_outlet'] = False
                    else:
                        if outlet_flow_key not in st.session_state:
                            st.session_state[outlet_flow_key] = float(current_outlet.get('flow', 0.0))
                        for mb_key, ok in outlet_keys.items():
                            if ok not in st.session_state:
                                st.session_state[ok] = float(current_outlet.get(mb_key, 0.0))
                    
                    mb_data['outlet']['flow'] = st.number_input(
                        'Flow (m³/day)',
                        value=st.session_state[outlet_flow_key],
                        format="%.2f",
                        step=100.0,
                        key=outlet_flow_key
                    )
                    n_conc = len(conc_params)
                    out_cols = st.columns(max(2, n_conc))
                    for i, (_, mb_key) in enumerate(conc_params):
                        with out_cols[i % len(out_cols)]:
                            mb_data['outlet'][mb_key] = st.number_input(
                                f'{mb_key} (mg/L)',
                                value=st.session_state[outlet_keys[mb_key]],
                                step=10.0,
                                key=outlet_keys[mb_key]
                            )
                    
                    st.session_state.mass_balance[section_name]['outlet'] = dict(mb_data['outlet'])
                
                # Return Flow - editable like outlet loading (Python can set, user can override)
                if has_return and return_to:
                    st.markdown("**↻ Return Flow**")
                    st.caption(f"Return flow from **{section_name}** to **{return_to}**")
                    current_return = st.session_state.mass_balance[section_name].get('return_flow', {})
                    current_return = {'flow': 0.0, **{mb_key: 0.0 for _, mb_key in conc_params}, **current_return}
                    rf_flow_key = f'mb_return_flow_{section_name}'
                    rf_keys = {mb_key: f'mb_return_{mb_key}_{section_name}' for _, mb_key in conc_params}
                    if section_python_updated:
                        st.info("💡 Return flow values updated by Python code")
                        st.session_state[rf_flow_key] = float(mb_data['return_flow'].get('flow', 0.0))
                        for mb_key, rk in rf_keys.items():
                            st.session_state[rk] = float(mb_data['return_flow'].get(mb_key, 0.0))
                    else:
                        if rf_flow_key not in st.session_state:
                            st.session_state[rf_flow_key] = float(current_return.get('flow', 0.0))
                        for mb_key, rk in rf_keys.items():
                            if rk not in st.session_state:
                                st.session_state[rk] = float(current_return.get(mb_key, 0.0))
                    rf_n = len(conc_params)
                    rf_cols = st.columns(1 + max(1, rf_n))
                    with rf_cols[0]:
                        mb_data['return_flow']['flow'] = st.number_input(
                            'Flow (m³/day)',
                            value=st.session_state[rf_flow_key],
                            format="%.2f",
                            step=100.0,
                            key=rf_flow_key
                        )
                    for i, (_, mb_key) in enumerate(conc_params):
                        with rf_cols[min(1 + i, len(rf_cols) - 1)]:
                            mb_data['return_flow'][mb_key] = st.number_input(
                                f'{mb_key} (mg/L)',
                                value=st.session_state[rf_keys[mb_key]],
                                step=10.0,
                                key=rf_keys[mb_key]
                            )
                    st.session_state.mass_balance[section_name]['return_flow'] = dict(mb_data['return_flow'])
                
                # Sludge discharge inputs (editable like intake and outlet)
                if generates_sludge:
                    st.markdown("**🟤 Sludge Discharge Parameters:**")
                    st.caption(f"Sludge from **{section_name}** to **{sludge_to}**")
                else:
                    st.markdown("**🟤 Sludge Discharge Parameters:**")
                    st.caption("(If this section generates sludge)")
                # Session state keys for sludge (sync with Python updates like outlet)
                sludge_flow_key = f'mb_sludge_flow_{section_name}'
                sludge_solids_key = f'mb_sludge_solids_{section_name}'
                current_sludge = st.session_state.mass_balance[section_name].get('sludge_discharge', {'flow': 0.0, 'solids': 0.0})
                if section_python_updated:
                    # Python ran - use updated sludge values
                    st.session_state[sludge_flow_key] = float(current_sludge.get('flow', 0.0))
                    st.session_state[sludge_solids_key] = float(current_sludge.get('solids', 0.0))
                else:
                    if sludge_flow_key not in st.session_state:
                        st.session_state[sludge_flow_key] = float(current_sludge.get('flow', 0.0))
                    if sludge_solids_key not in st.session_state:
                        st.session_state[sludge_solids_key] = float(current_sludge.get('solids', 0.0))
                sludge_col1, sludge_col2 = st.columns(2)
                with sludge_col1:
                    mb_data['sludge_discharge']['flow'] = st.number_input(
                        'Sludge Flow (m³/day)',
                        value=st.session_state[sludge_flow_key],
                        format="%.2f",
                        step=10.0,
                        key=sludge_flow_key
                    )
                with sludge_col2:
                    mb_data['sludge_discharge']['solids'] = st.number_input(
                        'Solids (%)',
                        value=st.session_state[sludge_solids_key],
                        format="%.2f",
                        step=0.1,
                        key=sludge_solids_key
                    )
                # Sync sludge back to session state
                st.session_state.mass_balance[section_name]['sludge_discharge'] = {
                    'flow': mb_data['sludge_discharge']['flow'],
                    'solids': mb_data['sludge_discharge']['solids']
                }
                
                # Calculate and display totals with mass balance (compact styling)
                st.markdown("**📈 Calculated Totals & Mass Balance:**")
                st.markdown(
                    "<style>.calc-metric { font-size: 1.5em !important; } "
                    ".calc-metric .stMetricValue { font-size: 1.2em !important; } "
                    ".calc-metric .stMetricLabel { font-size:  1.2em !important; }</style>",
                    unsafe_allow_html=True
                )
                calc_col1, calc_col2, calc_col3 = st.columns(3)
                
                with calc_col1:
                    # Intake totals (smaller display) — all Flow & Loading conc params
                    intake_flow = mb_data['intake'].get('flow', 0.0)
                    intake_conc_keys = {k for k in mb_data['intake'].keys() if k != 'flow'}
                    intake_load_parts = [f"{k}: {(intake_flow * float(mb_data['intake'].get(k, 0)) / 1000):.2f} kg/d" for k in sorted(intake_conc_keys)]
                    intake_load_str = " · ".join(intake_load_parts) if intake_load_parts else "—"
                    st.markdown(
                        f'<div class="calc-metric">'
                        f'<div style="font-size:0.8em;color:#6b7280;">Total Intake Flow</div>'
                        f'<div style="font-size:0.95em;"><strong>{intake_flow:.2f}</strong> <span style="font-size:0.75em;">m³/day</span></div>'
                       
                        f'</div>',
                        unsafe_allow_html=True
                    )
                
                with calc_col2:
                    # Outlet totals (smaller display) — all Flow & Loading conc params
                    effluent_flow = mb_data['outlet'].get('flow', 0.0)
                    outlet_conc_keys = {k for k in mb_data['outlet'].keys() if k != 'flow'}
                    outlet_load_parts = [f"{k}: {(effluent_flow * float(mb_data['outlet'].get(k, 0)) / 1000):.2f} kg/d" for k in sorted(outlet_conc_keys)]
                    outlet_load_str = " · ".join(outlet_load_parts) if outlet_load_parts else "—"
                    return_flow_val = mb_data.get('return_flow', {}).get('flow', 0.0) if has_return and return_to else 0.0
                    ret_caption = f' · ↻ Return: {return_flow_val:.2f} m³/day' if has_return and return_to else ''
                    st.markdown(
                        f'<div class="calc-metric">'
                        f'<div style="font-size:0.8em;color:#6b7280;">Total Outlet Flow</div>'
                        f'<div style="font-size:0.95em;"><strong>{effluent_flow:.2f}</strong> <span style="font-size:0.75em;">m³/day</span></div>'
                        
                        f'</div>',
                        unsafe_allow_html=True
                    )
                
                with calc_col3:
                    # Sludge Discharge: Flow (m³/day) main, solids % sub — no kg/d
                    sludge_flow = mb_data['sludge_discharge'].get('flow', 0.0)
                    sludge_solids = mb_data['sludge_discharge'].get('solids', 0.0)
                    st.markdown(
                        f'<div class="calc-metric">'
                        f'<div style="font-size:0.8em;color:#6b7280;">Sludge Discharge</div>'
                        f'<div style="font-size:0.95em;"><strong>{sludge_flow:.2f}</strong> <span style="font-size:0.75em;">m³/day</span></div>'
                        f'<div style="font-size:0.7em;color:#9ca3af;">Solids: {sludge_solids:.2f}%</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                
                # Mass Balance Check - all parameters (Flow + all concentration params from intake/outlet)
                st.markdown("**⚖️ Mass Balance Check:**")
                tolerance = 0.01
                rf = mb_data.get('return_flow', {})
                rf_flow = rf.get('flow', 0.0) if has_return and return_to else 0.0
                
                # Flow balance
                total_outflow = effluent_flow + rf_flow + sludge_flow
                flow_balance = intake_flow - total_outflow
                if abs(flow_balance) < tolerance:
                    st.success(f"✅ Flow Balance: {flow_balance:.2f} m³/day")
                else:
                    st.warning(f"⚠️ Flow Balance: {flow_balance:.2f} m³/day")
                st.caption(f"Intake: {intake_flow:.2f} = Outlet: {effluent_flow:.2f} + Return: {rf_flow:.2f} + Sludge: {sludge_flow:.2f}")
                
                # All concentration parameters (exclude 'flow')
                intake_keys = {k for k in mb_data['intake'].keys() if k != 'flow'}
                outlet_keys = {k for k in mb_data['outlet'].keys() if k != 'flow'}
                conc_params = sorted(intake_keys | outlet_keys)
                
                for param in conc_params:
                    intake_conc = float(mb_data['intake'].get(param, 0.0))
                    outlet_conc = float(mb_data['outlet'].get(param, 0.0))
                    rf_conc = float(rf.get(param, 0.0)) if has_return and return_to else 0.0
                    
                    intake_load = intake_flow * intake_conc / 1000
                    outlet_load = effluent_flow * outlet_conc / 1000
                    rf_load = rf_flow * rf_conc / 1000
                    
                    # Sludge contribution: BOD estimated from solids; TSS from solids%; others = 0
                    if param.upper() == 'BOD':
                        sludge_load = sludge_flow * (sludge_solids / 100) * 1000 * 0.5
                    elif param.upper() == 'TSS':
                        sludge_load = sludge_flow * (sludge_solids / 100) * 1000
                    else:
                        sludge_load = 0.0
                    
                    total_out_load = outlet_load + rf_load + sludge_load
                    param_balance = intake_load - total_out_load
                    if abs(param_balance) < tolerance:
                        st.success(f"✅ {param} Balance: {param_balance:.2f} kg/d")
                    else:
                        st.warning(f"⚠️ {param} Balance: {param_balance:.2f} kg/d")
                    st.caption(f"Intake: {intake_load:.2f} kg/d vs Out: {total_out_load:.2f} kg/d")
                
                st.divider()
                
                # Python Code Input and Execution
                st.markdown("**Python Calculations**")
                st.info("📘 **Libraries & variables:** See **Python Coding Guide** tab for reference and section-specific examples.")
                
                # Initialize code if not exists
                if 'python_code' not in mb_data:
                    mb_data['python_code'] = ''
                if 'python_output' not in mb_data:
                    mb_data['python_output'] = ''
                
                # Code input area
                python_code = st.text_area(
                    'Python Code:',
                    value=mb_data.get('python_code', ''),
                    height=200,
                    key=f'python_code_{section_name}',
                    help='Enter Python code using numpy, scipy.optimize.fsolve, and pandas. Example:\n\n# Example: Solve for MLSS\nfrom scipy.optimize import fsolve\nimport numpy as np\n\ndef residuals(x):\n    MLSS, RAS = x\n    # Your equations here\n    return [MLSS * SRT - 1, RAS - 0.5]\n\nresult = fsolve(residuals, [1000, 0.5])\nprint(f"MLSS: {result[0]}, RAS: {result[1]}")'
                )
                mb_data['python_code'] = python_code
                
                col_exec1, col_exec2 = st.columns([1, 4])
                with col_exec1:
                    if st.button('▶️ Run Code', key=f'run_code_{section_name}', type='primary'):
                        try:
                            # Prepare execution context with available libraries and data
                            defaults = st.session_state.get('project_defaults', get_defaults())
                            custom = st.session_state.get('project_defaults_custom', {'flow': [], 'kinetic': [], 'system': []})
                            design_params = {
                                'kinetic': {
                                    'Y': defaults.get('Y', 0.67),
                                    'kd': defaults.get('kd', 0.06),
                                    'SRT': defaults.get('SRT', 10),
                                },
                                'system': {
                                    'MLSS': defaults.get('MLSS', 3000),
                                }
                            }
                            for p in custom.get('kinetic', []):
                                if p.get('name'):
                                    design_params['kinetic'][p['name']] = float(p.get('value', 0))
                            for p in custom.get('system', []):
                                if p.get('name'):
                                    design_params['system'][p['name']] = float(p.get('value', 0))
                            exec_globals = {
                                'np': np,
                                'pd': pd,
                                'fsolve': fsolve,
                                'mb_data': mb_data,
                                'section_name': section_name,
                                'defaults': defaults,
                                'design_params': design_params,
                                'overview': st.session_state.get('wwtp_overview', {'sections': [], 'flow_connections': []}),
                                '__builtins__': __builtins__
                            }
                            
                            # Capture output
                            import io
                            import sys
                            old_stdout = sys.stdout
                            sys.stdout = captured_output = io.StringIO()
                            
                            try:
                                # Store original outlet values for comparison
                                original_outlet = {
                                    'flow': mb_data['outlet'].get('flow', 0.0),
                                    'BOD': mb_data['outlet'].get('BOD', 0.0),
                                    'TSS': mb_data['outlet'].get('TSS', 0.0)
                                }
                                exec(python_code, exec_globals)
                                output = captured_output.getvalue()
                                
                                # Get updated outlet values
                                updated_outlet = {
                                    'flow': mb_data['outlet'].get('flow', 0.0),
                                    'BOD': mb_data['outlet'].get('BOD', 0.0),
                                    'TSS': mb_data['outlet'].get('TSS', 0.0)
                                }
                                
                                # Check if values changed
                                values_changed = (
                                    abs(updated_outlet['flow'] - original_outlet['flow']) > 0.01 or
                                    abs(updated_outlet['BOD'] - original_outlet['BOD']) > 0.01 or
                                    abs(updated_outlet['TSS'] - original_outlet['TSS']) > 0.01
                                )
                                
                                if values_changed:
                                    output += f"\n\n✅ Outlet values updated:\n"
                                    output += f"  Flow: {original_outlet['flow']:.2f} → {updated_outlet['flow']:.2f} m³/day\n"
                                    output += f"  BOD: {original_outlet['BOD']:.1f} → {updated_outlet['BOD']:.1f} mg/L\n"
                                    output += f"  TSS: {original_outlet['TSS']:.1f} → {updated_outlet['TSS']:.1f} mg/L"
                                
                                # Include return flow in output when section has return flow (from Python code or RAS ratio)
                                if has_return and return_to and 'return_flow' in mb_data:
                                    updated_return_flow = mb_data['return_flow'].get('flow', 0.0)
                                    updated_return_bod = mb_data['return_flow'].get('BOD', 0.0)
                                    updated_return_tss = mb_data['return_flow'].get('TSS', 0.0)
                                    if updated_return_flow > 0:
                                        output += f"\n\n↻ Return Flow (to {return_to}):\n"
                                        output += f"  Flow: {updated_return_flow:.2f} m³/day\n"
                                        output += f"  BOD: {updated_return_bod:.2f} mg/L\n"
                                        output += f"  TSS: {updated_return_tss:.2f} mg/L"
                                
                                # Include sludge in output when Python sets it (Python-only, no manual input)
                                if 'sludge_discharge' in mb_data:
                                    sf = mb_data['sludge_discharge'].get('flow', 0.0)
                                    ss = mb_data['sludge_discharge'].get('solids', 0.0)
                                    if sf > 0:
                                        dest = f" to {sludge_to}" if sludge_to else ""
                                        output += f"\n\n🟤 Sludge Discharge{dest}:\n"
                                        output += f"  Flow: {sf:.2f} m³/day\n"
                                        output += f"  Solids: {ss:.2f}%"
                                
                                mb_data['python_output'] = output if output else "Code executed successfully (no output)"
                                
                                # Ensure outlet values are properly stored in session state
                                # Direct assignment to ensure values persist
                                updated_outlet_dict = {
                                    'flow': float(updated_outlet['flow']),
                                    'BOD': float(updated_outlet['BOD']),
                                    'TSS': float(updated_outlet['TSS'])
                                }
                                st.session_state.mass_balance[section_name]['outlet'] = updated_outlet_dict
                                
                                # Also update sludge_discharge if it was modified
                                if 'sludge_discharge' in mb_data:
                                    st.session_state.mass_balance[section_name]['sludge_discharge'] = {
                                        'flow': float(mb_data['sludge_discharge'].get('flow', 0.0)),
                                        'solids': float(mb_data['sludge_discharge'].get('solids', 0.0))
                                    }
                                
                                # Persist return_flow to session state (Python can set it directly, not just via RAS ratio)
                                if has_return and return_to and 'return_flow' in mb_data:
                                    return_flow_data = mb_data['return_flow']
                                    st.session_state.mass_balance[section_name]['return_flow'] = {
                                        'flow': float(return_flow_data.get('flow', 0.0)),
                                        'BOD': float(return_flow_data.get('BOD', 0.0)),
                                        'TSS': float(return_flow_data.get('TSS', 0.0)),
                                        'ratio': float(return_flow_data.get('ratio', 0.5))
                                    }
                                
                                # Set flag to show outlet was updated (widgets will read this on next run)
                                st.session_state.mass_balance[section_name]['python_updated_outlet'] = True
                                
                                # Force update mb_data reference to match session state
                                mb_data['outlet'] = updated_outlet_dict.copy()
                                
                                # Note: Widget keys will be initialized on next run (after rerun) 
                                # with the updated values from mass_balance['outlet']
                                
                            finally:
                                sys.stdout = old_stdout
                            
                            st.success("✅ Code executed successfully!")
                            # Rerun to update UI and next section's intake from this section's outlet
                            st.rerun()
                        except Exception as e:
                            mb_data['python_output'] = f"❌ Error: {str(e)}"
                            st.error(f"Error executing code: {str(e)}")
                
                # Display output
                if mb_data.get('python_output'):
                    st.markdown("**📊 Output:**")
                    st.code(mb_data['python_output'], language='text')
        
        st.divider()
        
        # Plant-Wide Iterative Calculation - Run All Section Codes Sequentially
        st.subheader('🏭 Plant-Wide Iterative Calculation')
        st.caption("Execute all section Python codes sequentially. Each section's outlet feeds to the next section's intake.")
        
        # Initialize plant-wide output storage
        if 'plant_wide_output' not in st.session_state:
            st.session_state.plant_wide_output = ''
        
        col_iter1, col_iter2 = st.columns([1, 3])
        with col_iter1:
            num_iterations = st.number_input(
                'Iterations:',
                min_value=1,
                value=1,
                step=1,
                key='plant_iterations',
                help='Number of times to run all section codes sequentially (for convergence)'
            )
        
        with col_iter2:
            if st.button('▶️ Run All Section Codes Sequentially', key='run_all_sections', type='primary'):
                try:
                    defaults = st.session_state.get('project_defaults', get_defaults())
                    all_outputs = []
                    updated_sections = []
                    
                    # Run iterations
                    for iteration in range(num_iterations):
                        if num_iterations > 1:
                            all_outputs.append(f"\n{'='*60}")
                            all_outputs.append(f"ITERATION {iteration + 1}")
                            all_outputs.append(f"{'='*60}\n")
                        
                        # Execute each section's code in sequence
                        for idx, section in enumerate(overview['sections']):
                            section_name = section['name']
                            
                            # Skip if section has no Python code
                            if section_name not in st.session_state.mass_balance:
                                continue
                            
                            mb_data = st.session_state.mass_balance[section_name]
                            python_code = mb_data.get('python_code', '')
                            
                            if not python_code or not python_code.strip():
                                continue
                            
                            # Update intake from all sources (matching Process Flow Diagram logic)
                            defaults_iter = st.session_state.get('project_defaults', get_defaults())
                            custom_flow_iter = st.session_state.get('project_defaults_custom', {}).get('flow', [])
                            conc_params_iter = get_flow_loading_conc_params()
                            
                            upstream_sections_iter = [conn['from'] for conn in overview['flow_connections'] if conn['to'] == section_name]
                            return_flow_sections_iter = [s['name'] for s in overview['sections'] 
                                                          if s.get('has_return_flow') and s.get('return_to') == section_name]
                            sludge_source_sections_iter = [s['name'] for s in overview['sections'] 
                                                          if s.get('generates_sludge') and s.get('sludge_to') == section_name]
                            all_downstream_iter = set(conn['to'] for conn in overview['flow_connections'])
                            is_entry_point_iter = section_name not in all_downstream_iter
                            
                            total_intake_flow_iter = 0.0
                            total_intake_loads_iter = {mb_key: 0.0 for _, mb_key in conc_params_iter}
                            
                            if is_entry_point_iter:
                                initial_flow_iter = float(defaults_iter.get('Q_avg', 60000))
                                vals_iter = {mb_key: _get_conc_val_from_defaults(dk, defaults_iter, custom_flow_iter) for dk, mb_key in conc_params_iter}
                                total_intake_flow_iter += initial_flow_iter
                                for mb_key in vals_iter:
                                    total_intake_loads_iter[mb_key] += initial_flow_iter * vals_iter[mb_key] / 1000
                            
                            for upstream_name_iter in upstream_sections_iter:
                                if upstream_name_iter in st.session_state.mass_balance:
                                    upstream_mb_iter = st.session_state.mass_balance[upstream_name_iter]
                                    if 'outlet' in upstream_mb_iter:
                                        upstream_flow_iter = float(upstream_mb_iter['outlet'].get('flow', 0.0))
                                        vals_iter = {mb_key: _get_conc_from_mb(upstream_mb_iter['outlet'], mb_key) for _, mb_key in conc_params_iter}
                                        total_intake_flow_iter += upstream_flow_iter
                                        for mb_key in vals_iter:
                                            total_intake_loads_iter[mb_key] += upstream_flow_iter * vals_iter[mb_key] / 1000
                            
                            for return_section_name_iter in return_flow_sections_iter:
                                if return_section_name_iter in st.session_state.mass_balance:
                                    return_mb_iter = st.session_state.mass_balance[return_section_name_iter]
                                    if 'return_flow' in return_mb_iter and return_mb_iter['return_flow'].get('flow', 0) > 0:
                                        return_flow_iter = float(return_mb_iter['return_flow'].get('flow', 0.0))
                                        vals_iter = {mb_key: _get_conc_from_mb(return_mb_iter['return_flow'], mb_key) for _, mb_key in conc_params_iter}
                                        total_intake_flow_iter += return_flow_iter
                                        for mb_key in vals_iter:
                                            total_intake_loads_iter[mb_key] += return_flow_iter * vals_iter[mb_key] / 1000
                            
                            for sludge_source_name_iter in sludge_source_sections_iter:
                                if sludge_source_name_iter in st.session_state.mass_balance:
                                    sludge_source_mb_iter = st.session_state.mass_balance[sludge_source_name_iter]
                                    if 'sludge_discharge' in sludge_source_mb_iter:
                                        sludge_flow_iter = float(sludge_source_mb_iter['sludge_discharge'].get('flow', 0.0))
                                        sludge_solids_iter = float(sludge_source_mb_iter['sludge_discharge'].get('solids', 0.0))
                                        if sludge_flow_iter > 0:
                                            sludge_tss_iter = sludge_solids_iter * 10000
                                            sludge_bod_iter = sludge_tss_iter * 0.5
                                            vals_iter = {}
                                            for _, mb_key in conc_params_iter:
                                                if mb_key == 'BOD': vals_iter[mb_key] = sludge_bod_iter
                                                elif mb_key == 'TSS': vals_iter[mb_key] = sludge_tss_iter
                                                elif mb_key == 'COD': vals_iter[mb_key] = sludge_bod_iter * 2.0
                                                else: vals_iter[mb_key] = 0.0
                                            total_intake_flow_iter += sludge_flow_iter
                                            for mb_key in vals_iter:
                                                total_intake_loads_iter[mb_key] += sludge_flow_iter * vals_iter[mb_key] / 1000
                            
                            avg_intake_iter = {}
                            if total_intake_flow_iter > 0:
                                for mb_key in total_intake_loads_iter:
                                    avg_intake_iter[mb_key] = (total_intake_loads_iter[mb_key] * 1000) / total_intake_flow_iter
                            else:
                                avg_intake_iter = {mb_key: 0.0 for mb_key in total_intake_loads_iter}
                            
                            mb_data['intake']['flow'] = total_intake_flow_iter
                            for _, mb_key in conc_params_iter:
                                mb_data['intake'][mb_key] = avg_intake_iter.get(mb_key, 0.0)
                            
                            # Prepare execution context for this section
                            custom_iter = st.session_state.get('project_defaults_custom', {'flow': [], 'kinetic': [], 'system': []})
                            design_params_iter = {
                                'kinetic': {
                                    'Y': defaults.get('Y', 0.67),
                                    'kd': defaults.get('kd', 0.06),
                                    'SRT': defaults.get('SRT', 10),
                                },
                                'system': {
                                    'MLSS': defaults.get('MLSS', 3000),
                                }
                            }
                            for p in custom_iter.get('kinetic', []):
                                if p.get('name'):
                                    design_params_iter['kinetic'][p['name']] = float(p.get('value', 0))
                            for p in custom_iter.get('system', []):
                                if p.get('name'):
                                    design_params_iter['system'][p['name']] = float(p.get('value', 0))
                            exec_globals = {
                                'np': np,
                                'pd': pd,
                                'fsolve': fsolve,
                                'mb_data': mb_data,
                                'section_name': section_name,
                                'defaults': defaults,
                                'design_params': design_params_iter,
                                'overview': overview,
                                '__builtins__': __builtins__
                            }
                            
                            # Capture output
                            import io
                            import sys
                            old_stdout = sys.stdout
                            sys.stdout = captured_output = io.StringIO()
                            
                            try:
                                original_outlet = dict(mb_data['outlet'])
                                
                                exec(python_code, exec_globals)
                                output = captured_output.getvalue()
                                
                                updated_outlet = dict(mb_data['outlet'])
                                
                                values_changed = False
                                for k in set(original_outlet) | set(updated_outlet):
                                    if k in ('flow',) or k in [mbk for _, mbk in conc_params_iter]:
                                        ov = float(original_outlet.get(k, 0))
                                        uv = float(updated_outlet.get(k, 0))
                                        if abs(uv - ov) > 0.01:
                                            values_changed = True
                                            break
                                
                                updated_outlet_dict = {k: float(v) for k, v in updated_outlet.items()}
                                st.session_state.mass_balance[section_name]['outlet'] = updated_outlet_dict
                                st.session_state.mass_balance[section_name]['python_updated_outlet'] = True
                                
                                # Update sludge_discharge if modified
                                if 'sludge_discharge' in mb_data:
                                    st.session_state.mass_balance[section_name]['sludge_discharge'] = {
                                        'flow': float(mb_data['sludge_discharge'].get('flow', 0.0)),
                                        'solids': float(mb_data['sludge_discharge'].get('solids', 0.0))
                                    }
                                
                                has_return_iter = section.get('has_return_flow', False)
                                return_to_iter = section.get('return_to', None)
                                if has_return_iter and return_to_iter and 'return_flow' in mb_data:
                                    return_flow_data = mb_data['return_flow']
                                    persisted_rf = {k: float(v) for k, v in return_flow_data.items()}
                                    if 'ratio' not in persisted_rf:
                                        persisted_rf['ratio'] = 0.5
                                    st.session_state.mass_balance[section_name]['return_flow'] = persisted_rf
                                
                                has_return_output = has_return_iter and return_to_iter and 'return_flow' in mb_data and mb_data['return_flow'].get('flow', 0) > 0
                                has_sludge_output = 'sludge_discharge' in mb_data and mb_data['sludge_discharge'].get('flow', 0) > 0
                                if output or values_changed or has_return_output or has_sludge_output:
                                    all_outputs.append(f"\n--- {section_name} ---")
                                    if output:
                                        all_outputs.append(output)
                                    if values_changed:
                                        all_outputs.append(f"✅ Outlet updated:")
                                        all_outputs.append(f"  Flow: {original_outlet.get('flow', 0):.2f} → {updated_outlet.get('flow', 0):.2f} m³/day")
                                        for _, mb_key in conc_params_iter:
                                            o = original_outlet.get(mb_key, 0)
                                            u = updated_outlet.get(mb_key, 0)
                                            all_outputs.append(f"  {mb_key}: {o:.1f} → {u:.1f} mg/L")
                                    if has_return_output:
                                        rf = mb_data['return_flow']
                                        conc_rf = ", ".join(f"{mbk}: {rf.get(mbk, 0):.2f} mg/L" for _, mbk in conc_params_iter)
                                        all_outputs.append(f"↻ Return Flow (to {return_to_iter}): {rf.get('flow', 0):.2f} m³/day, {conc_rf}")
                                    # Sludge from Python
                                    if 'sludge_discharge' in mb_data and mb_data['sludge_discharge'].get('flow', 0) > 0:
                                        sd = mb_data['sludge_discharge']
                                        sludge_to_iter = section.get('sludge_to', '')
                                        dest_str = f" to {sludge_to_iter}" if sludge_to_iter else ""
                                        all_outputs.append(f"🟤 Sludge Discharge{dest_str}: {sd.get('flow', 0):.2f} m³/day, Solids: {sd.get('solids', 0):.2f}%")
                                
                                updated_sections.append(section_name)
                                
                            except Exception as e:
                                all_outputs.append(f"\n--- {section_name} ---")
                                all_outputs.append(f"❌ Error: {str(e)}")
                            finally:
                                sys.stdout = old_stdout
                    
                    # Combine all outputs
                    combined_output = "\n".join(all_outputs) if all_outputs else "All section codes executed successfully (no output)"
                    st.session_state.plant_wide_output = combined_output
                    
                    if updated_sections:
                        st.success(f"✅ Sequentially executed codes for {len(set(updated_sections))} section(s)!")
                    else:
                        st.info("ℹ️ No section codes found or executed.")
                    
                    st.rerun()
                except Exception as e:
                    st.session_state.plant_wide_output = f"❌ Error: {str(e)}"
                    st.error(f"Error executing sequential codes: {str(e)}")
        
        # Display combined output
        if st.session_state.plant_wide_output:
            st.markdown("**📊 Sequential Execution Output:**")
            st.code(st.session_state.plant_wide_output, language='text')
        
        st.divider()
        
        # Summary Table
        st.subheader('📋 Mass Balance Summary')
        summary_rows = []
        for section in overview['sections']:
            section_name = section['name']
            if section_name in st.session_state.mass_balance:
                mb = st.session_state.mass_balance[section_name]
                # Handle backward compatibility
                if 'intake' in mb:
                    intake_flow = mb['intake'].get('flow', 0.0)
                    intake_bod = mb['intake'].get('BOD', 0.0)
                    intake_tss = mb['intake'].get('TSS', 0.0)
                else:
                    intake_flow = mb.get('sewage', {}).get('flow', 0.0)
                    intake_bod = mb.get('sewage', {}).get('BOD', 0.0)
                    intake_tss = mb.get('sewage', {}).get('TSS', 0.0)
                
                if 'outlet' in mb:
                    outlet_flow = mb['outlet'].get('flow', 0.0)
                    outlet_bod = mb['outlet'].get('BOD', 0.0)
                    outlet_tss = mb['outlet'].get('TSS', 0.0)
                else:
                    outlet_flow = 0.0
                    outlet_bod = 0.0
                    outlet_tss = 0.0
                
                if 'sludge_discharge' in mb:
                    sludge_flow = mb['sludge_discharge'].get('flow', 0.0)
                    sludge_solids = mb['sludge_discharge'].get('solids', 0.0)
                else:
                    sludge_flow = mb.get('sludge', {}).get('flow', 0.0)
                    sludge_solids = mb.get('sludge', {}).get('solids', 0.0)
                
                # Get return flow if exists
                return_flow = 0.0
                return_bod = 0.0
                return_to_info = 'None'
                if 'return_flow' in mb:
                    return_flow = mb['return_flow'].get('flow', 0.0)
                    return_bod = mb['return_flow'].get('BOD', 0.0)
                    # Find which section this returns to
                    section_obj = next((s for s in overview['sections'] if s['name'] == section_name), None)
                    if section_obj and section_obj.get('has_return_flow'):
                        return_to_info = section_obj.get('return_to', 'None')
                
                # Calculate loads (all flows are in m³/day)
                intake_bod_load = intake_flow * intake_bod / 1000  # m³/day * mg/L / 1000 = kg/d
                outlet_bod_load = outlet_flow * outlet_bod / 1000  # m³/day * mg/L / 1000 = kg/d
                return_bod_load = return_flow * return_bod / 1000 if return_flow > 0 else 0.0
                sludge_discharge_load = sludge_flow * (sludge_solids / 100) * 1000  # m³/day * % * density = kg/d
                
                summary_rows.append({
                    'Section': section_name,
                    'Intake Flow (m³/day)': f"{intake_flow:.2f}",
                    'Intake BOD (mg/L)': f"{intake_bod:.1f}",
                    'Intake BOD Load (kg/d)': f"{intake_bod_load:.2f}",
                    'Outlet Flow (m³/day)': f"{outlet_flow:.2f}",
                    'Outlet BOD (mg/L)': f"{outlet_bod:.1f}",
                    'Effluent Load (kg/d)': f"{outlet_bod_load:.2f}",
                    'Return Flow (m³/day)': f"{return_flow:.2f}",
                    'Return To': return_to_info,
                    'Sludge Flow (m³/day)': f"{sludge_flow:.2f}",
                    'Sludge Solids (%)': f"{sludge_solids:.2f}",
                    'Sludge Discharge (kg/d)': f"{sludge_discharge_load:.2f}"
                })
        
        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
        
        # Store updated mass balance
        st.session_state.mass_balance = st.session_state.mass_balance

# ==================== REFERENCE TAB ====================
with tab2:
    st.header('📚 Reference - Design Notes & Calculations')
    st.caption("Document your design calculations, references, and notes. Auto-numbered references can be cross-referenced from Mass Balance tab.")
    
    # Add enhanced drag-and-drop and paste functionality CSS/JS
    st.markdown("""
    <style>
    .upload-area {
        border: 2px dashed #ccc;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
        background-color: #f9f9f9;
        transition: all 0.3s ease;
        cursor: pointer;
        margin: 10px 0;
    }
    .upload-area:hover {
        border-color: #1f77b4;
        background-color: #f0f7ff;
    }
    .upload-area.drag-over {
        border-color: #1f77b4;
        background-color: #e6f2ff;
        transform: scale(1.02);
    }
    .upload-area.has-file {
        border-color: #28a745;
        background-color: #d4edda;
    }
    .paste-indicator {
        display: none;
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 20px 40px;
        border-radius: 8px;
        z-index: 10000;
        font-size: 18px;
    }
    .paste-indicator.show {
        display: block;
    }
    </style>
    <script>
    // Initialize paste handlers for image uploads
    function initPasteHandler(uploadKey) {
        const uploadArea = document.querySelector(`[data-testid="stFileUploader"][data-upload-key="${uploadKey}"]`);
        if (!uploadArea) return;
        
        // Make the upload area focusable for paste events
        uploadArea.setAttribute('tabindex', '0');
        uploadArea.style.outline = 'none';
        
        // Handle paste event
        uploadArea.addEventListener('paste', function(e) {
            e.preventDefault();
            const items = e.clipboardData.items;
            
            for (let i = 0; i < items.length; i++) {
                if (items[i].type.indexOf('image') !== -1) {
                    const blob = items[i].getAsFile();
                    const reader = new FileReader();
                    
                    reader.onload = function(event) {
                        const base64 = event.target.result;
                        // Store in session state via Streamlit
                        const indicator = document.getElementById('paste-indicator');
                        if (indicator) {
                            indicator.classList.add('show');
                            setTimeout(() => indicator.classList.remove('show'), 2000);
                        }
                        // Trigger file input with the pasted image
                        const input = uploadArea.querySelector('input[type="file"]');
                        if (input) {
                            const dataTransfer = new DataTransfer();
                            dataTransfer.items.add(blob);
                            input.files = dataTransfer.files;
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    };
                    
                    reader.readAsDataURL(blob);
                    break;
                }
            }
        });
        
        // Handle drag and drop visual feedback
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.closest('.upload-wrapper')?.classList.add('drag-over');
        });
        
        uploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            uploadArea.closest('.upload-wrapper')?.classList.remove('drag-over');
        });
        
        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.closest('.upload-wrapper')?.classList.remove('drag-over');
        });
    }
    
    // Initialize on page load
    window.addEventListener('load', function() {
        setTimeout(function() {
            initPasteHandler('img_upload_1');
            initPasteHandler('img_upload_2');
            initPasteHandler('img_upload_3');
        }, 500);
    });
    </script>
    <div id="paste-indicator" class="paste-indicator">📋 Image pasted! Processing...</div>
    """, unsafe_allow_html=True)
    
    # Initialize reference storage
    if 'references' not in st.session_state:
        st.session_state.references = {
            'section_1': [],  # WWTP Sections
            'section_2': [],  # Process Flow Diagram
            'section_3': []   # Discharge Configuration
        }
        st.session_state.reference_counter = 1
    
    # Initialize pasted image storage
    if 'pasted_images' not in st.session_state:
        st.session_state.pasted_images = {}
    
    references = st.session_state.references
    
    # Get overview sections for context
    overview = st.session_state.get('wwtp_overview', {'sections': [], 'flow_connections': []})
    
    # Helper function to render reference
    def render_reference(ref, ref_num, section_key):
        """Render a single reference item"""
        with st.container():
            col_ref_header, col_ref_delete = st.columns([5, 1])
            with col_ref_header:
                st.markdown(f"### Reference {ref_num}")
            with col_ref_delete:
                if st.button('🗑️', key=f'delete_ref_{ref_num}_{section_key}', help='Delete this reference'):
                    # Delete file from disk if exists
                    if 'file_path' in ref and ref['file_path']:
                        delete_reference_file(ref['file_path'])
                    # Remove from references
                    references[section_key] = [r for r in references[section_key] if r['id'] != ref_num]
                    # Clear cross-references from mass balance sections
                    for mb_key in list(st.session_state.keys()):
                        if mb_key.startswith('mb_cross_refs_'):
                            ref_list = st.session_state[mb_key]
                            if ref_num in ref_list:
                                ref_list.remove(ref_num)
                    st.rerun()
            
            # Reference type indicator
            ref_type = ref.get('type', 'text')
            type_icons = {
                'pdf': '📄',
                'image': '🖼️',
                'text': '📝',
                'latex': '🔢'
            }
            st.markdown(f"**Type:** {type_icons.get(ref_type, '📝')} {ref_type.upper()}")
            
            # Display content based on type
            if ref_type == 'pdf':
                file_path = ref.get('file_path')
                filename = ref.get('filename', 'reference.pdf')
                if file_path:
                    pdf_data = load_reference_file(file_path)
                    if pdf_data:
                        st.download_button(
                            label=f"📥 Download PDF: {filename}",
                            data=pdf_data,
                            file_name=filename,
                            mime='application/pdf',
                            key=f'download_pdf_{ref_num}'
                        )
                elif 'file_data' in ref:
                    # Fallback for old format (backward compatibility)
                    pdf_data = ref['file_data']
                    if isinstance(pdf_data, str):
                        pdf_data = base64.b64decode(pdf_data)
                    st.download_button(
                        label=f"📥 Download PDF: {filename}",
                        data=pdf_data,
                        file_name=filename,
                        mime='application/pdf',
                        key=f'download_pdf_{ref_num}'
                    )
                if 'description' in ref and ref['description']:
                    st.markdown(f"**Description:** {ref['description']}")
            
            elif ref_type == 'image':
                file_path = ref.get('file_path')
                if file_path:
                    img_data = load_reference_file(file_path)
                    if img_data:
                        st.image(BytesIO(img_data), use_container_width=True)
                elif 'file_data' in ref:
                    # Fallback for old format (backward compatibility)
                    img_data = ref['file_data']
                    if isinstance(img_data, str):
                        img_data = base64.b64decode(img_data)
                    st.image(BytesIO(img_data) if isinstance(img_data, bytes) else img_data, 
                            use_container_width=True)
                if 'description' in ref and ref['description']:
                    st.markdown(f"**Description:** {ref['description']}")
            
            elif ref_type == 'text':
                if 'content' in ref:
                    st.markdown(ref['content'])
            
            elif ref_type == 'latex':
                if 'equation' in ref:
                    st.latex(ref['equation'])
                if 'description' in ref and ref['description']:
                    st.markdown(f"**Description:** {ref['description']}")
            
            # Remarks
            if 'remarks' in ref and ref['remarks']:
                st.markdown(f"**Remarks:** {ref['remarks']}")
            
            # Cross-reference info
            if 'cross_refs' in ref and ref['cross_refs']:
                st.caption(f"🔗 Referenced from: {', '.join(ref['cross_refs'])}")
            
            st.divider()
    
    # Section 1: WWTP Sections References
    st.subheader('1️⃣ WWTP Sections - References')
    
    col_ref1_1, col_ref1_2 = st.columns([3, 1])
    with col_ref1_1:
        st.markdown("**Add Reference for WWTP Sections:**")
    with col_ref1_2:
        if st.button('➕ Add Reference', key='add_ref_section_1'):
            st.session_state.ref_adding_section = 1
            st.rerun()
    
    if st.session_state.get('ref_adding_section') == 1:
        st.markdown("**➕ Add New Reference**")
        # Move selectbox outside form so it can trigger immediate rerun
        ref_type = st.selectbox(
            "Reference Type:",
            ['text', 'pdf', 'image', 'latex'],
            key='ref_type_1'
        )
        
        with st.form("add_reference_form_1", clear_on_submit=True):
            # Use the ref_type from session state
            ref_type = st.session_state.get('ref_type_1', 'text')
            
            if ref_type == 'pdf':
                st.markdown("""
                <div style="padding: 10px; background: #f0f7ff; border-radius: 5px; margin-bottom: 10px; border: 1px solid #1f77b4;">
                    <strong>📄 PDF Upload Options:</strong><br>
                    • <strong>Drag & Drop:</strong> Drag a PDF file directly onto the upload area below<br>
                    • <strong>Click to Browse:</strong> Click the upload area to select a PDF file
                </div>
                """, unsafe_allow_html=True)
                uploaded_file = st.file_uploader(
                    "Upload PDF (Drag & Drop or Click to Browse)", 
                    type=['pdf'], 
                    key='pdf_upload_1',
                    label_visibility="visible",
                    help="Drag and drop a PDF file here or click to browse. Files are stored and ready for NAS deployment via Docker."
                )
                remarks = st.text_area("Remarks (explain calculation/design):", key='pdf_remarks_1', height=100)
            
            elif ref_type == 'image':
                st.markdown("""
                <div style="padding: 10px; background: #f0f7ff; border-radius: 5px; margin-bottom: 10px; border: 1px solid #1f77b4;">
                    <strong>📤 Upload Options:</strong><br>
                    • <strong>Drag & Drop:</strong> Drag an image file directly onto the upload area below<br>
                    • <strong>Click to Browse:</strong> Click the upload area to select a file<br>
                    • <strong>Paste from Clipboard:</strong> Copy an image (Ctrl+C / Cmd+C), then click the paste area below and press <strong>Ctrl+V / Cmd+V</strong>
                </div>
                """, unsafe_allow_html=True)
                
                uploaded_files = st.file_uploader(
                    "Upload Images (Drag & Drop or Click to Browse) - Multiple files allowed", 
                    type=['png', 'jpg', 'jpeg', 'gif', 'webp'], 
                    key='img_upload_1',
                    label_visibility="visible",
                    accept_multiple_files=True,
                    help="Drag and drop multiple image files here or click to browse. Files are stored and ready for NAS deployment via Docker."
                )
                
                # Paste image from clipboard
                st.markdown("**Or paste image from clipboard:**")
                paste_input = st.text_area(
                    "Click here and paste image (Ctrl+V / Cmd+V) - Paste image data URL or use browser's paste feature", 
                    key='paste_input_1',
                    height=120,
                    help="Copy an image to clipboard, then click in this box and press Ctrl+V (Windows/Linux) or Cmd+V (Mac). Some browsers also support pasting directly into the upload area above."
                )
                
                pasted_image_data = None
                if paste_input and paste_input.strip():
                    if paste_input.startswith('data:image'):
                        try:
                            # Extract base64 data
                            header, encoded = paste_input.split(',', 1)
                            pasted_image_data = base64.b64decode(encoded)
                            st.success("✅ Image pasted successfully from clipboard!")
                        except Exception as e:
                            st.error(f"Error parsing pasted image: {str(e)}")
                    else:
                        # Try to decode as base64 directly
                        try:
                            pasted_image_data = base64.b64decode(paste_input)
                            st.success("✅ Image data decoded successfully!")
                        except:
                            st.info("💡 Paste a data URL (data:image/...) or base64 encoded image data")
                
                # Add JavaScript for direct paste into upload area (enhancement)
                st.markdown("""
                <script>
                (function() {
                    // Wait for Streamlit to render
                    setTimeout(function() {
                        const uploadInputs = document.querySelectorAll('input[type="file"]');
                        uploadInputs.forEach(function(input) {
                            if (input.accept && input.accept.includes('image')) {
                                // Make the parent container focusable for paste
                                const container = input.closest('[data-testid="stFileUploader"]') || input.parentElement;
                                if (container) {
                                    container.setAttribute('tabindex', '0');
                                    container.style.outline = 'none';
                                    
                                    // Handle paste event
                                    container.addEventListener('paste', function(e) {
                                        e.preventDefault();
                                        const items = e.clipboardData.items;
                                        
                                        for (let i = 0; i < items.length; i++) {
                                            if (items[i].type.indexOf('image') !== -1) {
                                                const blob = items[i].getAsFile();
                                                const file = new File([blob], 'pasted_image.png', {type: 'image/png'});
                                                
                                                // Create a new FileList with the pasted file
                                                const dataTransfer = new DataTransfer();
                                                dataTransfer.items.add(file);
                                                input.files = dataTransfer.files;
                                                
                                                // Trigger change event
                                                const event = new Event('change', { bubbles: true });
                                                input.dispatchEvent(event);
                                                
                                                // Visual feedback
                                                const indicator = document.createElement('div');
                                                indicator.textContent = '📋 Image pasted!';
                                                indicator.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #28a745; color: white; padding: 10px 20px; border-radius: 5px; z-index: 10000;';
                                                document.body.appendChild(indicator);
                                                setTimeout(function() { indicator.remove(); }, 2000);
                                                
                                                break;
                                            }
                                        }
                                    });
                                    
                                    // Enhanced drag and drop visual feedback
                                    container.addEventListener('dragover', function(e) {
                                        e.preventDefault();
                                        container.style.border = '2px dashed #1f77b4';
                                        container.style.backgroundColor = '#e6f2ff';
                                    });
                                    
                                    container.addEventListener('dragleave', function(e) {
                                        e.preventDefault();
                                        container.style.border = '';
                                        container.style.backgroundColor = '';
                                    });
                                    
                                    container.addEventListener('drop', function(e) {
                                        e.preventDefault();
                                        container.style.border = '';
                                        container.style.backgroundColor = '';
                                    });
                                }
                            }
                        });
                    }, 500);
                })();
                </script>
                """, unsafe_allow_html=True)
                
                remarks = st.text_area("Remarks (explain calculation/design):", key='img_remarks_1', height=100)
            
            elif ref_type == 'text':
                content = st.text_area("Content:", height=200, key='text_content_1')
                remarks = st.text_area("Remarks (explain calculation/design):", key='text_remarks_1', height=100)
            
            elif ref_type == 'latex':
                equation = st.text_input("LaTeX Equation (e.g., E = mc^2):", key='latex_eq_1')
                remarks = st.text_area("Remarks (explain calculation/design):", key='latex_remarks_1', height=100)
            
            col_sub1, col_can1 = st.columns(2)
            with col_sub1:
                submitted = st.form_submit_button("✅ Add Reference")
            with col_can1:
                cancel = st.form_submit_button("❌ Cancel")
            
            if submitted:
                project_key = st.session_state.current_project
                
                if ref_type == 'pdf' and uploaded_file:
                    ref_num = st.session_state.reference_counter
                    new_ref = {
                        'id': ref_num,
                        'type': ref_type,
                        'section': 'section_1',
                        'remarks': remarks if 'remarks' in locals() else ''
                    }
                    filename = uploaded_file.name
                    file_path = save_reference_file(project_key, ref_num, filename, uploaded_file)
                    new_ref['file_path'] = file_path
                    new_ref['filename'] = filename
                    references['section_1'].append(new_ref)
                    st.session_state.reference_counter += 1
                    
                elif ref_type == 'image':
                    # Handle multiple uploaded files and pasted images
                    images_added = False
                    
                    # Process multiple uploaded files
                    if 'uploaded_files' in locals() and uploaded_files:
                        for uploaded_file in uploaded_files:
                            if uploaded_file:
                                ref_num = st.session_state.reference_counter
                                new_ref = {
                                    'id': ref_num,
                                    'type': ref_type,
                                    'section': 'section_1',
                                    'remarks': remarks if 'remarks' in locals() else ''
                                }
                                filename = uploaded_file.name
                                file_path = save_reference_file(project_key, ref_num, filename, uploaded_file)
                                new_ref['file_path'] = file_path
                                new_ref['filename'] = filename
                                references['section_1'].append(new_ref)
                                st.session_state.reference_counter += 1
                                images_added = True
                    
                    # Process pasted image
                    if 'pasted_image_data' in locals() and pasted_image_data:
                        ref_num = st.session_state.reference_counter
                        new_ref = {
                            'id': ref_num,
                            'type': ref_type,
                            'section': 'section_1',
                            'remarks': remarks if 'remarks' in locals() else ''
                        }
                        # Determine file extension from data URL header or default to png
                        ext = 'png'  # default
                        if 'paste_input' in locals() and paste_input:
                            if paste_input.startswith('data:image/png'):
                                ext = 'png'
                            elif paste_input.startswith('data:image/jpeg') or paste_input.startswith('data:image/jpg'):
                                ext = 'jpg'
                            elif paste_input.startswith('data:image/gif'):
                                ext = 'gif'
                            elif paste_input.startswith('data:image/webp'):
                                ext = 'webp'
                        filename = f"pasted_image_{ref_num}.{ext}"
                        file_path = save_reference_file(project_key, ref_num, filename, pasted_image_data)
                        new_ref['file_path'] = file_path
                        new_ref['filename'] = filename
                        references['section_1'].append(new_ref)
                        st.session_state.reference_counter += 1
                        images_added = True
                    
                    if not images_added:
                        st.warning("⚠️ Please upload at least one image or paste an image.")
                    else:
                        st.session_state.ref_adding_section = None
                        st.rerun()
                        
                if ref_type != 'image' or ('images_added' in locals() and not images_added):
                    if ref_type == 'text':
                        ref_num = st.session_state.reference_counter
                        new_ref = {
                            'id': ref_num,
                            'type': ref_type,
                            'section': 'section_1',
                            'remarks': remarks if 'remarks' in locals() else '',
                            'content': content
                        }
                        references['section_1'].append(new_ref)
                        st.session_state.reference_counter += 1
                        
                    elif ref_type == 'latex':
                        ref_num = st.session_state.reference_counter
                        new_ref = {
                            'id': ref_num,
                            'type': ref_type,
                            'section': 'section_1',
                            'remarks': remarks if 'remarks' in locals() else '',
                            'equation': equation
                        }
                        references['section_1'].append(new_ref)
                        st.session_state.reference_counter += 1
                    
                    if ref_type != 'image':
                        st.session_state.ref_adding_section = None
                        st.rerun()
            
            if cancel:
                st.session_state.ref_adding_section = None
                st.rerun()
    
    # Display references for section 1
    if references['section_1']:
        st.markdown("**References:**")
        for ref in references['section_1']:
            render_reference(ref, ref['id'], 'section_1')
    else:
        st.info("👆 Add references above to document your WWTP Sections design calculations")
    
    st.divider()
    
    # Section 2: Process Flow Diagram References
    st.subheader('2️⃣ Process Flow Diagram - References')
    
    col_ref2_1, col_ref2_2 = st.columns([3, 1])
    with col_ref2_1:
        st.markdown("**Add Reference for Process Flow Diagram:**")
    with col_ref2_2:
        if st.button('➕ Add Reference', key='add_ref_section_2'):
            st.session_state.ref_adding_section = 2
            st.rerun()
    
    if st.session_state.get('ref_adding_section') == 2:
        st.markdown("**➕ Add New Reference**")
        # Move selectbox outside form so it can trigger immediate rerun
        ref_type = st.selectbox(
            "Reference Type:",
            ['text', 'pdf', 'image', 'latex'],
            key='ref_type_2'
        )
        
        with st.form("add_reference_form_2", clear_on_submit=True):
            # Use the ref_type from session state
            ref_type = st.session_state.get('ref_type_2', 'text')
            
            if ref_type == 'pdf':
                st.markdown("""
                <div style="padding: 10px; background: #f0f7ff; border-radius: 5px; margin-bottom: 10px; border: 1px solid #1f77b4;">
                    <strong>📄 PDF Upload Options:</strong><br>
                    • <strong>Drag & Drop:</strong> Drag a PDF file directly onto the upload area below<br>
                    • <strong>Click to Browse:</strong> Click the upload area to select a PDF file
                </div>
                """, unsafe_allow_html=True)
                uploaded_file = st.file_uploader(
                    "Upload PDF (Drag & Drop or Click to Browse)", 
                    type=['pdf'], 
                    key='pdf_upload_2',
                    label_visibility="visible",
                    help="Drag and drop a PDF file here or click to browse. Files are stored and ready for NAS deployment via Docker."
                )
                remarks = st.text_area("Remarks (explain calculation/design):", key='pdf_remarks_2', height=100)
            
            elif ref_type == 'image':
                st.markdown("""
                <div style="padding: 10px; background: #f0f7ff; border-radius: 5px; margin-bottom: 10px; border: 1px solid #1f77b4;">
                    <strong>📤 Upload Options:</strong><br>
                    • <strong>Drag & Drop:</strong> Drag an image file directly onto the upload area below<br>
                    • <strong>Click to Browse:</strong> Click the upload area to select a file<br>
                    • <strong>Paste from Clipboard:</strong> Copy an image (Ctrl+C / Cmd+C), then click the paste area below and press <strong>Ctrl+V / Cmd+V</strong>
                </div>
                """, unsafe_allow_html=True)
                
                uploaded_files = st.file_uploader(
                    "Upload Images (Drag & Drop or Click to Browse) - Multiple files allowed", 
                    type=['png', 'jpg', 'jpeg', 'gif', 'webp'], 
                    key='img_upload_2',
                    label_visibility="visible",
                    accept_multiple_files=True,
                    help="Drag and drop multiple image files here or click to browse. Files are stored and ready for NAS deployment via Docker."
                )
                
                # Paste image from clipboard
                st.markdown("**Or paste image from clipboard:**")
                paste_input = st.text_area(
                    "Click here and paste image (Ctrl+V / Cmd+V) - Paste image data URL or use browser's paste feature", 
                    key='paste_input_2',
                    height=120,
                    help="Copy an image to clipboard, then click in this box and press Ctrl+V (Windows/Linux) or Cmd+V (Mac). Some browsers also support pasting directly into the upload area above."
                )
                
                pasted_image_data = None
                if paste_input and paste_input.strip():
                    if paste_input.startswith('data:image'):
                        try:
                            # Extract base64 data
                            header, encoded = paste_input.split(',', 1)
                            pasted_image_data = base64.b64decode(encoded)
                            st.success("✅ Image pasted successfully from clipboard!")
                        except Exception as e:
                            st.error(f"Error parsing pasted image: {str(e)}")
                    else:
                        # Try to decode as base64 directly
                        try:
                            pasted_image_data = base64.b64decode(paste_input)
                            st.success("✅ Image data decoded successfully!")
                        except:
                            st.info("💡 Paste a data URL (data:image/...) or base64 encoded image data")
                
                remarks = st.text_area("Remarks (explain calculation/design):", key='img_remarks_2', height=100)
            
            elif ref_type == 'text':
                content = st.text_area("Content:", height=200, key='text_content_2')
                remarks = st.text_area("Remarks (explain calculation/design):", key='text_remarks_2', height=100)
            
            elif ref_type == 'latex':
                equation = st.text_input("LaTeX Equation (e.g., E = mc^2):", key='latex_eq_2')
                remarks = st.text_area("Remarks (explain calculation/design):", key='latex_remarks_2', height=100)
            
            col_sub2, col_can2 = st.columns(2)
            with col_sub2:
                submitted = st.form_submit_button("✅ Add Reference")
            with col_can2:
                cancel = st.form_submit_button("❌ Cancel")
            
            if submitted:
                project_key = st.session_state.current_project
                
                if ref_type == 'pdf' and uploaded_file:
                    ref_num = st.session_state.reference_counter
                    new_ref = {
                        'id': ref_num,
                        'type': ref_type,
                        'section': 'section_2',
                        'remarks': remarks if 'remarks' in locals() else ''
                    }
                    filename = uploaded_file.name
                    file_path = save_reference_file(project_key, ref_num, filename, uploaded_file)
                    new_ref['file_path'] = file_path
                    new_ref['filename'] = filename
                    references['section_2'].append(new_ref)
                    st.session_state.reference_counter += 1
                    
                elif ref_type == 'image':
                    # Handle multiple uploaded files and pasted images
                    images_added = False
                    
                    # Process multiple uploaded files
                    if 'uploaded_files' in locals() and uploaded_files:
                        for uploaded_file in uploaded_files:
                            if uploaded_file:
                                ref_num = st.session_state.reference_counter
                                new_ref = {
                                    'id': ref_num,
                                    'type': ref_type,
                                    'section': 'section_2',
                                    'remarks': remarks if 'remarks' in locals() else ''
                                }
                                filename = uploaded_file.name
                                file_path = save_reference_file(project_key, ref_num, filename, uploaded_file)
                                new_ref['file_path'] = file_path
                                new_ref['filename'] = filename
                                references['section_2'].append(new_ref)
                                st.session_state.reference_counter += 1
                                images_added = True
                    
                    # Process pasted image
                    if 'pasted_image_data' in locals() and pasted_image_data:
                        ref_num = st.session_state.reference_counter
                        new_ref = {
                            'id': ref_num,
                            'type': ref_type,
                            'section': 'section_2',
                            'remarks': remarks if 'remarks' in locals() else ''
                        }
                        # Determine file extension from data URL header or default to png
                        ext = 'png'  # default
                        if 'paste_input' in locals() and paste_input:
                            if paste_input.startswith('data:image/png'):
                                ext = 'png'
                            elif paste_input.startswith('data:image/jpeg') or paste_input.startswith('data:image/jpg'):
                                ext = 'jpg'
                            elif paste_input.startswith('data:image/gif'):
                                ext = 'gif'
                            elif paste_input.startswith('data:image/webp'):
                                ext = 'webp'
                        filename = f"pasted_image_{ref_num}.{ext}"
                        file_path = save_reference_file(project_key, ref_num, filename, pasted_image_data)
                        new_ref['file_path'] = file_path
                        new_ref['filename'] = filename
                        references['section_2'].append(new_ref)
                        st.session_state.reference_counter += 1
                        images_added = True
                    
                    if not images_added:
                        st.warning("⚠️ Please upload at least one image or paste an image.")
                    else:
                        st.session_state.ref_adding_section = None
                        st.rerun()
                        
                if ref_type != 'image' or ('images_added' in locals() and not images_added):
                    if ref_type == 'text':
                        ref_num = st.session_state.reference_counter
                        new_ref = {
                            'id': ref_num,
                            'type': ref_type,
                            'section': 'section_2',
                            'remarks': remarks if 'remarks' in locals() else '',
                            'content': content
                        }
                        references['section_2'].append(new_ref)
                        st.session_state.reference_counter += 1
                        
                    elif ref_type == 'latex':
                        ref_num = st.session_state.reference_counter
                        new_ref = {
                            'id': ref_num,
                            'type': ref_type,
                            'section': 'section_2',
                            'remarks': remarks if 'remarks' in locals() else '',
                            'equation': equation
                        }
                        references['section_2'].append(new_ref)
                        st.session_state.reference_counter += 1
                    
                    if ref_type != 'image':
                        st.session_state.ref_adding_section = None
                        st.rerun()
            
            if cancel:
                st.session_state.ref_adding_section = None
                st.rerun()
    
    # Display references for section 2
    if references['section_2']:
        st.markdown("**References:**")
        for ref in references['section_2']:
            render_reference(ref, ref['id'], 'section_2')
    else:
        st.info("👆 Add references above to document your Process Flow Diagram design calculations")
    
    st.divider()
    
    # Section 3: Discharge Configuration References
    st.subheader('3️⃣ Discharge Configuration - References')
    
    col_ref3_1, col_ref3_2 = st.columns([3, 1])
    with col_ref3_1:
        st.markdown("**Add Reference for Discharge Configuration:**")
    with col_ref3_2:
        if st.button('➕ Add Reference', key='add_ref_section_3'):
            st.session_state.ref_adding_section = 3
            st.rerun()
    
    if st.session_state.get('ref_adding_section') == 3:
        st.markdown("**➕ Add New Reference**")
        # Move selectbox outside form so it can trigger immediate rerun
        ref_type = st.selectbox(
            "Reference Type:",
            ['text', 'pdf', 'image', 'latex'],
            key='ref_type_3'
        )
        
        with st.form("add_reference_form_3", clear_on_submit=True):
            # Use the ref_type from session state
            ref_type = st.session_state.get('ref_type_3', 'text')
            
            if ref_type == 'pdf':
                st.markdown("""
                <div style="padding: 10px; background: #f0f7ff; border-radius: 5px; margin-bottom: 10px; border: 1px solid #1f77b4;">
                    <strong>📄 PDF Upload Options:</strong><br>
                    • <strong>Drag & Drop:</strong> Drag a PDF file directly onto the upload area below<br>
                    • <strong>Click to Browse:</strong> Click the upload area to select a PDF file
                </div>
                """, unsafe_allow_html=True)
                uploaded_file = st.file_uploader(
                    "Upload PDF (Drag & Drop or Click to Browse)", 
                    type=['pdf'], 
                    key='pdf_upload_3',
                    label_visibility="visible",
                    help="Drag and drop a PDF file here or click to browse. Files are stored and ready for NAS deployment via Docker."
                )
                remarks = st.text_area("Remarks (explain calculation/design):", key='pdf_remarks_3', height=100)
            
            elif ref_type == 'image':
                st.markdown("""
                <div style="padding: 10px; background: #f0f7ff; border-radius: 5px; margin-bottom: 10px; border: 1px solid #1f77b4;">
                    <strong>📤 Upload Options:</strong><br>
                    • <strong>Drag & Drop:</strong> Drag an image file directly onto the upload area below<br>
                    • <strong>Click to Browse:</strong> Click the upload area to select a file<br>
                    • <strong>Paste from Clipboard:</strong> Copy an image (Ctrl+C / Cmd+C), then click the paste area below and press <strong>Ctrl+V / Cmd+V</strong>
                </div>
                """, unsafe_allow_html=True)
                
                uploaded_files = st.file_uploader(
                    "Upload Images (Drag & Drop or Click to Browse) - Multiple files allowed", 
                    type=['png', 'jpg', 'jpeg', 'gif', 'webp'], 
                    key='img_upload_3',
                    label_visibility="visible",
                    accept_multiple_files=True,
                    help="Drag and drop multiple image files here or click to browse. Files are stored and ready for NAS deployment via Docker."
                )
                
                # Paste image from clipboard
                st.markdown("**Or paste image from clipboard:**")
                paste_input = st.text_area(
                    "Click here and paste image (Ctrl+V / Cmd+V) - Paste image data URL or use browser's paste feature", 
                    key='paste_input_3',
                    height=120,
                    help="Copy an image to clipboard, then click in this box and press Ctrl+V (Windows/Linux) or Cmd+V (Mac). Some browsers also support pasting directly into the upload area above."
                )
                
                pasted_image_data = None
                if paste_input and paste_input.strip():
                    if paste_input.startswith('data:image'):
                        try:
                            # Extract base64 data
                            header, encoded = paste_input.split(',', 1)
                            pasted_image_data = base64.b64decode(encoded)
                            st.success("✅ Image pasted successfully from clipboard!")
                        except Exception as e:
                            st.error(f"Error parsing pasted image: {str(e)}")
                    else:
                        # Try to decode as base64 directly
                        try:
                            pasted_image_data = base64.b64decode(paste_input)
                            st.success("✅ Image data decoded successfully!")
                        except:
                            st.info("💡 Paste a data URL (data:image/...) or base64 encoded image data")
                
                remarks = st.text_area("Remarks (explain calculation/design):", key='img_remarks_3', height=100)
            
            elif ref_type == 'text':
                content = st.text_area("Content:", height=200, key='text_content_3')
                remarks = st.text_area("Remarks (explain calculation/design):", key='text_remarks_3', height=100)
            
            elif ref_type == 'latex':
                equation = st.text_input("LaTeX Equation (e.g., E = mc^2):", key='latex_eq_3')
                remarks = st.text_area("Remarks (explain calculation/design):", key='latex_remarks_3', height=100)
            
            col_sub3, col_can3 = st.columns(2)
            with col_sub3:
                submitted = st.form_submit_button("✅ Add Reference")
            with col_can3:
                cancel = st.form_submit_button("❌ Cancel")
            
            if submitted:
                project_key = st.session_state.current_project
                
                if ref_type == 'pdf' and uploaded_file:
                    ref_num = st.session_state.reference_counter
                    new_ref = {
                        'id': ref_num,
                        'type': ref_type,
                        'section': 'section_3',
                        'remarks': remarks if 'remarks' in locals() else ''
                    }
                    filename = uploaded_file.name
                    file_path = save_reference_file(project_key, ref_num, filename, uploaded_file)
                    new_ref['file_path'] = file_path
                    new_ref['filename'] = filename
                    references['section_3'].append(new_ref)
                    st.session_state.reference_counter += 1
                    
                elif ref_type == 'image':
                    # Handle multiple uploaded files and pasted images
                    images_added = False
                    
                    # Process multiple uploaded files
                    if 'uploaded_files' in locals() and uploaded_files:
                        for uploaded_file in uploaded_files:
                            if uploaded_file:
                                ref_num = st.session_state.reference_counter
                                new_ref = {
                                    'id': ref_num,
                                    'type': ref_type,
                                    'section': 'section_3',
                                    'remarks': remarks if 'remarks' in locals() else ''
                                }
                                filename = uploaded_file.name
                                file_path = save_reference_file(project_key, ref_num, filename, uploaded_file)
                                new_ref['file_path'] = file_path
                                new_ref['filename'] = filename
                                references['section_3'].append(new_ref)
                                st.session_state.reference_counter += 1
                                images_added = True
                    
                    # Process pasted image
                    if 'pasted_image_data' in locals() and pasted_image_data:
                        ref_num = st.session_state.reference_counter
                        new_ref = {
                            'id': ref_num,
                            'type': ref_type,
                            'section': 'section_3',
                            'remarks': remarks if 'remarks' in locals() else ''
                        }
                        # Determine file extension from data URL header or default to png
                        ext = 'png'  # default
                        if 'paste_input' in locals() and paste_input:
                            if paste_input.startswith('data:image/png'):
                                ext = 'png'
                            elif paste_input.startswith('data:image/jpeg') or paste_input.startswith('data:image/jpg'):
                                ext = 'jpg'
                            elif paste_input.startswith('data:image/gif'):
                                ext = 'gif'
                            elif paste_input.startswith('data:image/webp'):
                                ext = 'webp'
                        filename = f"pasted_image_{ref_num}.{ext}"
                        file_path = save_reference_file(project_key, ref_num, filename, pasted_image_data)
                        new_ref['file_path'] = file_path
                        new_ref['filename'] = filename
                        references['section_3'].append(new_ref)
                        st.session_state.reference_counter += 1
                        images_added = True
                    
                    if not images_added:
                        st.warning("⚠️ Please upload at least one image or paste an image.")
                    else:
                        st.session_state.ref_adding_section = None
                        st.rerun()
                        
                if ref_type != 'image' or ('images_added' in locals() and not images_added):
                    if ref_type == 'text':
                        ref_num = st.session_state.reference_counter
                        new_ref = {
                            'id': ref_num,
                            'type': ref_type,
                            'section': 'section_3',
                            'remarks': remarks if 'remarks' in locals() else '',
                            'content': content
                        }
                        references['section_3'].append(new_ref)
                        st.session_state.reference_counter += 1
                        
                    elif ref_type == 'latex':
                        ref_num = st.session_state.reference_counter
                        new_ref = {
                            'id': ref_num,
                            'type': ref_type,
                            'section': 'section_3',
                            'remarks': remarks if 'remarks' in locals() else '',
                            'equation': equation
                        }
                        references['section_3'].append(new_ref)
                        st.session_state.reference_counter += 1
                    
                    if ref_type != 'image':
                        st.session_state.ref_adding_section = None
                        st.rerun()
            
            if cancel:
                st.session_state.ref_adding_section = None
                st.rerun()
    
    # Display references for section 3
    if references['section_3']:
        st.markdown("**References:**")
        for ref in references['section_3']:
            render_reference(ref, ref['id'], 'section_3')
    else:
        st.info("👆 Add references above to document your Discharge Configuration design calculations")
    
    # Store references
    st.session_state.references = references

# ==================== PYTHON CODING GUIDE TAB ====================
with tab3:
    st.header('🐍 Python Coding Guide')
    st.caption("Reference for writing Python code in Mass Balance sections. Add section-specific guide cards for future design reuse.")

    st.subheader('📚 Beginner Guides')
    st.caption("Start here if you have basic Python skills. Work through these 11 guides in order.")

    # --- Guide 1: How Mass Balance Python Works ---
    with st.expander("1️⃣ Guide 1: How Mass Balance Python Code Works", expanded=True):
        st.markdown("""
**What happens when you run Python in Mass Balance?**

Each WWTP section (Headworks, Primary, Aeration, etc.) has its own Python code box. When you click **Run Code**:
1. Your code receives `mb_data` — a dictionary with this section's intake (from upstream) and outlet (what you write)
2. Your job: **read** intake, **calculate** outlet flow, BOD, TSS, sludge, return flow (if any)
3. You **update** `mb_data['outlet']`, `mb_data['sludge_discharge']`, and maybe `mb_data['return_flow']`
4. Those values flow to the next section automatically

**Key idea:** Intake is given. You compute and write the outlet. The next section uses your outlet as its intake.
        """)
        st.markdown("**Minimal example — pass-through (no treatment):**")
        st.code("""# Simplest case: outlet = intake (no removal, no sludge)
mb_data['outlet']['flow'] = mb_data['intake']['flow']
mb_data['outlet']['BOD'] = mb_data['intake']['BOD']
mb_data['outlet']['TSS'] = mb_data['intake']['TSS']
mb_data['sludge_discharge']['flow'] = 0.0
print("Pass-through: outlet = intake")""", language="python")
        st.caption("👆 Copy this code and try it in any section to see how data flows.")

    # --- Guide 2: Reading Inputs and Simple Calculations ---
    with st.expander("2️⃣ Guide 2: Reading Inputs and Simple Calculations"):
        st.markdown("""
**How to read intake and do mass balance math**

- **Flow** is in m³/day; **BOD** and **TSS** are in mg/L
- **Load (kg/d)** = flow × concentration ÷ 1000
  - Example: 10000 m³/day × 250 mg/L ÷ 1000 = 2500 kg BOD/day
- Use `defaults` for project-wide values (Q_avg, BOD_in, etc.)
- Use `print()` to show results in the output area
        """)
        st.markdown("**Example: Read intake, compute loads, apply removal %:**")
        st.code("""# Step 1: Read intake
Q = mb_data['intake']['flow']
BOD_in = mb_data['intake']['BOD']
TSS_in = mb_data['intake']['TSS']

# Step 2: Convert to loads (kg/d)
BOD_load = Q * BOD_in / 1000
TSS_load = Q * TSS_in / 1000

# Step 3: Apply removal (e.g. 30% BOD, 50% TSS in primary)
BOD_removed = BOD_load * 0.30
TSS_removed = TSS_load * 0.50
BOD_out_load = BOD_load - BOD_removed
TSS_out_load = TSS_load - TSS_removed

# Step 4: Assume outlet flow = intake flow (no sludge for now)
Q_out = Q
mb_data['outlet']['flow'] = Q_out
mb_data['outlet']['BOD'] = (BOD_out_load / Q_out) * 1000  # kg/d -> mg/L
mb_data['outlet']['TSS'] = (TSS_out_load / Q_out) * 1000
mb_data['sludge_discharge']['flow'] = 0.0

print(f"Intake: {Q:.0f} m³/d, BOD: {BOD_in:.0f} mg/L → Outlet BOD: {mb_data['outlet']['BOD']:.1f} mg/L")""", language="python")
        st.caption("👆 Copy and adapt the removal % and formulas for your section.")

    # --- Guide 3: Using fsolve for Multiple Unknowns ---
    with st.expander("3️⃣ Guide 3: Using fsolve for Multiple Unknowns"):
        st.markdown("""
**When outlet BOD, TSS, sludge flow, and return flow depend on each other**, you need to solve a system of equations. `fsolve` finds values that make all equations = 0.

**Pattern:**
1. Define a function `residuals(x)` where `x` = list of unknowns
2. Inside `residuals`, write each mass-balance equation; return a list of "errors" (should be 0)
3. Call `fsolve(residuals, x0)` — `x0` = initial guess
4. Use the result to update `mb_data`
        """)
        st.markdown("**Example: Solve for outlet BOD and TSS with target removal % (no sludge):**")
        st.code("""from scipy.optimize import fsolve
import numpy as np

Q = mb_data['intake']['flow']
BOD_load = mb_data['intake']['flow'] * mb_data['intake']['BOD'] / 1000
TSS_load = mb_data['intake']['flow'] * mb_data['intake']['TSS'] / 1000

# Unknowns: x = [outlet_BOD_mgL, outlet_TSS_mgL]
def residuals(x):
    ob, ot = x
    outlet_bod_load = Q * ob / 1000
    outlet_tss_load = Q * ot / 1000
    bod_removed = BOD_load - outlet_bod_load
    tss_removed = TSS_load - outlet_tss_load
    # Target: 90% BOD removal, 95% TSS removal
    eq1 = bod_removed - BOD_load * 0.90
    eq2 = tss_removed - TSS_load * 0.95
    return [eq1, eq2]

guess = [mb_data['intake']['BOD'] * 0.1, mb_data['intake']['TSS'] * 0.05]
result = fsolve(residuals, guess)
ob, ot = result

mb_data['outlet']['flow'] = Q
mb_data['outlet']['BOD'] = ob
mb_data['outlet']['TSS'] = ot
mb_data['sludge_discharge']['flow'] = 0.0
print(f"Outlet BOD: {ob:.1f} mg/L, TSS: {ot:.1f} mg/L")""", language="python")
        st.caption("👆 For sludge and return flow (RAS), see the full example in **Available Libraries & Variables** below.")

    # --- Guide 4: If-Else Conditional Logic ---
    with st.expander("4️⃣ Guide 4: If-Else Conditional Logic"):
        st.markdown("""
**Use `if` / `elif` / `else` when your section behaves differently** based on conditions.

Common cases:
- **Entry point** vs downstream (entry uses `defaults`, downstream uses intake)
- **Has return flow** (RAS) vs no return flow
- **Section type** (Headworks, Primary, Aeration) — different removal %
- **Guard against bad data** (zero flow, missing values)
        """)
        st.markdown("**Example: Different logic for entry point vs downstream:**")
        st.code("""# Check if this section is an entry point (gets flow from defaults, not upstream)
is_entry = section_name in ['Headworks', 'Inlet']  # adjust to your section names

if is_entry:
    Q = defaults.get('Q_avg', 60000)
    BOD = defaults.get('BOD_in', 250)
    TSS = defaults.get('TSS_in', 220)
else:
    Q = mb_data['intake']['flow']
    BOD = mb_data['intake']['BOD']
    TSS = mb_data['intake']['TSS']

# Different removal by section type
if 'Primary' in section_name:
    bod_removal = 0.30
    tss_removal = 0.50
elif 'Aeration' in section_name:
    bod_removal = 0.90
    tss_removal = 0.95
else:
    bod_removal = 0.0
    tss_removal = 0.0

BOD_out = BOD * (1 - bod_removal)
TSS_out = TSS * (1 - tss_removal)
mb_data['outlet']['flow'] = Q
mb_data['outlet']['BOD'] = BOD_out
mb_data['outlet']['TSS'] = TSS_out
mb_data['sludge_discharge']['flow'] = 0.0
print(f"{section_name}: BOD {BOD:.0f} → {BOD_out:.1f} mg/L ({bod_removal*100:.0f}% removal)")""", language="python")
        st.caption("👆 Adapt `is_entry` and section names to your Process Flow Diagram.")

    # --- Guide 5: For Loops ---
    with st.expander("5️⃣ Guide 5: For Loops"):
        st.markdown("""
**Use `for` loops to** iterate over lists or repeated logic.

Typical uses:
- Loop over `overview['sections']` to find this section's config
- Loop over `overview['flow_connections']` to see where flow goes
- Loop over multiple parameters (e.g., BOD, TSS, NH3) with same formula
- Loop for iterative refinement (e.g., guess-and-check)
        """)
        st.markdown("**Example: Loop over parameters + find section config from overview:**")
        st.code("""# Loop to find if THIS section has return flow (from overview)
has_return = False
for s in overview['sections']:
    if s.get('name') == section_name and s.get('has_return_flow') and s.get('return_to'):
        has_return = True
        break

# Loop over concentration params (BOD, TSS) with same removal formula
params = ['BOD', 'TSS']
removal = {'BOD': 0.90, 'TSS': 0.95}
Q = mb_data['intake']['flow']

for p in params:
    load_in = Q * mb_data['intake'].get(p, 0) / 1000
    load_out = load_in * (1 - removal.get(p, 0))
    mb_data['outlet'][p] = (load_out / Q) * 1000 if Q > 0 else 0

mb_data['outlet']['flow'] = Q
mb_data['sludge_discharge']['flow'] = 0.0
if has_return:
    mb_data['return_flow']['flow'] = 0.0  # set in fsolve example
print(f"Processed {len(params)} params. Has return flow: {has_return}")""", language="python")
        st.caption("👆 Use `any()` as shorthand: `has_return = any(s['name']==section_name and ... for s in overview['sections'])`.")

    # --- Guide 6: Using defaults and overview ---
    with st.expander("6️⃣ Guide 6: Using defaults and overview"):
        st.markdown("""
**`defaults`** = project default parameters (from Design Parameters). Common keys:
- `Q_avg`, `BOD_in`, `TSS_in` — inflow
- `MLSS`, `SRT`, `Y`, `kd` — activated sludge design

**`overview`** = Process Flow Diagram structure:
- `overview['sections']` — list of `{name, effluent_to, has_return_flow, return_to, sludge_to, ...}`
- `overview['flow_connections']` — list of `{from, to}`
        """)
        st.markdown("**Example: Read defaults and check overview structure:**")
        st.code("""# Project design flow and influent quality
Q_design = defaults.get('Q_avg', 60000)
BOD_design = defaults.get('BOD_in', 250)
TSS_design = defaults.get('TSS_in', 220)

# Use design values for entry points, else use intake
upstream_names = [c['from'] for c in overview.get('flow_connections', []) if c['to'] == section_name]
is_entry = len(upstream_names) == 0

if is_entry:
    Q, BOD, TSS = Q_design, BOD_design, TSS_design
else:
    Q = mb_data['intake']['flow']
    BOD = mb_data['intake'].get('BOD', BOD_design)
    TSS = mb_data['intake'].get('TSS', TSS_design)

# Where does sludge from this section go?
my_section = next((s for s in overview['sections'] if s.get('name') == section_name), {})
sludge_to = my_section.get('sludge_to', [])

print(f"Section: {section_name}, Entry: {is_entry}, Sludge to: {sludge_to}")""", language="python")
        st.caption("👆 `next(..., {})` returns the first matching section or empty dict if not found.")

    # --- Guide 7: Design Parameters (Kinetic & System) ---
    with st.expander("7️⃣ Guide 7: Design Parameters (Kinetic & System)"):
        st.markdown("""
**`design_params`** = Design Parameters from the Default Parameters panel (Kinetic Parameters and System Parameters).

Use this variable to access:
- **Kinetic parameters:** `Y` (yield), `kd` (decay), `SRT` (sludge retention time), plus any custom kinetic params (e.g. `Ks`, `mu_max`) you add in Design Parameters
- **System parameters:** `MLSS` (mixed liquor suspended solids), plus any custom system params (e.g. `HRT`, `F/M`) you add in Design Parameters

**Structure:**
- `design_params['kinetic']['Y']` — always available (built-in)
- `design_params['kinetic']['Ks']` — only if you added "Ks" as a custom Kinetic parameter
- `design_params['system']['MLSS']` — always available (built-in)
- `design_params['system']['HRT']` — only if you added "HRT" as a custom System parameter

**When to use:** Activated sludge calculations, Monod kinetics, F/M ratio, HRT checks, or any design formula that needs kinetic or system constants.
        """)
        st.markdown("**Example: Use kinetic and system parameters in mass balance:**")
        st.code("""# Read Kinetic Parameters (Y, kd, SRT) and System Parameters (MLSS)
Y = design_params['kinetic']['Y']
kd = design_params['kinetic']['kd']
SRT = design_params['kinetic']['SRT']
MLSS = design_params['system']['MLSS']

# Use in activated sludge formula: 1/SRT = Y * (F/M) - kd
Q = mb_data['intake']['flow']
BOD_load = Q * mb_data['intake']['BOD'] / 1000
V = 5000  # tank volume m³ (or from custom system param)
F_M = BOD_load / (V * MLSS / 1000)  # kg BOD / kg MLSS / day
mu = Y * F_M * (MLSS/1000) / (V * MLSS/1e6) - kd  # simplified
print(f"F/M: {F_M:.3f}, 1/SRT target: {1/SRT:.3f}")""", language="python")
        st.markdown("**Example: Use custom parameters (Ks, HRT) if defined:**")
        st.code("""# Safe access: use .get() if you added custom params
Ks = design_params['kinetic'].get('Ks', 60)      # half-saturation (mg/L), default 60
HRT = design_params['system'].get('HRT', 6)     # hours, default 6

Q = mb_data['intake']['flow']
V = Q * HRT / 24  # volume from hydraulic retention time
print(f"Ks: {Ks} mg/L, HRT: {HRT} h, Est. Volume: {V:.0f} m³")""", language="python")
        st.caption("👆 Add custom Kinetic (e.g. Ks, mu_max) or System (e.g. HRT, F/M) params in **Design Parameters** → Default Parameters → use ➕ to add.")

    # --- Guide 8: Return Flow (RAS) Logic ---
    with st.expander("8️⃣ Guide 8: Return Flow (RAS) Logic"):
        st.markdown("""
**Return flow** = part of the mixed liquor that goes back to an upstream section (e.g., RAS to aeration).

When a section has `has_return_flow` and `return_to`:
- Total flow splits: **outlet** (to downstream) + **return** (to upstream)
- RAS ratio: `return_flow = outlet_flow × ras_ratio`
- Net flow: `outlet_flow = (total_flow - sludge) / (1 + ras_ratio)`
- You must set `mb_data['return_flow']['flow']`, `['BOD']`, `['TSS']`
        """)
        st.markdown("**Example: Split outlet and return flow:**")
        st.code("""has_return = any(s.get('name')==section_name and s.get('has_return_flow') and s.get('return_to')
              for s in overview['sections'])
ras_ratio = 0.5  # 50% RAS

Q_in = mb_data['intake']['flow']
sludge_flow = Q_in * 0.01  # 1% to sludge

net_flow = Q_in - sludge_flow
if has_return:
    outlet_flow = net_flow / (1 + ras_ratio)
    return_flow = outlet_flow * ras_ratio
else:
    outlet_flow = net_flow
    return_flow = 0.0

mb_data['outlet']['flow'] = outlet_flow
mb_data['outlet']['BOD'] = mb_data['intake']['BOD'] * 0.1
mb_data['outlet']['TSS'] = mb_data['intake']['TSS'] * 0.05
mb_data['sludge_discharge']['flow'] = sludge_flow
mb_data['sludge_discharge']['solids'] = 5.0
if has_return:
    mb_data['return_flow']['flow'] = return_flow
    mb_data['return_flow']['BOD'] = mb_data['outlet']['BOD']
    mb_data['return_flow']['TSS'] = mb_data['outlet']['TSS']
else:
    mb_data['return_flow']['flow'] = 0.0
print(f"Outlet: {outlet_flow:.0f}, Return: {return_flow:.0f} m³/d")""", language="python")
        st.caption("👆 Return flow has same BOD/TSS as outlet (mixed liquor).")

    # --- Guide 9: Sludge and Solids Handling ---
    with st.expander("9️⃣ Guide 9: Sludge and Solids Handling"):
        st.markdown("""
**Sludge discharge** = flow and solids % from this section to sludge handling.

- `mb_data['sludge_discharge']['flow']` — m³/day
- `mb_data['sludge_discharge']['solids']` — % (e.g., 5.0 = 5%)
- **Solids mass (kg/d)** = flow × (solids/100) × 1000
- TSS removed → often becomes sludge solids mass
        """)
        st.markdown("**Example: Compute sludge from TSS removal:**")
        st.code("""Q = mb_data['intake']['flow']
TSS_in = mb_data['intake']['TSS']
tss_removal = 0.95  # 95% to sludge
solids_pct = 5.0    # 5% solids in waste sludge

TSS_removed_kgd = Q * TSS_in / 1000 * tss_removal
# Sludge flow: solids_kgd = Q_sludge * (solids%/100) * 1000
# So: Q_sludge = solids_kgd / ((solids/100) * 1000)
sludge_flow = TSS_removed_kgd / ((solids_pct / 100) * 1000)
Q_out = Q - sludge_flow
TSS_out_load = Q * TSS_in / 1000 * (1 - tss_removal)
TSS_out = (TSS_out_load / Q_out * 1000) if Q_out > 0 else 0

mb_data['outlet']['flow'] = Q_out
mb_data['outlet']['TSS'] = TSS_out
mb_data['sludge_discharge']['flow'] = sludge_flow
mb_data['sludge_discharge']['solids'] = solids_pct
print(f"Sludge: {sludge_flow:.1f} m³/d @ {solids_pct}% solids = {TSS_removed_kgd:.1f} kg/d")""", language="python")
        st.caption("👆 Adjust solids % to match your process (thickener vs raw WAS).")

    # --- Guide 10: Lists, Dictionaries, and Safe Access ---
    with st.expander("🔟 Guide 10: Lists, Dictionaries, and Safe Access"):
        st.markdown("""
**Avoid errors** when keys might be missing:

- `d.get('key', default)` — returns value or default if key missing
- `d.get('key')` — returns `None` if missing
- Check before divide: `x / y if y > 0 else 0`
- Loop safely: `for k in d.get('keys', []):`
        """)
        st.markdown("**Example: Safe access to mb_data and overview:**")
        st.code("""# Safe: use .get() with default
flow = mb_data.get('intake', {}).get('flow', 0.0)
BOD = mb_data.get('intake', {}).get('BOD', 250)

# Get all concentration params that exist in intake
intake = mb_data.get('intake', {})
params = [k for k in intake if k != 'flow']

for p in params:
    val = intake.get(p, 0)
    out_val = val * 0.9  # 10% removal
    mb_data.setdefault('outlet', {})[p] = out_val

mb_data['outlet']['flow'] = flow
mb_data.setdefault('sludge_discharge', {})['flow'] = 0.0
mb_data.setdefault('sludge_discharge', {})['solids'] = 0.0

# Avoid divide by zero
load = (flow * BOD / 1000) if flow > 0 else 0
print(f"Processed params: {params}")""", language="python")
        st.caption("👆 `setdefault(key, default)` sets value only if key is missing.")

    # --- Guide 11: Complete Mass Balance Example ---
    with st.expander("1️⃣1️⃣ Guide 11: Complete Mass Balance Example"):
        st.markdown("""
**Putting it all together:** entry check, return flow, sludge, fsolve, and updates.

This example combines:
- if/else for entry vs downstream
- Overview check for return flow
- fsolve for coupled BOD/TSS/sludge
- Sludge solids calculation
- Safe .get() usage
        """)
        st.markdown("**Full example (copy and adapt):**")
        st.code("""from scipy.optimize import fsolve

# 1. Entry vs downstream
upstream = [c['from'] for c in overview.get('flow_connections', []) if c.get('to') == section_name]
if not upstream:
    Q_in = defaults.get('Q_avg', 60000)
    BOD_in = defaults.get('BOD_in', 250)
    TSS_in = defaults.get('TSS_in', 220)
else:
    Q_in = mb_data['intake']['flow']
    BOD_in = mb_data['intake'].get('BOD', 250)
    TSS_in = mb_data['intake'].get('TSS', 220)

BOD_load = Q_in * BOD_in / 1000
TSS_load = Q_in * TSS_in / 1000
has_return = any(s.get('name')==section_name and s.get('has_return_flow') and s.get('return_to')
                for s in overview.get('sections', []))
ras = 0.5

def residuals(x):
    ob, ot, sf = x
    Q_out = Q_in - sf
    if has_return:
        Q_out = Q_out / (1 + ras)
    rf = Q_out * ras if has_return else 0
    bod_out = Q_out * ob / 1000
    bod_rf = rf * ob / 1000 if has_return else 0
    tss_out = Q_out * ot / 1000
    tss_rf = rf * ot / 1000 if has_return else 0
    eq1 = BOD_load - bod_out - bod_rf - BOD_load*0.9
    eq2 = TSS_load - tss_out - tss_rf - TSS_load*0.95
    eq3 = Q_in - Q_out - rf - sf
    return [eq1, eq2, eq3]

r = fsolve(residuals, [BOD_in*0.1, TSS_in*0.05, Q_in*0.01])
ob, ot, sf = r
net = Q_in - sf
if has_return:
    Q_out = net / (1 + ras)
    rf = Q_out * ras
else:
    Q_out = net
    rf = 0.0

mb_data['outlet']['flow'] = Q_out
mb_data['outlet']['BOD'] = ob
mb_data['outlet']['TSS'] = ot
mb_data['sludge_discharge']['flow'] = sf
mb_data['sludge_discharge']['solids'] = 5.0
if has_return:
    mb_data['return_flow']['flow'] = rf
    mb_data['return_flow']['BOD'] = ob
    mb_data['return_flow']['TSS'] = ot
print(f"Done: Q_out={Q_out:.0f}, RAS={rf:.0f}, Sludge={sf:.0f} m³/d")""", language="python")
        st.caption("👆 Combines entry check, return flow, sludge, fsolve, and safe .get(). Adapt removal % and ras to your design.")
    with st.expander("ℹ️ Available Libraries & Variables", expanded=False):
        st.markdown("""
**Available Libraries:**
- `numpy` (as `np`) - Array math + linear algebra
- `scipy.optimize.fsolve` (as `fsolve`) - Non-linear equation solver
- `pandas` (as `pd`) - Data tables + results

**Available Variables:**
- `mb_data` - Current section's mass balance data dictionary with:
  - `mb_data['intake']` - Intake loading: flow (m³/day), BOD (mg/L), TSS (mg/L)
    - Note: Intake is auto-calculated from all sources (upstream sections, return flows, sludge flows, initial loading)
    - Intake accounts for Process Flow Diagram connections, return flows (RAS), and sludge flows
  - `mb_data['outlet']` - Outlet loading: flow (m³/day), BOD (mg/L), TSS (mg/L)
    - **Important:** Update these values - they feed to downstream sections!
  - `mb_data['return_flow']` - Return flow (Python only): flow (m³/day), BOD (mg/L), TSS (mg/L)
    - Set by Python code - no manual/RAS input
  - `mb_data['sludge_discharge']` - Sludge discharge: flow (m³/day), solids (%)
    - Editable via UI or set by Python. Flows to sections defined in Process Flow Diagram (sludge_to)
- `section_name` - Name of the current section
- `defaults` - Project default parameters (Q_avg, BOD_in, TSS_in, etc.)
- `design_params` - Kinetic & System parameters: `design_params['kinetic']` (Y, kd, SRT, custom), `design_params['system']` (MLSS, custom)
- `overview` - Process Flow Diagram structure with sections, flow_connections, return flows, sludge flows

**Example Usage:**
```python
# Example: Mass balance calculation and iterative solve
from scipy.optimize import fsolve
import numpy as np

# Access intake data (from previous section or initial loading)
intake_flow = mb_data['intake']['flow']  # m³/day
intake_bod = mb_data['intake']['BOD']    # mg/L
intake_tss = mb_data['intake']['TSS']    # mg/L

# Calculate intake loads (kg/d)
intake_bod_load = intake_flow * intake_bod / 1000  # m³/day * mg/L / 1000 = kg/d
intake_tss_load = intake_flow * intake_tss / 1000

print(f"Intake Flow: {intake_flow:.2f} m³/day")
print(f"Intake BOD Load: {intake_bod_load:.2f} kg/d")
print(f"Intake TSS Load: {intake_tss_load:.2f} kg/d")

# Example: Solve for outlet BOD, TSS, return flow, and sludge (all from Python)
ras_ratio = 0.5  # e.g. 50% RAS - define in your Python logic
has_return_flow = any(s['name']==section_name and s.get('has_return_flow') and s.get('return_to') for s in overview['sections'])

def residuals(x):
    outlet_bod, outlet_tss, sludge_flow = x
    bod_removal = 0.9  # 90% BOD removal
    tss_removal = 0.95  # 95% TSS removal

    outlet_flow = intake_flow - sludge_flow
    if has_return_flow:
        outlet_flow = outlet_flow / (1 + ras_ratio)  # Net flow splits: outlet + return

    return_flow_val = outlet_flow * ras_ratio if has_return_flow else 0
    outlet_bod_load = outlet_flow * outlet_bod / 1000
    return_bod_load = return_flow_val * outlet_bod / 1000 if has_return_flow else 0
    removed_bod = intake_bod_load * bod_removal
    bod_balance = intake_bod_load - outlet_bod_load - return_bod_load - removed_bod

    outlet_tss_load = outlet_flow * outlet_tss / 1000
    return_tss_load = return_flow_val * outlet_tss / 1000 if has_return_flow else 0
    removed_tss = intake_tss_load * tss_removal
    tss_balance = intake_tss_load - outlet_tss_load - return_tss_load - removed_tss

    flow_balance = intake_flow - outlet_flow - return_flow_val - sludge_flow
    return [bod_balance, tss_balance, flow_balance]

result = fsolve(residuals, [intake_bod * 0.1, intake_tss * 0.05, intake_flow * 0.01])
sludge_flow = result[2]
outlet_flow = intake_flow - sludge_flow
if has_return_flow:
    outlet_flow = outlet_flow / (1 + ras_ratio)
return_flow_val = outlet_flow * ras_ratio if has_return_flow else 0

# Update outlet, return flow, and sludge (all Python-only)
mb_data['outlet']['BOD'] = result[0]
mb_data['outlet']['TSS'] = result[1]
mb_data['outlet']['flow'] = outlet_flow
mb_data['sludge_discharge']['flow'] = sludge_flow
mb_data['sludge_discharge']['solids'] = 5.0  # 5% solids
if has_return_flow:
    mb_data['return_flow']['flow'] = return_flow_val
    mb_data['return_flow']['BOD'] = result[0]
    mb_data['return_flow']['TSS'] = result[1]

print(f"\\nOutlet: {mb_data['outlet']['flow']:.2f} m³/day, BOD: {result[0]:.1f} mg/L, TSS: {result[1]:.1f} mg/L")
if has_return_flow:
    print(f"Return Flow: {return_flow_val:.2f} m³/day")
print(f"Sludge: {sludge_flow:.2f} m³/day, {mb_data['sludge_discharge']['solids']:.1f}% solids")
```
        """)

    st.divider()
    st.subheader('📇 Section-specific Guide Cards')

    # Card CRUD state
    if 'pg_card_editing' not in st.session_state:
        st.session_state.pg_card_editing = None  # card id when editing
    if 'pg_card_adding' not in st.session_state:
        st.session_state.pg_card_adding = False

    cards = st.session_state.python_coding_guide_cards

    # Add new card
    if st.session_state.pg_card_adding:
        with st.form("add_pg_card_form", clear_on_submit=True):
            st.markdown("**➕ Add Guide Card**")
            new_title = st.text_input("Card Title", placeholder="e.g., Aeration Tank Mass Balance")
            new_section = st.text_input("Target Section", placeholder="e.g., Aeration - or leave blank for general")
            new_libraries = st.text_area("Available Libraries:", placeholder="- `numpy` (as `np`) - Array math\\n- `scipy.optimize.fsolve` (as `fsolve`)\\n- `pandas` (as `pd`)", height=80)
            new_variables = st.text_area("Available Variables:", placeholder="- `mb_data` - intake, outlet, return_flow, sludge_discharge\\n- `section_name`, `defaults`, `overview`", height=120)
            new_example = st.text_area("Example Usage (Python code):", placeholder="# Your Python code here...", height=150)
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                submitted = st.form_submit_button("✅ Add")
            with col_a2:
                cancel = st.form_submit_button("❌ Cancel")
            if submitted and new_title.strip():
                cards.append({
                    'id': str(uuid.uuid4())[:8],
                    'title': new_title.strip(),
                    'section': new_section.strip() if new_section else '',
                    'libraries': new_libraries.strip(),
                    'variables': new_variables.strip(),
                    'example_code': new_example.strip()
                })
                st.session_state.python_coding_guide_cards = cards
                st.session_state.pg_card_adding = False
                st.success("Card added!")
                log_activity('pg_card_added', new_title.strip())
                st.rerun()
            if cancel:
                st.session_state.pg_card_adding = False
                st.rerun()
    else:
        if st.button("➕ Add Guide Card", type="primary"):
            st.session_state.pg_card_adding = True
            st.rerun()

    # Display cards
    if not cards:
        st.info("No guide cards yet. Add a card to document Python patterns for specific sections (e.g., Headworks, Primary, Aeration).")
    else:
        for i, card in enumerate(cards):
            cid = card.get('id', str(i))
            is_editing = st.session_state.pg_card_editing == cid

            with st.container():
                if is_editing:
                    with st.form(f"edit_pg_card_{cid}"):
                        st.markdown(f"**✏️ Edit: {card.get('title', 'Untitled')}**")
                        edit_title = st.text_input("Card Title", value=card.get('title', ''), key=f"et_{cid}")
                        edit_section = st.text_input("Target Section", value=card.get('section', ''), key=f"es_{cid}")
                        edit_libraries = st.text_area("Available Libraries:", value=card.get('libraries', ''), height=80, key=f"el_{cid}")
                        edit_variables = st.text_area("Available Variables:", value=card.get('variables', ''), height=120, key=f"ev_{cid}")
                        edit_example = st.text_area("Example Usage (Python code):", value=card.get('example_code', ''), height=150, key=f"ee_{cid}")
                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            if st.form_submit_button("💾 Save"):
                                card['title'] = edit_title.strip()
                                card['section'] = edit_section.strip()
                                card['libraries'] = edit_libraries.strip()
                                card['variables'] = edit_variables.strip()
                                card['example_code'] = edit_example.strip()
                                # Remove legacy 'content' if present
                                if 'content' in card:
                                    del card['content']
                                st.session_state.pg_card_editing = None
                                st.success("Card updated!")
                                st.rerun()
                        with col_e2:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state.pg_card_editing = None
                                st.rerun()
                else:
                    with st.expander(f"**{card.get('title', 'Untitled')}**" + (f" — {card.get('section')}" if card.get('section') else ""), expanded=False):
                        # Legacy cards: if only 'content' exists, show as generic content
                        if 'libraries' not in card and 'variables' not in card and 'example_code' not in card and card.get('content'):
                            st.markdown(card['content'])
                        else:
                            # Available Libraries
                            st.markdown("**Available Libraries:**")
                            libs = card.get('libraries', '')
                            if libs:
                                st.markdown(libs)
                            else:
                                st.caption("(None)")
                            st.markdown("")
                            # Available Variables
                            st.markdown("**Available Variables:**")
                            vars_text = card.get('variables', '')
                            if vars_text:
                                st.markdown(vars_text)
                            else:
                                st.caption("(None)")
                            st.markdown("")
                            # Example Usage with copyable code
                            st.markdown("**Example Usage:**")
                            example = card.get('example_code', '')
                            if example:
                                st.code(example, language="python")
                                st.caption("👆 Click the copy icon above the code block to copy the entire code")
                            else:
                                st.caption("(No example)")
                        st.divider()
                        col_v1, col_v2 = st.columns([1, 1])
                        with col_v1:
                            if st.button("✏️ Edit", key=f"edit_{cid}"):
                                st.session_state.pg_card_editing = cid
                                st.rerun()
                        with col_v2:
                            if st.button("🗑️ Delete", key=f"del_{cid}"):
                                cards[:] = [c for c in cards if c.get('id') != cid]
                                st.session_state.python_coding_guide_cards = cards
                                st.success("Card deleted!")
                                st.rerun()
