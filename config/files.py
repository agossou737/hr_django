"""Stockage privé et validation des fichiers téléversés."""
import os

from django import forms
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404
from django.utils.deconstruct import deconstructible

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}


@deconstructible
class PrivateStorage(FileSystemStorage):
    """Fichiers hors de MEDIA_ROOT : aucune URL publique n'existe pour eux."""

    def __init__(self):
        super().__init__(location=str(settings.PRIVATE_ROOT), base_url=None)

    def url(self, name):
        raise ValueError("Les fichiers privés n'ont pas d'URL publique : utilisez la vue de téléchargement.")


def private_storage():
    return PrivateStorage()


def validate_upload(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise forms.ValidationError("Format non autorisé (PDF, Word, JPG ou PNG uniquement).")
    if file.size > settings.UPLOAD_MAX_MB * 1024 * 1024:
        raise forms.ValidationError(f"Fichier trop volumineux (max {settings.UPLOAD_MAX_MB} Mo).")
    return file


def download(field_file, filename):
    """Réponse de téléchargement d'un fichier privé (le contrôle d'accès est fait par l'appelant)."""
    if not field_file or not field_file.storage.exists(field_file.name):
        raise Http404
    return FileResponse(field_file.open("rb"), as_attachment=True, filename=filename)
