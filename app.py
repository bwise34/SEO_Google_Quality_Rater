import streamlit as st
import openai
from openai import OpenAI
import os
# import pyperclip
from st_copy_to_clipboard import st_copy_to_clipboard

# Set layout to wide
st.set_page_config(layout="wide")
# Set OpenAI key from Streamlit Cloud secret variable
api_key = os.environ["API_KEY"]


# Helper function to truncate text
def truncate_text(text, max_length=500):
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

# Read Google Quality Rater Guidelines Documentation from a file
with open('google_QRG.txt', 'r') as file:
    google_quality_rater_documentation = file.read()

# Defining OpenAI request settings
st.write("### OpenAI Model Settings \n I would say stay around the **0.4 to 0.9** range \n - The higher the number the more creative the model will be \n - The lower the setting the more deterministic the model will be")
# Temperature scale for setting the temperature setting to the OpenAI request
temp = st.slider("Set the temperature for the OpenAI request", min_value=0.0, max_value=1.0, value=0.6, step=0.1)


# Streamlit UI
st.title("Instruction Extraction Tool")
# Title and evaluation topics
st.write(f"## Evalualtion Topic")
evaluation_topics = st.text_area(
    "Enter Topic or feature to evaluate",
    "Input Evaluation Topic/Feature",
    height=75
)



# Use text area input for evaluation topic
selected_topic = evaluation_topics

# Display the selected topic
st.write(f"## Selected Evaluation Topic: \n - {selected_topic}")

st.write(f"## System Role")
# Prompt input for system role
role = st.text_area("Enter your system role for the GPT model. \n\n **Does NOT have to change but wanted to provide the ability to try different system roles.**",
                        "You are a helpful assistant.", 
                        height=300)

st.write(f"## Prompt")
st.write("Within the prompt to use stored variables such as the Google QRG Documentation or the Evaluation Topic, please provide them in the text area in the following example format: \n - {google_quality_rater_documentation} \n - {selected_topic} \n - {name of variable} ")
# Prompt input for user prompt
prompt = st.text_area("Enter your prompt for the GPT model", height=300)

# Initialize or load stored outputs
if 'outputs' not in st.session_state:
    st.session_state.outputs = []

# Display defined variables in a table format at the top left corner
with st.sidebar:
    st.write("### Defined Variables")
    st.markdown(
        """
        <style>
        .variable-table {
            width: 100%;
            border-collapse: collapse;
        }
        .variable-table td, .variable-table th {
            border: 1px solid #ddd;
            padding: 8px;
        }
        .variable-table th {
            padding-top: 12px;
            padding-bottom: 12px;
            text-align: left;
            background-color: #000;
            color: #fff;
        }
        .wrap-text {
            word-wrap: break-word;
            max-width: 125px; /* Set a fixed width for the variable column */
        }
        </style>
        """, unsafe_allow_html=True
    )
    st.markdown(
        f"""
        <table class="variable-table">
            <tr>
                <th>Variable</th>
                <th>Value</th>
            </tr>
            <tr>
                <td class="wrap-text">google_quality_rater_documentation</td>
                <td>{truncate_text(google_quality_rater_documentation, 100)}</td>
            </tr>
            <tr>
                <td class="wrap-text">selected_topic</td>
                <td>{selected_topic}</td>
            </tr>
        </table>
        """, unsafe_allow_html=True
    )

# Button to trigger extraction
if st.button("## Extract Instructions"):
    # Define a dictionary of variables
    variables = {
        "google_quality_rater_documentation": google_quality_rater_documentation,
        "selected_topic": selected_topic
    }

    # Replace placeholders with variable values in the user prompt
    formatted_prompt = prompt.format(**variables)

    # Call the GPT model
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": role},
            {"role": "user", "content": formatted_prompt}
        ],
        temperature=temp,
        max_tokens=4000
    )

    # Display the extracted instructions
    instructions = response.choices[0].message.content.strip('\n').strip()
    run_number = len(st.session_state.outputs) + 1
    truncated_prompt = truncate_text(formatted_prompt)
    st.session_state.outputs.append({"run_number": run_number, "prompt": truncated_prompt, "instructions": instructions})

    # Display the extracted instructions in a table format
    st.subheader("Extracted Instructions")


# Dropdown to select from stored outputs
selected_output = None
if st.session_state.outputs:
    selected_output = st.selectbox(
        "Select an output to compare",
        st.session_state.outputs,
        format_func=lambda x: f"Run {x['run_number']}: {truncate_text(x['instructions'], 30)}"  # Show run number and beginning of the output for identification
    )

# Display the current and previous outputs side by side
if st.session_state.outputs:
    current_output = st.session_state.outputs[-1]  # Most recent output

    col1, col2 = st.columns(2)

    with col1:
        st.write("## Previous Output")
        if selected_output:
            st.write(f"### Run {selected_output['run_number']}")
            # Add button to copy the extracted instructions to clipboard
            st.write("Copy Button: ")
            st_copy_to_clipboard(selected_output['instructions'], key=f"copy_button_previous_{selected_output['run_number']}")
            st.write(selected_output['instructions'])
            if st.button(f"Show Prompt for Run {selected_output['run_number']}", key=f"prompt_button_previous_{selected_output['run_number']}"):
                st.write(f"### Prompt for Run {selected_output['run_number']}")
                st.write(selected_output['prompt'])
    
    with col2:
        st.write("## Current Output")
        st.write(f"### Run {current_output['run_number']}")
        # Add button to copy the extracted instructions to clipboard
        st.write("Copy Button: ")
        st_copy_to_clipboard(current_output['instructions'], key=f"copy_button_current_{current_output['run_number']}")
        st.write(current_output['instructions'])
        if st.button(f"Show Prompt for Run {current_output['run_number']}", key=f"prompt_button_current_{current_output['run_number']}"):
            st.write(f"### Prompt for Run {current_output['run_number']}")
            st.write(current_output['prompt'])

# Run the Streamlit app using `streamlit run app.py`
