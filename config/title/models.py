# Generic model imports
from django.db import models


class BaseModel(models.Model):
    """
    Abstraction layer to create metadata information
    for any django object within this API. Should not
    be used for any nested objects.
    """

    class Meta:
        abstract = True

    creation_date = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now_add=True)


class Title(BaseModel):
    title = models.CharField(max_length=50)
    image = models.ImageField(upload_to='photos/%Y/%m/%d')
    date = models.DateTimeField()
    readCount = models.IntegerField()
    body = models.TextField()
