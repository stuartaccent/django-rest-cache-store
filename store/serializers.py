from rest_framework import serializers

from store.models import StoreHistory


class StoreHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreHistory
        fields = '__all__'
