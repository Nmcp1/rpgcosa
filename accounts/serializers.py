from rest_framework import serializers
from django.contrib.auth.models import User
from .models import InvitationCode

class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    invitation_code = serializers.CharField()

    def validate(self, attrs):
        code_str = attrs["invitation_code"].strip().upper()
        try:
            code = InvitationCode.objects.get(code=code_str)
        except InvitationCode.DoesNotExist:
            raise serializers.ValidationError({"invitation_code": "Código inválido"})

        if not code.can_be_used():
            raise serializers.ValidationError({"invitation_code": "Código agotado o inactivo"})

        attrs["invitation_obj"] = code
        return attrs

    def create(self, validated_data):
        code = validated_data.pop("invitation_obj")
        username = validated_data["username"]
        password = validated_data["password"]

        user = User.objects.create_user(username=username, password=password)
        code.register_use()
        return user
