import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask, jsonify, render_template, send_from_directory
from pynetdicom import AE, evt, debug_logger, StoragePresentationContexts, VerificationPresentationContexts, QueryRetrievePresentationContexts
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    CTImageStorage,
    MRImageStorage,
    Verification
)
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian, PYDICOM_IMPLEMENTATION_UID
import pydicom
import threading
import os
from datetime import datetime
import json
import time

# Set up logging
log_file_path = 'logs/dicom_server.log'
simplified_log_file_path = 'simplified_logs/dicom_simplified.log'
exception_log_file_path = 'logs/exception.log'

os.makedirs('logs', exist_ok=True)
os.makedirs('simplified_logs', exist_ok=True)

# Detailed logger
handler = TimedRotatingFileHandler(log_file_path, when="midnight", interval=1)
handler.suffix = "%Y%m%d"
detailed_logger = logging.getLogger('detailed_logger')
detailed_logger.setLevel(logging.INFO)
detailed_logger.addHandler(handler)
detailed_logger.addHandler(logging.StreamHandler())

# Simplified logger
simplified_handler = TimedRotatingFileHandler(simplified_log_file_path, when="midnight", interval=1)
simplified_handler.suffix = "%Y%m%d"
simplified_logger = logging.getLogger('simplified_logger')
simplified_logger.setLevel(logging.INFO)
simplified_logger.addHandler(simplified_handler)
simplified_logger.addHandler(logging.StreamHandler())

# Exception logger
exception_handler = TimedRotatingFileHandler(exception_log_file_path, when="midnight", interval=1)
exception_handler.suffix = "%Y%m%d"
exception_logger = logging.getLogger('exception_logger')
exception_logger.setLevel(logging.ERROR)
exception_logger.addHandler(exception_handler)
exception_logger.addHandler(logging.StreamHandler())

# Function to log valid JSON messages
def log_simplified_message(message):
    try:
        json_message = json.dumps(message)
        simplified_logger.info(json_message)
    except (TypeError, ValueError) as e:
        exception_logger.error(f"Failed to log simplified message: {message} - {e}")

# Enable pynetdicom's debug logging
debug_logger()

# Function to generate fake DICOM files
def create_fake_dicom_files(directory, num_files=5):
    os.makedirs(directory, exist_ok=True)
    for i in range(num_files):
        filename = os.path.join(directory, f"test_file{i+1}.dcm")
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = CTImageStorage
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID

        ds = FileDataset(filename, {}, file_meta=file_meta, preamble=b"\0" * 128)
        ds.PatientName = f"Test^Patient{i+1}"
        ds.PatientID = f"{i+1}"
        ds.StudyInstanceUID = generate_uid()
        ds.SeriesInstanceUID = generate_uid()
        ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
        ds.Modality = "CT"
        ds.StudyDate = datetime.now().strftime("%Y%m%d")
        ds.StudyTime = datetime.now().strftime("%H%M%S")
        ds.Rows = 512
        ds.Columns = 512
        ds.BitsAllocated = 16
        ds.BitsStored = 12
        ds.HighBit = 11
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.PixelData = b'\x00' * (ds.Rows * ds.Columns * 2)

        ds.is_little_endian = True
        ds.is_implicit_VR = False

        pydicom.dcmwrite(filename, ds)
        detailed_logger.info(f"Created fake DICOM file: {filename}")
        log_simplified_message({
            "ID": str(int(time.time() * 1000000)),
            "event": "Created fake DICOM file",
            "file": filename,
            "timestamp": datetime.now().isoformat()
        })

# Function to scan and load DICOM files
def load_dicom_files(directory):
    dicom_files = {}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.dcm'):
                path = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(path)
                    dicom_files[path] = ds
                except Exception as e:
                    detailed_logger.error(f"Failed to read DICOM file {path}: {e}")
                    log_simplified_message({
                        "ID": str(int(time.time() * 1000000)),
                        "event": "Failed to read DICOM file",
                        "file": path,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
    return dicom_files

dicom_directory = 'dicom_files'
create_fake_dicom_files(dicom_directory)
dicom_datasets = load_dicom_files(dicom_directory)

def handle_assoc(event):
    assoc_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"Association requested from {event.assoc.requestor.address}:{event.assoc.requestor.port}")
    
    version = event.assoc.requestor.implementation_version_name if event.assoc.requestor.implementation_version_name else "N/A"
    
    log_simplified_message({
        "ID": assoc_id,
        "event": "Association requested",
        "IP": event.assoc.requestor.address,
        "Port": event.assoc.requestor.port,
        "level": "warning",
        "msg": "Connection from",
        "timestamp": datetime.now().isoformat()
    })
    log_simplified_message({
        "ID": assoc_id,
        "Version": version,
        "level": "info",
        "msg": "Client",
        "timestamp": datetime.now().isoformat()
    })

def handle_release(event):
    release_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"Association released from {event.assoc.requestor.address}:{event.assoc.requestor.port}")
    log_simplified_message({
        "ID": release_id,
        "event": "Association released",
        "IP": event.assoc.requestor.address,
        "Port": event.assoc.requestor.port,
        "Status": "Finished",
        "level": "warning",
        "msg": "Connection",
        "timestamp": datetime.now().isoformat()
    })

def handle_find(event):
    find_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"C-FIND request received: {event.identifier}")
    
    # Log the C-FIND Search term and type
    for elem in event.identifier:
        if elem.VR == 'PN' and elem.keyword == 'PatientName':
            term = str(elem.value)
            log_simplified_message({
                "ID": find_id,
                "Term": term,
                "Type": "PatientName",
                "level": "info",
                "msg": "C-FIND Search",
                "timestamp": datetime.now().isoformat()
            })
            break

    log_simplified_message({
        "ID": find_id,
        "event": "C-FIND request received",
        "Command": "C-FIND",
        "identifier": str(event.identifier),
        "level": "info",
        "msg": "Received",
        "timestamp": datetime.now().isoformat()
    })

    # Create a response dataset and log the number of matches
    matches = 1  # For simplicity, we are assuming 1 match in this example
    log_simplified_message({
        "ID": find_id,
        "Matches": matches,
        "level": "warning",
        "msg": "C-FIND Search result",
        "timestamp": datetime.now().isoformat()
    })
    
    ds = Dataset()
    ds.PatientName = "Doe^John"
    ds.PatientID = "12345"
    ds.StudyDate = "20210101"
    ds.QueryRetrieveLevel = "STUDY"
    yield 0xFF00, ds

def handle_store(event):
    store_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"C-STORE request received: {event.dataset}")
    log_simplified_message({
        "ID": store_id,
        "event": "C-STORE request received",
        "Command": "C-STORE",
        "dataset": str(event.dataset),
        "level": "info",
        "msg": "Received",
        "timestamp": datetime.now().isoformat()
    })
    return 0x0000

def handle_echo(event):
    echo_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"C-ECHO request received")
    log_simplified_message({
        "ID": echo_id,
        "event": "C-ECHO request received",
        "Command": "C-ECHO",
        "level": "info",
        "msg": "Received",
        "timestamp": datetime.now().isoformat()
    })
    return 0x0000

def handle_move(event):
    move_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"C-MOVE request received: {event.identifier}")
    log_simplified_message({
        "ID": move_id,
        "event": "C-MOVE request received",
        "Command": "C-MOVE",
        "identifier": str(event.identifier),
        "level": "info",
        "msg": "Received",
        "timestamp": datetime.now().isoformat()
    })
    ds = Dataset()
    ds.SOPInstanceUID = generate_uid()
    ds.PatientName = "Doe^John"
    ds.PatientID = "12345"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPClassUID = CTImageStorage
    yield 1, ds

def handle_get(event):
    get_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"C-GET request received: {event.identifier}")
    log_simplified_message({
        "ID": get_id,
        "event": "C-GET request received",
        "Command": "C-GET",
        "identifier": str(event.identifier),
        "level": "info",
        "msg": "Received",
        "timestamp": datetime.now().isoformat()
    })
    remaining_subops = len(dicom_datasets)
    for path, ds in dicom_datasets.items():
        yield remaining_subops, ds
        remaining_subops -= 1
    yield 0

handlers = [
    (evt.EVT_ACSE_RECV, handle_assoc),
    (evt.EVT_RELEASED, handle_release),
    (evt.EVT_C_FIND, handle_find),
    (evt.EVT_C_STORE, handle_store),
    (evt.EVT_C_ECHO, handle_echo),
    (evt.EVT_C_MOVE, handle_move),
    (evt.EVT_C_GET, handle_get),
]

ae = AE()
ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
ae.add_supported_context(CTImageStorage)
ae.add_supported_context(MRImageStorage)
ae.add_supported_context(Verification)

for context in StoragePresentationContexts + VerificationPresentationContexts + QueryRetrievePresentationContexts:
    ae.add_supported_context(context.abstract_syntax)

def start_dicom_server():
    ae.start_server(('0.0.0.0', 11112), evt_handlers=handlers)

dicom_thread = threading.Thread(target=start_dicom_server)
dicom_thread.daemon = True
dicom_thread.start()

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('status.html')

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/status')
def status():
    return jsonify({"status": "running", "associations": len(ae.active_associations)})

@app.route('/logs/all')
def all_logs():
    try:
        if not os.path.exists(log_file_path):
            return jsonify({"error": "Log file does not exist"}), 404
        with open(log_file_path, 'r') as f:
            log_content = f.read()
        return log_content
    except Exception as e:
        exception_logger.error(f"Error reading log file: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/logs/simplified')
def simplified_logs():
    try:
        if not os.path.exists(simplified_log_file_path):
            return jsonify({"error": "Log file does not exist"}), 404
        log_entries = []
        with open(simplified_log_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        log_entries.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        exception_logger.error(f"Invalid JSON in log file: {line} - {e}")
                        continue
        return jsonify(log_entries)
    except Exception as e:
        exception_logger.error(f"Error reading simplified log file: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/logs/simplified_page')
def simplified_logs_page():
    return render_template('simplified_logs.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

@app.errorhandler(Exception)
def handle_exception(e):
    exception_logger.error(f"Unhandled exception: {e}")
    return jsonify({"error": "Internal Server Error"}), 500

if __name__ == "__main__":
    app.run(port=5000)
