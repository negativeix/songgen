from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from .models import Song, Library


def song_list(request):
    songs = list(Song.objects.values())
    return JsonResponse(songs, safe=False)

@csrf_exempt
def song_create(request):
    if request.method == "POST":
        data = json.loads(request.body)

        library = Library.objects.first()
    if library is None:
        return JsonResponse({"error": "No library found. Please create one first."}, status=400)

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
        data = json.loads(request.body)

        try:
            song = Song.objects.get(pk=song_id)
        except Song.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

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