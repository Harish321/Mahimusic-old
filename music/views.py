from django.contrib.auth import authenticate, login
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404,redirect
from django.db.models import Q
from .forms import AlbumForm, SongForm, UserForm
from .models import Album, Song
from django.http import HttpResponseRedirect
import os, sys

AUDIO_FILE_TYPES = ['wav', 'mp3', 'ogg']
IMAGE_FILE_TYPES = ['png', 'jpg', 'jpeg']
from mutagen import *
def create_album(request):
    if not request.user.is_authenticated():
        return render(request, 'music/login.html')
    else:
        form = AlbumForm(request.POST or None, request.FILES or None)
        if form.is_valid():
            album = form.save(commit=False)
            album.user = request.user
            album.album_logo = request.FILES['album_logo']
            file_type = album.album_logo.url.split('.')[-1]
            file_type = file_type.lower()
            if file_type not in IMAGE_FILE_TYPES:
                context = {
                    'album': album,
                    'form': form,
                    'error_message': 'Image file must be PNG, JPG, or JPEG',
                }
                return render(request, 'music/create_album.html', context)
            album.save()
            return render(request, 'music/detail.html', {'album': album})
        context = {
            "form": form,
        }
        return render(request, 'music/create_album.html', context)

'''
files variable stores all the uploaded files.

'''
def create_song(request):
    form = SongForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        files = request.FILES.getlist('audio_file')
        for a in files:
            file = File(a)
            
            '''IF there isn't any data about album in the mp3 it sets it to unknown'''
            file_album_name=''
            if 'TALB' in file:
                file_album_name=file.tags['TALB']
            else:
                file_album_name='Unknown'
            
            '''If album is created for the first time'''
            if not Album.objects.filter(album_title=file_album_name,user=request.user):
                '''
                The below if condition takes care of first time upload
                i.e
                If there is no folder for the new user then it creates one
                '''

                if not os.path.exists('media/'+str(request.user.pk)):
                    os.makedirs('media/'+str(request.user.pk))
            

                '''new folder for the album is created'''
                if not os.path.exists(('media/'+str(request.user.pk)+'/'+str(file_album_name))):
                    os.makedirs('media/'+str(request.user.pk)+'/'+str(file_album_name))
            

                '''creates a thumbnail for the album'''
                filename='default.jpg'#default image
                if 'APIC:' in file:
                    artwork = file.tags['APIC:'].data
                    filename='media/'+str(request.user.pk)+'/'+str(file_album_name)+'/'+str(file_album_name)+'.jpg'
                    with open(filename, 'w+') as img:
                        img.write(artwork) # write artwork to new image
                
                    statinfo = os.stat(filename)#gives details of the image
                    if statinfo.st_size==0:
                        '''If there is no image then we use default'''
                        filename='default.jpg'
                    else:
                        '''The below file name stores address .../..../media/filename'''
                        filename=str(request.user.pk)+'/'+str(file_album_name)+'/'+str(file_album_name)+'.jpg'

                new=Album(album_title=file_album_name,user=request.user,album_logo=filename)
                new.save()
                '''If the album exists then below else statement checks if the uploaded is duplicate song or not'''
            else:
                if Song.objects.filter(user=request.user,album__album_title=file_album_name,song_title=file.tags['TIT2']):
                    context = {
                        'form': form,
                        'error_message': 'You already added that song',
                    }
                    return render(request, 'music/create_song.html', context)
            
            '''save the uploaded files to the file system and insert into database'''
            song_title=file.tags['TIT2']
            with open(str("media/"+str(request.user.pk)+"/"+str(file_album_name)+"/"+str(song_title)+".mp3"), 'wb+') as destination:
                for chunk in a.chunks():
                    destination.write(chunk)
            upload_url = str(request.user.pk)+"/"+str(file_album_name)+"/"+str(song_title)+".mp3"
            new_song = Song(user = request.user, album = Album.objects.get(album_title=file_album_name,user=request.user), song_title = song_title, audio_file = upload_url)
            new_song.save()
            
        return HttpResponseRedirect('/') #redirects to the home page
    context = {
        'form': form,
    }
    return render(request, 'music/create_song.html', context)


def delete_album(request, album_id):
    album = Album.objects.get(pk=album_id)
    album.delete()
    albums = Album.objects.filter(user=request.user)
    return render(request, 'music/index.html', {'albums': albums})


def delete_song(request, album_id, song_id):
    album = get_object_or_404(Album, pk=album_id)
    song = Song.objects.get(pk=song_id)
    song.delete()
    return render(request, 'music/detail.html', {'album': album})


def detail(request, album_id):
    if not request.user.is_authenticated():
        return render(request, 'music/login.html')
    else:
        user = request.user
        album = get_object_or_404(Album, pk=album_id)
        return render(request, 'music/detail.html', {'album': album, 'user': user})


def favorite(request, song_id):
    song = get_object_or_404(Song, pk=song_id)
    try:
        if song.is_favorite:
            song.is_favorite = False
        else:
            song.is_favorite = True
        song.save()
    except (KeyError, Song.DoesNotExist):
        return JsonResponse({'success': False})
    else:
        return JsonResponse({'success': True})


def favorite_album(request, album_id):
    album = get_object_or_404(Album, pk=album_id)
    try:
        if album.is_favorite:
            album.is_favorite = False
        else:
            album.is_favorite = True
        album.save()
    except (KeyError, Album.DoesNotExist):
        return JsonResponse({'success': False})
    else:
        return JsonResponse({'success': True})


def index(request):
    if not request.user.is_authenticated():
        return render(request, 'music/login.html')
    else:
        albums = Album.objects.filter(user=request.user)
        song_results = Song.objects.all()
        query = request.GET.get("q")
        if query:
            albums = albums.filter(
                Q(album_title__icontains=query) |
                Q(artist__icontains=query)
            ).distinct()
            song_results = song_results.filter(
                Q(song_title__icontains=query)
            ).distinct()
            return render(request, 'music/index.html', {
                'albums': albums,
                'songs': song_results,
            })
        else:
            return render(request, 'music/index.html', {'albums': albums})


def logout_user(request):
    logout(request)
    form = UserForm(request.POST or None)
    context = {
        "form": form,
    }
    return render(request, 'music/login.html', context)


def login_user(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                albums = Album.objects.filter(user=request.user)
                return render(request, 'music/index.html', {'albums': albums})
            else:
                return render(request, 'music/login.html', {'error_message': 'Your account has been disabled'})
        else:
            return render(request, 'music/login.html', {'error_message': 'Invalid login'})
    return render(request, 'music/login.html')


def register(request):
    form = UserForm(request.POST or None)
    if form.is_valid():
        user = form.save(commit=False)
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user.set_password(password)
        user.save()
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                albums = Album.objects.filter(user=request.user)
                return render(request, 'music/index.html', {'albums': albums})
    context = {
        "form": form,
    }
    return render(request, 'music/register.html', context)


def songs(request, filter_by):
    if not request.user.is_authenticated():
        return render(request, 'music/login.html')
    else:
        try:
            song_ids = []
            for album in Album.objects.filter(user=request.user):
                for song in album.song_set.all():
                    song_ids.append(song.pk)
            users_songs = Song.objects.filter(pk__in=song_ids)
            if filter_by == 'favorites':
                users_songs = users_songs.filter(is_favorite=True)
        except Album.DoesNotExist:
            users_songs = []
        return render(request, 'music/songs.html', {
            'song_list': users_songs,
            'filter_by': filter_by,
        })
