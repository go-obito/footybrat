from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        username = attrs["username"]
        email = attrs["email"].strip().lower()
        if User.objects.filter(username=username).exists() or User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Unable to create account with these details.")
        validate_password(attrs["password"], user=User(username=username, email=email))
        attrs["email"] = email
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")
