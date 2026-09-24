from rest_framework import serializers

from .models import Subscriber


class SubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()

    def save(self, **kwargs):
        email = self.validated_data["email"]
        subscriber, _ = Subscriber.objects.update_or_create(
            email=email,
            defaults={"is_active": True},
        )
        return subscriber
