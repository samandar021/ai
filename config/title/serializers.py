from rest_framework import serializers

from .models import Title, IOSFiles


class TitleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Title
        fields = "__all__"


class IOSFilesSerializer(serializers.ModelSerializer):
    # files = serializers.ReadOnlyField()

    class Meta:
        model = IOSFiles
        fields = "__all__"
