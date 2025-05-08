import subprocess
import streamlit as st
import sys
import time
import os
import re

if 'process' not in st.session_state:
    st.session_state.process = None
if 'running' not in st.session_state:
    st.session_state.running = False
if 'stop_requested' not in st.session_state:
    st.session_state.stop_requested = False
if 'accumulated_output' not in st.session_state:
    st.session_state.accumulated_output = ""
if 'return_code' not in st.session_state:
    st.session_state.return_code = None
if 'process_error' not in st.session_state:
    st.session_state.process_error = None


if st.session_state.running and st.session_state.stop_requested:
    st.warning("Attempting to stop the process...")
    if st.session_state.process:
        try:
            st.session_state.process.terminate()
            st.info("Stop signal sent.")
        except Exception as e:
            st.error(f"Error sending stop signal: {e}")
        finally:
            st.session_state.running = False
            st.session_state.stop_requested = False
            st.session_state.process = None

st.title("Credit Card Comparison Report Generator")

start_button_disabled = st.session_state.running
if st.button("Start API Process", key="start_process_button", disabled=start_button_disabled):
    st.write("Initiating the comparison report generation process...")
    st.session_state.running = True
    st.session_state.stop_requested = False
    st.session_state.accumulated_output = ""
    st.session_state.return_code = None
    st.session_state.process_error = None
    st.session_state.process = None
    st.rerun()

if st.session_state.running:
    if st.button("Stop Process", key="stop_process_button"):
        st.session_state.stop_requested = True
        st.info("Stop requested. Waiting for process to terminate...")
        st.rerun()

if st.session_state.running:
    with st.status("Running external process...", expanded=True) as status:
        if st.session_state.running:
            log_area = st.empty()

            try:
                if st.session_state.process is None:
                    my_env = os.environ.copy()
                    my_env["PYTHONIOENCODING"] = "utf-8"

                    process = subprocess.Popen(
                        [sys.executable, "main1.py"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        bufsize=1,
                        env=my_env
                    )
                    st.session_state.process = process
                else:
                     process = st.session_state.process

                while st.session_state.running and process.poll() is None:
                     line = process.stdout.readline()
                     if not line:
                         if process.poll() is not None:
                              break
                         time.sleep(0.01)
                         continue

                     st.session_state.accumulated_output += line
                     log_area.code(st.session_state.accumulated_output, language='log')

                try:
                    st.session_state.return_code = process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    st.warning("Process is taking longer than expected to finish after loop exited.")
                    st.session_state.return_code = -999

            except FileNotFoundError:
                error_msg = "Error: Could not find the Python executable or 'main1.py'."
                st.session_state.process_error = error_msg
                status.update(label=error_msg, state="error")
                st.error(error_msg + " Ensure Python is in your PATH and 'main1.py' is in the same directory as your app.")
            except Exception as e:
                error_msg = f"An unexpected error occurred during process execution: {e}"
                st.session_state.process_error = error_msg
                status.update(label=error_msg, state="error")
                st.error(error_msg)

            finally:
                st.session_state.running = False
                st.session_state.process = None
                st.rerun()

        if st.session_state.return_code is not None:
             if st.session_state.return_code == 0:
                 status.update(label="Process finished successfully!", state="complete")
             elif st.session_state.return_code < 0:
                 status.update(label="Process stopped by user.", state="warning")
             else:
                 status.update(label=f"Process failed with exit code {st.session_state.return_code}.", state="error")
        elif st.session_state.process_error:
             status.update(label="Process encountered an error.", state="error")


if st.session_state.return_code == 0 and not st.session_state.running:

    st.success("Report generation completed successfully.")
    st.subheader("Summary from Process Log")

    col1, col2 = st.columns(2)

    with col1:
        st.write("#### Details")
        request_id_match = re.search(r"Request ID: (\w+)", st.session_state.accumulated_output)
        if request_id_match:
            st.info(f"**Request ID:** `{request_id_match.group(1)}`")
        else:
             st.info("Could not find Request ID in logs.")

        report_title_match = re.search(r"Report Title: (.*)", st.session_state.accumulated_output)
        if report_title_match:
            st.info(f"**Report Title:** {report_title_match.group(1)}")
        else:
             st.info("Could not find Report Title in logs.")


    with col2:
        st.write("#### Output Files")
        pdf_path_match = re.search(r"PDF generated successfully: (.+\.pdf)", st.session_state.accumulated_output)
        extracted_pdf_path = None
        if pdf_path_match:
            extracted_pdf_path = pdf_path_match.group(1)
            st.info(f"**Generated PDF:** `{extracted_pdf_path}`")

            if os.path.exists(extracted_pdf_path):
                try:
                    with open(extracted_pdf_path, "rb") as file:
                        st.download_button(
                            label="Download Report PDF",
                            data=file,
                            file_name=os.path.basename(extracted_pdf_path),
                            mime="application/pdf"
                        )
                except Exception as e:
                    st.warning(f"Could not create download button for {extracted_pdf_path}: {e}")
            elif extracted_pdf_path:
                st.warning(f"Local file not found at extracted path: `{extracted_pdf_path}`")
        else:
             st.info("Could not find PDF file path in logs.")

        gcs_url_match = re.search(r"Public URL: (https?://\S+)", st.session_state.accumulated_output)
        if gcs_url_match:
            extracted_gcs_url = gcs_url_match.group(1)
            st.info(f"**Cloud Storage URL:** [Link]({extracted_gcs_url})")
        else:
             st.info("Could not find GCS Public URL in logs.")

    metrics_start_pattern = r"=+ Overall Total Usage: =+"
    metrics_end_pattern = r"={70,}"

    metrics_start_match = re.search(metrics_start_pattern, st.session_state.accumulated_output)

    if metrics_start_match:
        metrics_block_start_index = metrics_start_match.start()
        metrics_end_match = re.search(metrics_end_pattern, st.session_state.accumulated_output[metrics_block_start_index:])

        metrics_block = ""
        if metrics_end_match:
            metrics_block_end_index = metrics_block_start_index + metrics_end_match.end()
            metrics_block = st.session_state.accumulated_output[metrics_block_start_index:metrics_block_end_index].strip()
        else:
            metrics_block = st.session_state.accumulated_output[metrics_block_start_index:].strip()
            st.warning("Could not find the end marker for the token usage summary in logs.")

        if metrics_block:
            st.subheader("Token Usage Summary")
            input_tokens_match = re.search(r"Total Input Tokens: ([\d,]+)", metrics_block)
            output_tokens_match = re.search(r"Total Output Tokens: ([\d,]+)", metrics_block)
            total_tokens_match = re.search(r"Total All Tokens: ([\d,]+)", metrics_block)
            total_cost_match = re.search(r"Total Cost: \$([\d\.]+)", metrics_block)

            metric_cols = st.columns(4)
            if input_tokens_match:
                metric_cols[0].metric("Input Tokens", input_tokens_match.group(1))
            if output_tokens_match:
                 metric_cols[1].metric("Output Tokens", output_tokens_match.group(1))
            if total_tokens_match:
                 metric_cols[2].metric("Total Tokens", total_tokens_match.group(1))
            if total_cost_match:
                 metric_cols[3].metric("Total Cost", f"${float(total_cost_match.group(1)):.6f}")

        else:
            st.warning("Token usage summary block was found but appears empty.")

elif st.session_state.return_code is not None and st.session_state.return_code != 0 and not st.session_state.running:
     if st.session_state.return_code < 0:
          st.warning("Process was stopped by user.")
     else:
        st.error(f"Process failed with exit code {st.session_state.return_code}.")
        if st.session_state.process_error:
            st.error(f"Error details: {st.session_state.process_error}")

if not st.session_state.running and st.session_state.accumulated_output:
     with st.expander("Show Full Process Log"):
          st.code(st.session_state.accumulated_output, language='log')