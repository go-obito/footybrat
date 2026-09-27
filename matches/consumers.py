from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .realtime import PUBLIC_CONTENT_GROUP


class PublicUpdatesConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(PUBLIC_CONTENT_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(PUBLIC_CONTENT_GROUP, self.channel_name)

    async def content_update(self, event):
        await self.send_json(
            {"resource": event["resource"], "updated_at": event["updated_at"]}
        )