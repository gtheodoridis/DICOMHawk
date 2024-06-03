import logging
from flask import Flask, jsonify, send_from_directory
from pynetdicom import AE, evt, debug_logger, StoragePresentationContexts, VerificationPresentationContexts
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    CTImageStorage,
    MRImageStorage,
    Verification
)
from pydicom.dataset import Dataset
import threading
import os

# Set up logging
log_file_path = 'dicom_server.log'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(log_file_path),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

# Enable pynetdicom's debug logging
debug_logger()

# Handlers for different DICOM events
def handle_assoc(event):
    logger.info(f"Association requested from {event.assoc.requestor.address}:{event.assoc.requestor.port}")

def handle_release(event):
    logger.info(f"Association released from {event.assoc.requestor.address}:{event.assoc.requestor.port}")

def handle_find(event):
    logger.info(f"C-FIND request received: {event.identifier}")
    ds = Dataset()
    ds.PatientName = "Doe^John"
    ds.PatientID = "12345"
    ds.StudyDate = "20210101"
    ds.QueryRetrieveLevel = "STUDY"
    yield 0xFF00, ds

def handle_store(event):
    logger.info(f"C-STORE request received: {event.dataset}")
    return 0x0000

def handle_echo(event):
    logger.info(f"C-ECHO request received")
    return 0x0000

handlers = [
    (evt.EVT_ACSE_RECV, handle_assoc),
    (evt.EVT_RELEASED, handle_release),
    (evt.EVT_C_FIND, handle_find),
    (evt.EVT_C_STORE, handle_store),
    (evt.EVT_C_ECHO, handle_echo),
]

# Initialize the Application Entity
ae = AE()

# Add supported presentation contexts
ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
ae.add_supported_context(CTImageStorage)
ae.add_supported_context(MRImageStorage)
ae.add_supported_context(Verification)

# Add all storage presentation contexts
for context in StoragePresentationContexts + VerificationPresentationContexts:
    ae.add_supported_context(context.abstract_syntax)

# Function to start the DICOM server
def start_dicom_server():
    ae.start_server(('0.0.0.0', 11112), evt_handlers=handlers)

# Start the DICOM server in a separate thread
dicom_thread = threading.Thread(target=start_dicom_server)
dicom_thread.daemon = True
dicom_thread.start()

# Flask web server for monitoring
app = Flask(__name__)

@app.route('/')
def home():
    return send_from_directory('.', 'status.html')

@app.route('/logs')
def logs():
    return send_from_directory('.', 'logs.html')

@app.route('/status')
def status():
    return jsonify({"status": "running", "associations": len(ae.active_associations)})

@app.route('/simplified_logs.log')
def simplified_logs():
    try:
        if not os.path.exists(log_file_path):
            return jsonify({"error": "Log file does not exist"}), 404
        with open(log_file_path, 'r') as f:
            log_content = f.read()
        return log_content
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}")
    return jsonify({"error": "Internal Server Error"}), 500

if __name__ == "__main__":
    app.run(port=5000)
