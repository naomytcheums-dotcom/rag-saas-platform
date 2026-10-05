"""P2C-6: known foreign media/transcript/frame IDs without S3 or processing."""

from unittest.mock import AsyncMock, Mock

from api.models.media import MediaAsset, MediaFrame, MediaStatus, MediaTranscript, MediaType
from test_document_idor import denied, make_tenants, snapshot


async def test_media_idor(client, db_session, monkeypatch):
    (owner, org_a, user_a), (attacker, org_b, user_b) = await make_tenants(
        client, db_session, monkeypatch, "media"
    )
    asset = MediaAsset(
        organization_id=org_a, uploaded_by=user_a, media_type=MediaType.video,
        status=MediaStatus.completed, filename="private-video.mp4",
        file_key="p2c/private-video.mp4", file_size=12, mime_type="video/mp4",
        description="private-video-description",
    )
    own = MediaAsset(
        organization_id=org_b, uploaded_by=user_b, media_type=MediaType.video,
        filename="own-video.mp4", file_key="p2c/own-video.mp4",
        file_size=12, mime_type="video/mp4",
    )
    db_session.add_all([asset, own])
    await db_session.flush()
    transcript = MediaTranscript(media_asset_id=asset.id, text="private-transcript")
    frame = MediaFrame(
        media_asset_id=asset.id, frame_index=0, timestamp_ms=0,
        file_key="p2c/private-frame.jpg", description="private-frame",
    )
    db_session.add_all([transcript, frame])
    await db_session.commit()
    asset_id, own_id, frame_id = asset.id, own.id, frame.id
    baseline = await snapshot(db_session, asset, own, transcript, frame)
    stream, delete, schedule, process = Mock(), Mock(), Mock(), AsyncMock()
    monkeypatch.setattr("api.routers.media.stream_document_file", stream)
    monkeypatch.setattr("api.services.media.delete_document_file", delete)
    monkeypatch.setattr("api.routers.media.schedule_media_processing", schedule)
    monkeypatch.setattr("api.services.media.process_media_asset", process)
    control = await client.get(f"/media/{asset_id}", headers=owner)
    assert control.status_code == 200, control.text
    control = await client.get(f"/media/{asset_id}/transcript", headers=owner)
    assert control.status_code == 200
    assert control.json()["text"] == "private-transcript"
    violations = []
    for suffix in (
        "", "/status", "/transcript", "/description", "/file", "/frames",
        f"/frames/{frame_id}/file",
    ):
        await denied(client, "GET", f"/media/{asset_id}{suffix}", attacker, violations)
    await denied(client, "GET", f"/organizations/{org_a}/media", attacker, violations)
    await denied(
        client, "GET", f"/media/{own_id}/frames/{frame_id}/file", attacker, violations
    )
    await denied(client, "POST", f"/media/{asset_id}/process", attacker, violations)
    await denied(client, "DELETE", f"/media/{asset_id}", attacker, violations)
    assert await snapshot(db_session, asset, own, transcript, frame) == baseline
    for boundary in (stream, delete, schedule, process):
        boundary.assert_not_called()
    assert not violations, "\n".join(violations)
