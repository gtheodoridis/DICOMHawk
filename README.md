# DICOMHawk

DICOMHawk is a powerful and efficient honeypot for DICOM servers, designed to attract and log unauthorized access attempts and interactions. Built using Flask and pynetdicom, DICOMHawk offers a streamlined web interface for monitoring and managing DICOM interactions in real-time.

## Features

- **DICOM Server Simulation**: Supports C-ECHO, C-FIND, and C-STORE operations to simulate a realistic DICOM server environment.
- **Logging**: Detailed logging of DICOM associations, DIMSE messages, and event-specific data to track and analyze potential attacks.
- **Web Interface**: A user-friendly web interface to view server status, active associations, and logs.
- **Custom Handlers**: Easily extendable to support additional DICOM services and custom logging or handling requirements.
