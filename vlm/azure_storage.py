#!/usr/bin/env python3
"""
OmniSight Azure Blob Storage Manager for Uploading Screenshot Artifacts & Manifests.
"""

import logging
import os
import pathlib
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.resolve()
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)


def get_azure_blob_service():
    """Initializes Azure BlobServiceClient if connection string or credentials exist in .env."""
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

    try:
        from azure.storage.blob import BlobServiceClient
        if conn_str:
            return BlobServiceClient.from_connection_string(conn_str)
        elif account_name and account_key:
            account_url = f"https://{account_name}.blob.core.windows.net"
            return BlobServiceClient(account_url=account_url, credential=account_key)
    except Exception as e:
        logger.warning(f"⚠️ Azure Blob Storage client notice: {e}")
    return None


def upload_artifact_to_azure(file_path: str, blob_prefix: str = "") -> Optional[str]:
    """
    Uploads a single file (screenshot, manifest.json) to Azure Blob Storage Container.
    Returns the public Azure Blob URL upon success, or None on fallback.
    """
    blob_service = get_azure_blob_service()
    if not blob_service:
        return None

    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "omnisight-artifacts")
    file_obj = pathlib.Path(file_path).resolve()

    if not file_obj.exists():
        return None

    blob_name = f"{blob_prefix}/{file_obj.name}".strip("/") if blob_prefix else file_obj.name

    try:
        container_client = blob_service.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container(public_access="blob")

        blob_client = container_client.get_blob_client(blob_name)
        with open(file_obj, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        blob_url = blob_client.url
        return blob_url
    except Exception as e:
        logger.error(f"⚠️ Failed to upload {file_obj.name} to Azure Blob: {e}")
        return None


def upload_run_folder_to_azure(run_dir: str) -> Dict[str, str]:
    """
    Uploads an entire screenshot run folder (manifest.json and images) to Azure Container.
    Returns a dictionary mapping local file names to public Azure Blob URLs.
    """
    run_path = pathlib.Path(run_dir).resolve()
    if not run_path.exists():
        return {}

    prefix_name = run_path.name
    uploaded_urls = {}

    for file_obj in run_path.iterdir():
        if file_obj.is_file():
            url = upload_artifact_to_azure(str(file_obj), blob_prefix=prefix_name)
            if url:
                uploaded_urls[file_obj.name] = url
                logger.info(f"☁️ [Azure Blob] Uploaded: {file_obj.name} -> {url}")

    return uploaded_urls
