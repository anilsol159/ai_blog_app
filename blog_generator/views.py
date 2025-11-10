from django.shortcuts import render,redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from pytube import YouTube
import yt_dlp
from django.conf import settings
import os
import assemblyai as aai
from google import genai
# import openai
import markdown
from .models import BlogPost



# Create your views here.
@login_required
def index(request):
    return render(request,'index.html')

# def yt_title(link):
#     print('Entered Title\n\n\n\n\n\n\n\n\n')
#     yt = YouTube(link)
#     print('Fetched object Title\n\n\n\n\n\n\n\n\n')
#     title = yt.title
#     print(f'{title}\n\n\n\n\n\n\n\n\n')
#     return title

def yt_title(link):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(link, download=False)
        return info.get('title')

@csrf_exempt
def generate_blog(request):
    if request.method=='POST':
        yt_link=''
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error':'Invalid data sent'}, status=400)
        
        # get video title
        title = yt_title(yt_link)


        # get video transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error':'Failed to get transcript'},status = 500)

        print('transcription generated \n\n\n\n\n\n\n\n')
        # use open ai to generate the blog
        blog_content= generate_blog_from_transcription(transcription)
        html_content = markdown.markdown(blog_content)
        print('content generated \n\n\n\n\n\n\n\n')
        if not blog_content:
            return JsonResponse({'error':'Failed to generate blog article'},status = 500)
        

        # save blog article to db
        new_blog_article = BlogPost.objects.create(
            user = request.user,
            youtube_title = title,
            yt_link = yt_link,
            generated_content = html_content
        )

        new_blog_article.save()

        # return blog article as a response
        return JsonResponse({'content':html_content})
        # return JsonResponse({'content':transcription})

    else:
        return JsonResponse({'error':'Invalid request method'}, status=405)

# def download_audio(link):
#     yt=YouTube(link)
#     video = yt.streams.filter(only_audio=True).first()
#     out_file = video.download(output_path=settings.MEDIA_ROOT)
#     base,ext = os.path.splitext(out_file)
#     new_file = base + '.mp3'
#     os.rename(out_file,new_file)
#     return new_file


def download_audio(link):
    """Download YouTube video as MP3 and return the saved file path."""
    output_dir = settings.MEDIA_ROOT
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',         # best quality audio
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',  # bitrate
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            mp3_file = f"{base}.mp3"

        # return absolute path of the MP3 file
        return mp3_file

    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None


def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = ""

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    return transcript.text

# def generate_blog_from_transcription(transcript):
#     openai.api_key = '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'

#     prompt = f"Based on the following transcription from a YouTube video, write a comprehensive blog article, write it based on the transcript, but don't make it look like a youtube video, make it look like a proper blog article:\n\n{transcript}\n\nArticle:"

#     response = openai.completions.create(
#         model='text-davinci-003',
#         prompt=prompt,
#         max_tokens=1000
#     )

#     generated_content = response.choices[0].text.strip()
#     return generated_content

def generate_blog_from_transcription(transcript):
    client = genai.Client(api_key='')

    prompt = f"Based on the following transcription from a YouTube video, write a comprehensive blog article, write it based on the transcript, but don't make it look like a youtube video, make it look like a proper blog article:\n\n{transcript}\n\nArticle:"

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text

def user_login(request):
    if request.method=='POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request,username=username,password=password)
        if user is not None:
            login(request,user)
            return redirect('/')
        else:
            error_message = 'Invalid username or password'
            return render(request, 'login.html',{'error_message':error_message})
    return render(request, 'login.html')

def user_signup(request):
    if request.method=='POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password==repeatPassword:
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                user.save()
                login(request,user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message':error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message':error_message})
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')


def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, 'all-blogs.html',{
        'blog_articles':blog_articles,
    })


def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user==blog_article_detail.user:
        return render(request, 'blog-details.html',{
            'blog_article_detail':blog_article_detail
        })
    else:
        return redirect('/')