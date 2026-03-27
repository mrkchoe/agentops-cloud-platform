from app.models.entities import ConversationType, MessageProvider
from app.services.messaging_service import get_or_create_channel_binding


def test_get_or_create_channel_binding(db_session):
    binding, conv, created = get_or_create_channel_binding(
        db_session,
        workspace_id=1,
        provider=MessageProvider.TWILIO,
        external_user_address="+1000",
    )
    assert created is True
    assert conv.workspace_id == 1
    assert conv.type == ConversationType.DIRECT

    binding2, conv2, created2 = get_or_create_channel_binding(
        db_session,
        workspace_id=1,
        provider=MessageProvider.TWILIO,
        external_user_address="+1000",
    )
    assert created2 is False
    assert conv2.id == conv.id
    assert binding2.id == binding.id

