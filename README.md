# WWTP Design Portfolio

A Streamlit application for managing wastewater treatment plant (WWTP) design projects and calculations.

## Features

- **Project Management**: Create and switch between multiple WWTP design projects
- **Default Parameters**: Cached default design parameters for quick access
- **Multi-tab Interface**: Organized sections for Mass Balance, P&ID + Equipment List, Hydraulic Design, and Control Philosophy

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the Streamlit app:

```bash
streamlit run app.py
```

## Deployment on Streamlit Cloud

1. Push this repository to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Sign in with your GitHub account
4. Click "New app"
5. Select this repository
6. Set the main file path to `app.py`
7. Click "Deploy"

The app will be available at a public URL like: `https://your-app-name.streamlit.app`

## Requirements

- streamlit
- pandas
- numpy
- scipy
- plotly
