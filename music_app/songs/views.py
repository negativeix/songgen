from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from .models import Song, Library, User, Folder


# ======================
# SONG CRUD
# ======================
def song_list(request):
    songs = list(Song.objects.values())
    return JsonResponse(songs, safe=False)


@csrf_exempt
def song_create(request):
    if request.method == "POST":
        data = json.loads(request.body)

        library = Library.objects.first()
        if library is None:
            return JsonResponse({"error": "No library found"}, status=400)

        song = Song.objects.create(
            title=data.get("title"),
            artist=data.get("artist"),
            duration=data.get("duration"),
            genre=data.get("genre"),
            library=library
        )

        return JsonResponse({"message": "Song created", "id": str(song.songId)})


@csrf_exempt
def song_update(request, song_id):
    if request.method == "PUT":
        try:
            song = Song.objects.get(pk=song_id)
        except Song.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        data = json.loads(request.body)

        song.title = data.get("title", song.title)
        song.artist = data.get("artist", song.artist)
        song.duration = data.get("duration", song.duration)
        song.genre = data.get("genre", song.genre)
        song.save()

        return JsonResponse({"message": "Song updated"})


@csrf_exempt
def song_delete(request, song_id):
    if request.method == "DELETE":
        try:
            song = Song.objects.get(pk=song_id)
        except Song.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        song.delete()
        return JsonResponse({"message": "Song deleted"})


# ======================
# USER CRUD
# ======================
def user_list(request):
    users = list(User.objects.values())
    return JsonResponse(users, safe=False)


@csrf_exempt
def user_create(request):
    if request.method == "POST":
        data = json.loads(request.body)

        user = User.objects.create(
            username=data.get("username"),
            email=data.get("email"),
            status=data.get("status")
        )

        return JsonResponse({"message": "User created", "id": str(user.userId)})

@csrf_exempt
def user_update(request, user_id):
    if request.method == "PUT":
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        data = json.loads(request.body)

        user.username = data.get("username", user.username)
        user.email = data.get("email", user.email)
        user.status = data.get("status", user.status)
        user.save()

        return JsonResponse({"message": "User updated"})


@csrf_exempt
def user_delete(request, user_id):
    if request.method == "DELETE":
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        user.delete()
        return JsonResponse({"message": "User deleted"})
# ======================
# FOLDER CRUD
# ======================
def folder_list(request):
    folders = list(Folder.objects.values())
    return JsonResponse(folders, safe=False)


@csrf_exempt
def folder_create(request):
    if request.method == "POST":
        data = json.loads(request.body)

        library = Library.objects.first()
        if library is None:
            return JsonResponse({"error": "No library found"}, status=400)

        folder = Folder.objects.create(
            name=data.get("name"),
            library=library
        )

        return JsonResponse({"message": "Folder created", "id": str(folder.folderId)})

@csrf_exempt
def folder_update(request, folder_id):
    if request.method == "PUT":
        try:
            folder = Folder.objects.get(pk=folder_id)
        except Folder.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        data = json.loads(request.body)

        folder.name = data.get("name", folder.name)
        folder.save()

        return JsonResponse({"message": "Folder updated"})


@csrf_exempt
def folder_delete(request, folder_id):
    if request.method == "DELETE":
        try:
            folder = Folder.objects.get(pk=folder_id)
        except Folder.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        folder.delete()
        return JsonResponse({"message": "Folder deleted"})