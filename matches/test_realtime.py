from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase, override_settings

from config.asgi import application
from .realtime import PUBLIC_CONTENT_GROUP


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
)
class PublicUpdatesTests(SimpleTestCase):
    async def test_connected_client_receives_public_content_update(self):
        communicator = WebsocketCommunicator(
            application,
            "/ws/updates/",
            headers=[(b"origin", b"http://testserver")],
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await get_channel_layer().group_send(
            PUBLIC_CONTENT_GROUP,
            {"type": "content_update", "resource": "live_scores", "updated_at": "now"},
        )

        self.assertEqual(
            await communicator.receive_json_from(),
            {"resource": "live_scores", "updated_at": "now"},
        )
        await communicator.disconnect()