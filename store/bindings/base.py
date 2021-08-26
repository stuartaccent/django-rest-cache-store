import sys
from time import time

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.shortcuts import get_object_or_404
from rest_framework import status, exceptions
from rest_framework.response import Response

from store.models import StoreHistory


class AppStoreMetaclass(type):
    INSTANCES = dict()
    NOCACHE = sys.argv[1:2] == ['test']

    def __new__(mcs, name, bases, attrs):
        new_class = super().__new__(mcs, name, bases, attrs)
        if new_class.cache_key and new_class.cache_key in mcs.INSTANCES:
            raise Exception(f'instance already registered at {new_class.cache_key}')
        if new_class.cache_key:
            mcs.INSTANCES[new_class.cache_key] = new_class
        return new_class

    @classmethod
    def register_all(cls):
        for _, store in cls.INSTANCES.items():
            store.register()

    @classmethod
    def full_store(cls):
        data = {
            cache_key: store.data()
            for cache_key, store in cls.INSTANCES.items()
        }
        data['version'] = cls.get_version()
        return data

    @classmethod
    def actions(cls):
        return cls._actions

    @classmethod
    def get_instance(cls, cache_key):
        return cls.INSTANCES[cache_key]

    @classmethod
    def get_version(cls):
        return cache.get('version')

    @classmethod
    def set_version(cls):
        version = time()
        cache.set('version', version, None)
        return version

    @classmethod
    def save_to_history(cls, **kwargs):
        StoreHistory.objects.create(**kwargs)

    @classmethod
    def send_group_info(cls):
        channel_layer = get_channel_layer()
        data = {
            'type': 'store.binding',
            'version': cls.get_version(),
        }
        async_to_sync(channel_layer.group_send)('store_binding', data)


class BaseAppStore(metaclass=AppStoreMetaclass):
    cache_key = None
    model = None
    serializer = None

    @classmethod
    def cache_add_all(cls, data):
        cache.set(cls.cache_key, data, None)

    @classmethod
    def cache_get(cls, key):
        if cls.NOCACHE:
            return cls.get_serializer(instance=cls.get_queryset().get(pk=key)).data
        return cls.cache_get_all().get(key)

    @classmethod
    def cache_get_all(cls):
        if cls.NOCACHE:
            return {d['id']: d for d in cls.get_serializer(instance=cls.get_queryset(), many=True).data}
        return cache.get(cls.cache_key) or {}

    @classmethod
    def cache_rebuild(cls, id=None):
        version = cls.set_version()
        if id:
            cache_data = cls.cache_get_all()
            try:
                instance = cls.get_queryset().get(pk=id)
                state = 'U' if id in cache_data else 'C'
                cache_data[id] = cls.get_serializer(instance=instance).data
                cls.save_to_history(version=version, cache_key=cls.cache_key, item_id=id, state=state)
            except cls.model.DoesNotExist:
                cache_data.pop(id)
                cls.save_to_history(version=version, cache_key=cls.cache_key, item_id=id, state='D')
            cls.cache_add_all(cache_data)
        else:
            cls.cache_add_all(cls.get_initial_state())
            cls.save_to_history(version=version, cache_key=cls.cache_key, state='U')

    @classmethod
    def data(cls):
        return [v for _, v in cls.cache_get_all().items()]

    @classmethod
    def get_initial_state(cls):
        data = cls.get_serializer(instance=cls.get_queryset(), many=True).data
        return {item['id']: item for item in data}

    @classmethod
    def get_queryset(cls):
        return cls.model.objects.all()

    @classmethod
    def get_serializer(cls, **kwargs):
        return cls.serializer(**kwargs)

    @classmethod
    def post_delete_receiver(cls, instance, **kwargs):
        id = instance.pk

        def do():
            from store.tasks import trigger_cache_rebuild
            res = trigger_cache_rebuild(cls.cache_key, id)
            res()

        transaction.on_commit(lambda: do())

    @classmethod
    def post_save_receiver(cls, instance, created, **kwargs):
        def do():
            from store.tasks import trigger_cache_rebuild
            res = trigger_cache_rebuild(cls.cache_key, instance.pk)
            res()

        transaction.on_commit(lambda: do())

    @classmethod
    def register(cls):
        if cls.NOCACHE:
            return
        post_save.connect(cls.post_save_receiver, sender=cls.model)
        post_delete.connect(cls.post_delete_receiver, sender=cls.model)

    @classmethod
    @transaction.atomic
    def create(cls, request, *args, **kwargs):
        serializer = cls.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @classmethod
    @transaction.atomic
    def update(cls, request, pk, *args, **kwargs):
        qs = cls.get_queryset()
        instance = get_object_or_404(qs, pk=pk)
        serializer = cls.get_serializer(
            instance=instance,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        instance = get_object_or_404(qs, pk=pk)
        serializer = cls.get_serializer(
            instance=instance,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @classmethod
    @transaction.atomic
    def delete(cls, request, pk, *args, **kwargs):
        qs = cls.get_queryset()
        instance = get_object_or_404(qs, pk=pk)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NoCreateMixin:
    @classmethod
    def create(cls, request, *args, **kwargs):
        raise exceptions.MethodNotAllowed(method='post')


class NoDeleteMixin:
    @classmethod
    def delete(cls, request, pk, *args, **kwargs):
        raise exceptions.MethodNotAllowed(method='delete')


class NoUpdateMixin:
    @classmethod
    def update(cls, request, pk, *args, **kwargs):
        raise exceptions.MethodNotAllowed(method='put')


class ReadOnlyMixin(NoCreateMixin, NoDeleteMixin, NoUpdateMixin):
    pass
