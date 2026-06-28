import json
from channels.generic.websocket import AsyncWebsocketConsumer


class DriverLocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Reject unauthenticated connections
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.driver_id = self.scope['url_route']['kwargs']['driver_id']
        self.group_name = f'driver_{self.driver_id}'

        # Only the driver whose ID matches may broadcast; riders may listen
        self.is_broadcaster = str(user.pk) == str(self.driver_id) and user.role == 'driver'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Only the matching driver may push location updates
        if not getattr(self, 'is_broadcaster', False):
            return
        data = json.loads(text_data)
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'location_update', 'data': data}
        )

    async def location_update(self, event):
        await self.send(text_data=json.dumps(event['data']))


class TripConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.trip_id = self.scope['url_route']['kwargs']['trip_id']
        self.group_name = f'trip_{self.trip_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass

    async def trip_update(self, event):
        await self.send(text_data=json.dumps(event['data']))
