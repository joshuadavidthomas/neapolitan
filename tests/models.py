import uuid
from django.db import models


class Bookmark(models.Model):
    url = models.URLField(unique=True)
    title = models.CharField(max_length=255)
    note = models.TextField(blank=True)
    favourite = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class NamedCollection(models.Model):
    """For testing UUID lookup"""

    name = models.CharField(max_length=25, unique=True)
    code = models.UUIDField(unique=True, default=uuid.uuid4)


class BookmarkTag(models.Model):
    """For testing foreign key display"""

    bookmark = models.ForeignKey(
        Bookmark, on_delete=models.CASCADE, related_name="tags"
    )
    tag = models.CharField(max_length=50)

    def __str__(self):
        return self.tag
