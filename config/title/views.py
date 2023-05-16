from django.shortcuts import render

from rest_framework import mixins, views, generics, viewsets, response, status, permissions
from rest_framework.views import APIView

from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser, JSONParser
from rest_framework.generics import RetrieveUpdateDestroyAPIView, ListCreateAPIView, get_object_or_404
from rest_framework.response import Response
from .models import Title, IOSFiles
from .serializers import TitleSerializer, IOSFilesSerializer
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, filters


def content(data):
    return {'data': data, 'statusCode': status.HTTP_201_CREATED}


def nonContent():
    return {'statusCode': status.HTTP_204_NO_CONTENT}


class TitleView(ListCreateAPIView):
    serializer_class = TitleSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend)

    ordering = ['pk']

    def get_queryset(self):
        return Title.objects.all()

    def get(self, request, *args, **kwargs):
        self.serializer_class = TitleSerializer
        return self.list(request, *args, **kwargs)

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=self.request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TitleUpdateView(RetrieveUpdateDestroyAPIView):
    serializer_class = TitleSerializer

    def get_queryset(self):
        return Title.objects.all()

    def get(self, request, pk):
        instance = get_object_or_404(Title, id=pk)
        serializer = self.serializer_class(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        instance = get_object_or_404(Title, id=pk)
        serializer = self.serializer_class(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=self.request.user)
        return Response(serializer.data, status.HTTP_202_ACCEPTED)

    def delete(self, request, pk):
        instance = get_object_or_404(Title, id=pk)
        instance.delete()
        return Response(nonContent(), status.HTTP_204_NO_CONTENT)


class IOSFileView(ListCreateAPIView):
    serializer_class = IOSFilesSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend)

    ordering = ['pk']

    def get_queryset(self):
        return IOSFiles.objects.all()

    def get(self, request, *args, **kwargs):
        self.serializer_class = IOSFilesSerializer
        return self.list(request, *args, **kwargs)

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=self.request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class IOSFileUpdateView(RetrieveUpdateDestroyAPIView):
    serializer_class = IOSFilesSerializer

    def get_queryset(self):
        return IO.objects.all()

    def get(self, request, pk):
        instance = get_object_or_404(Title, id=pk)
        serializer = self.serializer_class(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        instance = get_object_or_404(Title, id=pk)
        serializer = self.serializer_class(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=self.request.user)
        return Response(serializer.data, status.HTTP_202_ACCEPTED)

    def delete(self, request, pk):
        instance = get_object_or_404(Title, id=pk)
        instance.delete()
        return Response(nonContent(), status.HTTP_204_NO_CONTENT)
