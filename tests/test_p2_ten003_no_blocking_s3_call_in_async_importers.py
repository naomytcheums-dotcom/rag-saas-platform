"""TEN-003 (rest): every async importer (batch upload, URL, GitHub, Drive, Docs, Notion, Confluence, OneDrive, ZIP) must hand the synchronous boto3
write to a worker thread. A direct `upload_document_file(...)` call from an `async def` would freeze the event loop for the whole S3 round trip."""

import ast
import pathlib

SOURCE = pathlib.Path(__file__).resolve().parent.parent / "api" / "security" / "documents.py"


def _direct_calls_in_async_functions():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    offenders = []
    for function in [node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)]:
        for call in [node for node in ast.walk(function) if isinstance(node, ast.Call)]:
            if isinstance(call.func, ast.Name) and call.func.id == "upload_document_file":
                offenders.append((function.name, call.lineno))
    return offenders


def test_no_async_function_calls_the_blocking_s3_upload_directly():
    assert _direct_calls_in_async_functions() == []


def test_the_nine_importers_use_to_thread():
    text = SOURCE.read_text(encoding="utf-8")
    assert text.count("asyncio.to_thread(upload_document_file") + text.count("asyncio.to_thread(\n                upload_document_file") >= 10
